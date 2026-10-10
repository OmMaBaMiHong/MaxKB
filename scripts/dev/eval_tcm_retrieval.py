"""混沌海 · 中医检索质量基线评测。

流程：评测语料（条文/方剂）→ tcm 切分入库 → celery 向量化 →
逐 case 跑 keywords 检索（真实 jieba 词法，不依赖外部 embedding key）→
hit@1 / hit@3 统计 + 断言。blend/向量模式的语义评测待接入真实 embedding 后启用。

用法：仓库根目录 `uv run python scripts/dev/eval_tcm_retrieval.py [--fixture 路径]`
前置：web(8080) + celery + embedding_mock(9401) 已启动。
"""
import json
import os
import sys
import time

sys.path.insert(0, "apps")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "maxkb.settings")
import django  # noqa: E402

django.setup()

import httpx  # noqa: E402
import uuid as _uuid  # noqa: E402

from common.auth.product_tenant import issue_product_tenant_token  # noqa: E402
from common.utils.rsa_util import rsa_long_encrypt  # noqa: E402
from knowledge.models import Knowledge, Document, Embedding  # noqa: E402
from models_provider.models import Model as ModelModel  # noqa: E402

fixture_path = "scripts/dev/fixtures/tcm_eval.json"
if "--fixture" in sys.argv:
    fixture_path = sys.argv[sys.argv.index("--fixture") + 1]
fixture = json.load(open(fixture_path, encoding="utf-8"))

BASE = "http://127.0.0.1:8080/product-api/api"
K = fixture["hit_at_k"]
client = httpx.Client(base_url=BASE, timeout=60)
P, U = "pilot-tcm", "u1001"
token = issue_product_tenant_token(P, U, "user")
headers = {"Authorization": f"Bearer {token}"}
failures = []

# 1. 建库 + 绑 mock embedding（keywords 检索不依赖它，但入库管线要求已绑定）
r = client.post("/knowledge", json={"name": "中医评测库"}, headers=headers)
kid = r.json()["data"]["id"]
model = ModelModel.objects.filter(name="dev-embed-mock", model_type="EMBEDDING").first()
if model is None:
    model = ModelModel.objects.create(
        name="dev-embed-mock", model_type="EMBEDDING", model_name="mock-embedding-1024",
        provider="model_openai_provider", status="SUCCESS",
        credential=rsa_long_encrypt(json.dumps({"api_key": "dev", "api_base": "http://127.0.0.1:9401/v1"})),
        workspace_id=P,
    )
Knowledge.objects.filter(id=kid).update(embedding_model_id=model.id)

# 2. tcm 切分入库（走产品 API 的领域切分参数）
doc_payload = dict(fixture["document"])
doc_payload["content"] = fixture["content"]
doc_payload["name"] = doc_payload["name"] + f"-{_uuid.uuid4().hex[:6]}"
r = client.post(f"/knowledge/{kid}/documents", json=doc_payload, headers=headers)
assert r.json().get("code") == 200, r.text[:200]
doc_id = r.json()["data"]["id"]

# 3. 轮询向量化完成
for _ in range(60):
    emb = Embedding.objects.filter(knowledge_id=kid, is_active=True).count()
    if emb >= fixture["expect_blocks_min"]:
        break
    time.sleep(1)
print(f"语料块 embedding 数: {emb}")

# 4. 逐 case 检索评分
hit1 = hit3 = 0
for case in fixture["cases"]:
    r = client.post(
        f"/knowledge/{kid}/search",
        json={"query": case["query"], "search_mode": case["mode"], "top_number": K, "similarity": 0.0},
        headers=headers,
    )
    hits = r.json().get("data") or []
    texts = json.dumps(hits, ensure_ascii=False)
    top1_hit = K >= 1 and len(hits) >= 1 and case["expect_keyword"] in texts[: len(texts) // max(len(hits), 1)]
    top3_hit = any(case["expect_keyword"] in json.dumps(h, ensure_ascii=False) for h in hits[:K])
    hit1 += 1 if top1_hit else 0
    hit3 += 1 if top3_hit else 0
    mark = "PASS" if top3_hit else "FAIL"
    print(f"{mark} {case['query']} → top{K} 命中期望词[{case['expect_keyword']}]={top3_hit} hits={len(hits)}")
    if not top3_hit:
        failures.append(case["query"])

# 5. 元数据证据：命中段落标题应携带 书·篇·条号
r = client.post(f"/knowledge/{kid}/search", json={"query": "桂枝汤", "search_mode": "keywords", "similarity": 0.0, "top_number": 5}, headers=headers)
titles = [h.get("title") or (h.get("paragraph") or {}).get("title", "") for h in (r.json().get("data") or [])]
has_meta = any("第" in t and "·" in t for t in titles if t)
print(f"段落标题元数据样例: {titles[:2]}")
if not has_meta:
    print("WARN 检索结果未携带条号标题（HitTest 返回字段口径待核对）")

print(f"\n==== TCM 检索基线: hit@1 {hit1}/{len(fixture['cases'])}, hit@{K} {hit3}/{len(fixture['cases'])} ====")

# 6. 清理评测库
client.delete(f"/knowledge/{kid}", headers=headers)

sys.exit(1 if failures else 0)
