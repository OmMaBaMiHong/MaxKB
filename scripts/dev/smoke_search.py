"""混沌海 · 检索链路冒烟：mock embedding → celery 向量化 → pgvector blend/keywords 检索 → 三层矩阵越权。

用法：仓库根目录 `uv run python scripts/dev/smoke_search.py`
前置：web(8080) + celery worker 已启动；scripts/dev/embedding_mock.py 已启动（9401）。
"""
import os
import sys
import time

sys.path.insert(0, "apps")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "maxkb.settings")
import django  # noqa: E402

django.setup()

import httpx  # noqa: E402
import json  # noqa: E402

from common.auth.product_tenant import issue_product_tenant_token  # noqa: E402
from knowledge.models import Knowledge, Document, Embedding  # noqa: E402
from models_provider.models import Model as ModelModel  # noqa: E402
from common.utils.rsa_util import rsa_long_encrypt  # noqa: E402

BASE = "http://127.0.0.1:8080/product-api/api"
client = httpx.Client(base_url=BASE, timeout=60)
P1, U1, U2 = "pilot-gmoney", "u1001", "u2002"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + ("  | " + str(detail)[:150] if detail else ""))


def h(token):
    return {"Authorization": f"Bearer {token}"}


def body_code(r):
    try:
        return r.json().get("code")
    except Exception:
        return None


def denied(r):
    return r.status_code >= 400 or body_code(r) in (401, 403, 404, 1403, 1404, 10000)


t_u1 = issue_product_tenant_token(P1, U1, "user")
t_u2 = issue_product_tenant_token(P1, U2, "user")

# 1. 建知识库并绑定 mock embedding（openai 兼容 → 本地 mock 服务）
r = client.post("/knowledge", json={"name": "检索冒烟库"}, headers=h(t_u1))
kid = r.json()["data"]["id"]
model = ModelModel.objects.filter(name="dev-embed-mock", model_type="EMBEDDING").first()
if model is None:
    model = ModelModel.objects.create(
        name="dev-embed-mock", model_type="EMBEDDING", model_name="mock-embedding-1024",
        provider="model_openai_provider", status="SUCCESS",
        credential=rsa_long_encrypt(json.dumps({"api_key": "dev", "api_base": "http://127.0.0.1:9401/v1"})),
        workspace_id=P1,
    )
Knowledge.objects.filter(id=kid).update(embedding_model_id=model.id)

# 2. 未绑库检索 → 400
r2 = client.post("/knowledge", json={"name": "检索-未绑模型"}, headers=h(t_u1))
kid_nobind = r2.json()["data"]["id"]
r = client.post(f"/knowledge/{kid_nobind}/search", json={"query": "任意"}, headers=h(t_u1))
check("1 未绑模型检索 400", body_code(r) == 400, f"code={body_code(r)}")

# 3. 建文档 → celery 异步向量化（mock 服务出向量）
r = client.post(
    f"/knowledge/{kid}/documents",
    json={"name": "伤寒论摘要", "content": "桂枝汤主治风寒表虚证，发热汗出。\n\n麻黄汤主治风寒表实证，无汗而喘。"},
    headers=h(t_u1),
)
check("2 建文档", body_code(r) == 200, r.text[:120])

# 4. 轮询向量化落库
ok = False
emb = 0
for _ in range(45):
    docs = Document.objects.filter(knowledge_id=kid).count()
    emb = Embedding.objects.filter(knowledge_id=kid, is_active=True).count()
    if docs >= 1 and emb >= 1:
        ok = True
        break
    time.sleep(1)
check("3 celery 向量化落库", ok, f"docs={docs} embeddings={emb}")

# 5. blend 检索命中
r = client.post(f"/knowledge/{kid}/search", json={"query": "桂枝汤治什么", "top_number": 5, "similarity": 0.3}, headers=h(t_u1))
hits = r.json().get("data") or []
check("4 blend 检索命中", body_code(r) == 200 and len(hits) >= 1, f"hits={len(hits)}")

# 6. keywords 检索（用 jieba 分词粒度内的 token）
r = client.post(f"/knowledge/{kid}/search", json={"query": "风寒", "search_mode": "keywords", "similarity": 0.1}, headers=h(t_u1))
hits_k = r.json().get("data") or []
check("5 keywords 检索命中", body_code(r) == 200 and len(hits_k) >= 1, f"hits={len(hits_k)}")

# 7. 跨用户检索拒绝
r = client.post(f"/knowledge/{kid}/search", json={"query": "桂枝"}, headers=h(t_u2))
check("6 跨用户检索拒绝", denied(r), f"http={r.status_code} code={body_code(r)}")

# 8. 删除清理验证
r = client.delete(f"/knowledge/{kid}", headers=h(t_u1))
check("7 删知识库", body_code(r) == 200)

fails = [x for x in results if not x[1]]
print(f"\n==== SEARCH SMOKE {len(results) - len(fails)}/{len(results)} PASS ====")
sys.exit(1 if fails else 0)
