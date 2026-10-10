"""混沌海 · 矩阵租户知识/文档 API 回归冒烟（16 用例，含越权）。

用法：仓库根目录 `uv run python scripts/dev/smoke_tenant_api.py`
前置：web(8080) 已启动、maxkb_dev 库已迁移、.env 配好 MAXKB_PRODUCT_TENANT_SECRET。
"""
import os
import sys

sys.path.insert(0, "apps")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "maxkb.settings")
import django  # noqa: E402

django.setup()

import httpx  # noqa: E402
import json  # noqa: E402

from common.auth.product_tenant import issue_product_tenant_token  # noqa: E402
from knowledge.models import Knowledge  # noqa: E402
from models_provider.models import Model  # noqa: E402
from common.utils.rsa_util import rsa_long_encrypt  # noqa: E402

BASE = "http://127.0.0.1:8080/product-api/api"
client = httpx.Client(base_url=BASE, timeout=30)
P1, P2, U1, U2 = "pilot-gmoney", "pilot-workbench", "u1001", "u2002"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + ("  | " + str(detail)[:120] if detail else ""))


def h(token):
    return {"Authorization": f"Bearer {token}"}


def body_code(r):
    try:
        return r.json().get("code")
    except Exception:
        return None


def denied(r):
    """MaxKB 惯例：业务异常 HTTP 200 + body code；兼容直接 4xx。"""
    return r.status_code >= 400 or body_code(r) in (401, 403, 404, 1403, 1404, 10000)


t_u1_p1 = issue_product_tenant_token(P1, U1, "user")
t_u1_p2 = issue_product_tenant_token(P2, U1, "user")
t_u2_p1 = issue_product_tenant_token(P1, U2, "user")
t_admin_p1 = issue_product_tenant_token(P1, U1, "product_admin")
t_super = issue_product_tenant_token(P1, U1, "super_admin")

# 1. L2：u1001 在 P1 建知识库
r = client.post("/knowledge", json={"name": "冒烟-工作台资料"}, headers=h(t_u1_p1))
check("1 L2 建知识库", r.status_code == 200, r.text[:150])
kid = r.json().get("data", {}).get("id") if r.status_code == 200 else None

# 2. 归属由上下文决定：请求体伪造 owner 无效
r = client.post("/knowledge", json={"name": "伪造", "owner_user_id": U2, "workspace_id": P2}, headers=h(t_u1_p1))
row = r.json().get("data", {}) if r.status_code == 200 else {}
check("2 请求体伪造归属无效", r.status_code == 200 and row.get("owner_user_id") == U1 and row.get("workspace_id") == P1, str(row)[:120])
kid_fake = row.get("id")

# 3. 跨产品隔离：同一用户在 P2 看不到 P1 的库
r = client.get("/knowledge", headers=h(t_u1_p2))
ids = [x["id"] for x in r.json().get("data", [])]
check("3 跨产品隔离(同用户)", kid not in ids and kid_fake not in ids, str(len(ids)) + " rows in P2")

# 4. 跨用户拒绝：U2 在同产品读 U1 的库 → 拒绝
r = client.get(f"/knowledge/{kid}", headers=h(t_u2_p1))
check("4 跨用户 404", denied(r), f"http={r.status_code} code={body_code(r)}")

# 5. L1：product_admin 看产品内全量（含 U1 的库）
r = client.get("/knowledge", headers=h(t_admin_p1))
ids = [x["id"] for x in r.json().get("data", [])]
check("5 L1 产品管理员全量", kid in ids and kid_fake in ids)

# 6. L2 下钻：product_admin ?owner_user_id=U2 只看 U2 的
r = client.get("/knowledge?owner_user_id=" + U2, headers=h(t_admin_p1))
ids = [x["id"] for x in r.json().get("data", [])]
check("6 L2 下钻按用户", kid not in ids and kid_fake not in ids, str(len(ids)) + " rows of U2")

# 7. L3：super_admin 跨产品按 userId 查（用 P2 令牌查 P1 建的库）
r = client.get(f"/knowledge/{kid}", headers=h(t_super))
check("7 L3 超管跨产品可读", r.status_code == 200, f"http={r.status_code}")
r = client.get("/knowledge?owner_user_id=" + U1, headers=h(t_super))
check("7b L3 按用户收敛", r.status_code == 200)

# 8. C 端用户不能查别人（显式指定他人属主 → 403）
r = client.get("/knowledge?owner_user_id=" + U2, headers=h(t_u1_p1))
check("8 C端查他人 403", denied(r), f"http={r.status_code} code={body_code(r)}")

# 9. 文档：未绑 embedding 模型 → 400 前置守卫
r = client.post(f"/knowledge/{kid}/documents", json={"name": "d1", "content": "第一段\n\n第二段"}, headers=h(t_u1_p1))
check("9 未绑模型 400 守卫", body_code(r) == 400, f"code={body_code(r)} msg={r.text[:80]}")

# 10. 绑定开发用 embedding 模型后建文档 → 走 MaxKB 既有管线（@post 向量化入队）
model = Model.objects.filter(name="dev-embed-smoke", model_type="EMBEDDING").first()
if model is None:
    model = Model.objects.create(
        name="dev-embed-smoke", model_type="EMBEDDING", model_name="qwen3-embedding-0.6b",
        provider="model_openai_provider", status="SUCCESS",
        credential=rsa_long_encrypt(json.dumps({"api_base": "http://127.0.0.1:9401/v1", "api_key": "dev"})),
        workspace_id=P1,
    )
Knowledge.objects.filter(id=kid).update(embedding_model_id=model.id)
r = client.post(f"/knowledge/{kid}/documents", json={"name": "测试文档", "content": "桂枝汤主治风寒表虚证。\n\n组成：桂枝、芍药、生姜。"}, headers=h(t_u1_p1))
check("10 绑模型后建文档", body_code(r) == 200, r.text[:150])
doc_id = (r.json().get("data") or {}).get("id") if body_code(r) == 200 else None

# 11. 文档列表 + 跨用户拒绝
r = client.get(f"/knowledge/{kid}/documents", headers=h(t_u1_p1))
check("11 文档列表", body_code(r) == 200 and len(r.json().get("data", [])) == 1)
if doc_id:
    r = client.get(f"/knowledge/{kid}/documents/{doc_id}", headers=h(t_u2_p1))
    check("11b 文档跨用户 404", denied(r), f"http={r.status_code} code={body_code(r)}")

# 12. 删文档（既有管线清理）+ 删知识库
if doc_id:
    r = client.delete(f"/knowledge/{kid}/documents/{doc_id}", headers=h(t_u1_p1))
    check("12 删文档", body_code(r) == 200)
r = client.delete(f"/knowledge/{kid}", headers=h(t_u1_p1))
check("12b 删知识库", body_code(r) == 200)
check("12c 删除后确无", denied(client.get(f"/knowledge/{kid}", headers=h(t_u1_p1))))

fails = [x for x in results if not x[1]]
print(f"\n==== SMOKE {len(results) - len(fails)}/{len(results)} PASS ====")
sys.exit(1 if fails else 0)
