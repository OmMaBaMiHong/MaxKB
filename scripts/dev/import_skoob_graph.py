"""Skoob Neo4j 拆书成果 → 混沌海 全量迁移（完结书验证）。

从 skoob Neo4j 导出指定 graph_id 的：
  - TianwangChunk（正文块，含章节号/标题）→ paragraphs 预切分直灌
  - Entity（实体，graph_id 圈定）→ GraphNode
  - Entity 间 RELATED_TO → GraphEdge
向量由混沌海管线重嵌（Qwen3），不迁移旧向量。

用法：仓库根目录 `uv run python scripts/dev/import_skoob_graph.py <graph_id>`
前置：web(8080)+celery 已启动；skooob-neo4j 在 17687。
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, "apps")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "maxkb.settings")
import django  # noqa: E402

django.setup()

import httpx  # noqa: E402

from common.auth.product_tenant import issue_product_tenant_token  # noqa: E402
from knowledge.models import Embedding, GraphEdge, GraphNode, Knowledge  # noqa: E402
from models_provider.models import Model as ModelModel  # noqa: E402

NEO_PASS = os.environ.get(
    "NEO4J_PASSWORD",
    next(line.split("=", 1)[1].strip() for line in open("/Users/wade/work-space/skoob/.env") if line.startswith("NEO4J_PASSWORD=")),
)
from neo4j import GraphDatabase  # noqa: E402

_neo = GraphDatabase.driver("bolt://127.0.0.1:17687", auth=("neo4j", NEO_PASS))
GRAPH_ID = sys.argv[1] if len(sys.argv) > 1 else "general-2b2c2c1bba54884d40b0c70790a7d98d79bc8618"
P, U = os.environ.get("IMPORT_PRODUCT", "default"), os.environ.get("IMPORT_USER", "admin")
BATCH = 200


def cypher(query: str) -> list:
    """neo4j Python 驱动直查 → 字典列表。"""
    with _neo.session() as session:
        return [dict(record) for record in session.run(query)]


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'")


print(f"目标 graph_id: {GRAPH_ID}")

# ── 1. 书名（从 skoob PG 的 asset.graph_id 反查）──
title_rows = subprocess.run(
    ["docker", "exec", "skoob-postgres", "psql", "-U", "skoob", "-d", "skoob", "-tAc",
     f"SELECT title FROM asset WHERE graph_id='{GRAPH_ID}' LIMIT 1"],
    capture_output=True, text=True,
).stdout.strip()
book_title = title_rows or GRAPH_ID[:16]
print(f"书名: {book_title}")

# ── 2. 导出正文块 ──
chunk_rows = cypher(
    f"MATCH (c:TianwangChunk {{bookId: 'book:{GRAPH_ID}:chapters'}}) "
    f"RETURN c.text AS text, c.chapterNumber AS ch, c.chunkIndex AS idx, c.title AS title "
    f"ORDER BY toInteger(c.chapterNumber), toInteger(c.chunkIndex)"
)
print(f"正文块: {len(chunk_rows)}")
# 按 章节聚合为段落（同章多块合并）
chapters: dict = {}
for row in chunk_rows:
    ch = str(row.get("ch") or "0")
    chapters.setdefault(ch, []).append(row.get("text") or "")
paragraphs = [
    {"title": f"第{ch}章", "content": "\n".join(parts)}
    for ch, parts in sorted(chapters.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0)
]
print(f"聚合章节: {len(paragraphs)} 章, 总字数 {sum(len(p['content']) for p in paragraphs)}")

# ── 3. 导出实体与关系（graph_id 圈定）──
entity_rows = cypher(
    f"MATCH (e:Entity {{graph_id: '{GRAPH_ID}'}}) "
    f"RETURN e.name AS name, e.type AS type, e.tier AS tier, e.profile AS profile LIMIT 5000"
)
print(f"实体: {len(entity_rows)}")
relation_rows = cypher(
    f"MATCH (a:Entity {{graph_id: '{GRAPH_ID}'}})-[r:RELATED_TO]->(b:Entity {{graph_id: '{GRAPH_ID}'}}) "
    f"RETURN a.name AS src, b.name AS dst, coalesce(r.rel, r.relation, '相关') AS rel LIMIT 5000"
)
print(f"关系: {len(relation_rows)}")

# ── 4. 灌入混沌海 ──
token = issue_product_tenant_token(P, U, "user")
headers = {"Authorization": f"Bearer {token}"}
client = httpx.Client(base_url="http://127.0.0.1:8080/product-api/api", timeout=300)

r = client.post("/knowledge", json={"name": f"拆书·{book_title}"[:150]}, headers=headers)
kid = r.json()["data"]["id"]
qwen = ModelModel.objects.get(name="Qwen3-Embedding-0.6B", model_type="EMBEDDING")
Knowledge.objects.filter(id=kid).update(embedding_model_id=qwen.id)
print("知识库已建:", kid)

# 正文分批（每文档 ≤2000 段；这里一章一段，单文档直灌）
for start in range(0, len(paragraphs), BATCH):
    batch = paragraphs[start:start + BATCH]
    r = client.post(
        f"/knowledge/{kid}/documents",
        json={"name": f"{book_title}·正文·{start + 1}-{start + len(batch)}章", "paragraphs": batch},
        headers=headers,
    )
    assert r.json().get("code") == 200, r.text[:300]
    print(f"  正文批次 {start + 1}-{start + len(batch)} 章已入库")

# 实体/关系 → 图（直写 DB，幂等合并；不调 LLM——拆书成果直接迁移）
k = Knowledge.objects.get(id=kid)
entity_to_node = {}
for row in entity_rows:
    name = str(row.get("name") or "").strip()[:150]
    if not name:
        continue
    node = GraphNode.objects.filter(knowledge=k, name=name).first()
    if node is None:
        node = GraphNode.objects.create(
            knowledge=k, workspace_id=k.workspace_id, name=name,
            type=str(row.get("type") or "其他")[:32],
            description=str(row.get("profile") or "")[:2048],
            mention_count=1, source_paragraph_ids=[],
        )
    entity_to_node[name] = node
edge_count = 0
for row in relation_rows:
    src = entity_to_node.get(str(row.get("src") or "").strip())
    dst = entity_to_node.get(str(row.get("dst") or "").strip())
    if src is None or dst is None or src.id == dst.id:
        continue
    rel = str(row.get("rel") or "相关")[:64]
    if not GraphEdge.objects.filter(knowledge=k, source_node=src, target_node=dst, relation=rel).exists():
        GraphEdge.objects.create(knowledge=k, workspace_id=k.workspace_id, source_node=src, target_node=dst, relation=rel)
        edge_count += 1
print(f"图写入: 节点 {len(entity_to_node)}, 新边 {edge_count}")

# ── 5. 等待向量化完成 ──
for _ in range(600):
    emb = Embedding.objects.filter(knowledge_id=kid, is_active=True).count()
    if emb >= len(paragraphs):
        break
    time.sleep(5)
print(f"向量化: {emb}/{len(paragraphs)}")
print(f"完成。知识库 id: {kid}")
