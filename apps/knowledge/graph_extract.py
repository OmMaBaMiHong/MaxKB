# coding=utf-8
"""
    M3 知识图谱抽取服务（混沌海）：LightRAG 风格实体/关系抽取 → PG 邻接表。
    LLM 走 OpenAI 兼容端点（默认本地 LM Studio qwen3-8b，环境变量可换 sub2api/硅基流动）。
    抽取维度沿用 Skoob 拆书验证过的体系（人物/势力/地点/器物/概念/事件…）。
    幂等：实体按 (knowledge, name) 合并，关系按 (knowledge, src, dst, relation) 合并。
"""
import json
import re
import time
import uuid as _uuid

import requests
from django.utils.translation import gettext_lazy as _

from common.utils.logger import maxkb_logger
from knowledge.models import GraphEdge, GraphNode, Paragraph
from maxkb.const import CONFIG

ENTITY_TYPES = "人物、组织、地点、器物、概念、事件、规则、其他"


def _llm_config() -> tuple:
    """LLM 端点：默认本地 LM Studio（qwen3-8b）；CHAOSSEA_LLM_BASE/MODEL/API_KEY 可换 sub2api/硅基流动。"""
    base = str(CONFIG.get("CHAOSSEA_LLM_BASE", "http://127.0.0.1:1234/v1") or "http://127.0.0.1:1234/v1").rstrip("/")
    model = str(CONFIG.get("CHAOSSEA_LLM_MODEL", "qwen/qwen3-8b") or "qwen/qwen3-8b")
    key = str(CONFIG.get("CHAOSSEA_LLM_API_KEY", "lm-studio") or "lm-studio")
    return base, model, key


_PROMPT = """你是知识图谱构建专家。从下面的文本中抽取实体和实体间关系。

实体类型限定：{types}。
要求：
1. 只输出一个 JSON 对象，不要输出任何其他文字或 markdown 代码块标记。
2. 实体名使用文中原名（人名/组织名/地名/器物名），不要概括改写。
3. relations 里的 source/target 必须与 entities 中的 name 完全一致。
4. description 用一句话概括，不超过60字。
5. 关系类型用短词（如：隶属、持有、位于、对抗、师徒、亲属、创造、使用）。

文本：
---
{text}
---

输出格式：
{{"entities": [{{"name": "实体名", "type": "类型", "description": "一句话描述"}}], "relations": [{{"source": "实体名", "target": "实体名", "relation": "关系词", "description": "一句话"}}]}}"""


def _extract_one(text: str, base: str, model: str, key: str, timeout: int = 90) -> dict:
    resp = requests.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": _PROMPT.format(types=ENTITY_TYPES, text=text[:3000])}],
            "temperature": 0.1,
            "max_tokens": 2048,
            "stream": False,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    # 容错：剥掉可能的 ```json 包裹或前后杂文，取第一个完整 JSON 对象
    match = re.search(r"\{.*\}", content, re.S)
    if not match:
        return {"entities": [], "relations": []}
    data = json.loads(match.group(0))
    return {
        "entities": [e for e in data.get("entities", []) if isinstance(e, dict) and e.get("name")],
        "relations": [r for r in data.get("relations", []) if isinstance(r, dict) and r.get("source") and r.get("target")],
    }


def _upsert_node(knowledge, workspace_id, name, etype, description, paragraph_id) -> GraphNode:
    node = GraphNode.objects.filter(knowledge_id=knowledge.id, name=name).first()
    if node is None:
        node = GraphNode.objects.create(
            knowledge=knowledge, workspace_id=workspace_id, name=name[:150],
            type=(etype or "其他")[:32], description=(description or "")[:2048],
            mention_count=1, source_paragraph_ids=[paragraph_id],
        )
        return node
    node.mention_count += 1
    if description and len(description) > len(node.description):
        node.description = description[:2048]
    if paragraph_id and paragraph_id not in node.source_paragraph_ids:
        node.source_paragraph_ids = (node.source_paragraph_ids + [paragraph_id])[:50]
    node.save(update_fields=["mention_count", "description", "source_paragraph_ids", "update_time"])
    return node


def _upsert_edge(knowledge, workspace_id, src: GraphNode, dst: GraphNode, relation, description, paragraph_id):
    relation = (relation or "相关")[:64]
    edge = GraphEdge.objects.filter(
        knowledge_id=knowledge.id, source_node=src, target_node=dst, relation=relation
    ).first()
    if edge is None:
        GraphEdge.objects.create(
            knowledge=knowledge, workspace_id=workspace_id,
            source_node=src, target_node=dst, relation=relation,
            description=(description or "")[:2048], source_paragraph_ids=[paragraph_id],
        )
        return
    if description and description not in (edge.description or ""):
        edge.description = ((edge.description + "；" if edge.description else "") + description)[:2048]
    if paragraph_id and paragraph_id not in edge.source_paragraph_ids:
        edge.source_paragraph_ids = (edge.source_paragraph_ids + [paragraph_id])[:50]
    edge.save(update_fields=["description", "source_paragraph_ids", "update_time"])


def build_graph_for_knowledge(knowledge, limit: int = 40) -> dict:
    """对知识库全部段落做实体/关系抽取并写图。同步执行（demo 规模），生产可转 celery。"""
    base, model, key = _llm_config()
    if not base:
        raise ValueError("LLM 端点未配置（CHAOSSEA_LLM_BASE）")
    workspace_id = knowledge.workspace_id
    paragraphs = list(
        Paragraph.objects.filter(knowledge_id=knowledge.id, is_active=True)
        .order_by("document_id", "position")
        .values("id", "content", "title")[:limit]
    )
    nodes_before = GraphNode.objects.filter(knowledge_id=knowledge.id).count()
    edges_before = GraphEdge.objects.filter(knowledge_id=knowledge.id).count()
    errors = 0
    started = time.time()
    for row in paragraphs:
        text = (row["content"] or "").strip()
        if len(text) < 30:
            continue
        paragraph_id = str(row["id"])
        try:
            data = _extract_one(text, base, model, key)
        except Exception as exc:  # noqa: BLE001
            errors += 1
            maxkb_logger.warning(f"图谱抽取失败 paragraph={paragraph_id}: {exc}")
            continue
        name_to_node = {}
        for ent in data["entities"]:
            node = _upsert_node(knowledge, workspace_id, str(ent["name"]).strip(), ent.get("type"), ent.get("description"), paragraph_id)
            name_to_node[str(ent["name"]).strip()] = node
        for rel in data["relations"]:
            src = name_to_node.get(str(rel["source"]).strip())
            dst = name_to_node.get(str(rel["target"]).strip())
            if src is None or dst is None or src.id == dst.id:
                continue
            _upsert_edge(knowledge, workspace_id, src, dst, rel.get("relation"), rel.get("description"), paragraph_id)
    nodes_after = GraphNode.objects.filter(knowledge_id=knowledge.id).count()
    edges_after = GraphEdge.objects.filter(knowledge_id=knowledge.id).count()
    return {
        "paragraphs": len(paragraphs),
        "errors": errors,
        "nodes_added": nodes_after - nodes_before,
        "edges_added": edges_after - edges_before,
        "nodes_total": nodes_after,
        "edges_total": edges_after,
        "seconds": round(time.time() - started, 1),
        "llm": f"{base} ({model})",
    }


def get_graph(knowledge, limit_nodes: int = 300) -> dict:
    """读图（租户已由上层过滤）：节点+边，前端渲染用。"""
    nodes = list(
        GraphNode.objects.filter(knowledge_id=knowledge.id)
        .order_by("-mention_count")[:limit_nodes]
    )
    node_ids = {n.id for n in nodes}
    edges = GraphEdge.objects.filter(
        knowledge_id=knowledge.id, source_node_id__in=node_ids, target_node_id__in=node_ids
    ).select_related("source_node", "target_node")
    return {
        "nodes": [
            {
                "id": str(n.id), "name": n.name, "type": n.type,
                "description": n.description, "mentions": n.mention_count,
                "sources": [str(s) for s in (n.source_paragraph_ids or [])][:5],
            }
            for n in nodes
        ],
        "edges": [
            {
                "source": str(e.source_node_id), "target": str(e.target_node_id),
                "relation": e.relation, "description": e.description,
            }
            for e in edges
        ],
    }
