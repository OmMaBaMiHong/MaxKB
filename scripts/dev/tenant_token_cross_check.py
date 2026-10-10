"""租户令牌跨语言契约测试的 Python 半边（被 tenant_token_cross_check.mjs 调用）。

--issue <productId> <userId> <role>   签发（密钥取 KB_TEST_SECRET 环境变量，直接注入 CONFIG）
--verify <token>                      验签并输出 JSON 结果（ok=true/false）
"""
import json
import os
import sys

sys.path.insert(0, "apps")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "maxkb.settings")
# 测试密钥注入必须在 django.setup() 之前：CONFIG 在 const 导入时冻结，后写环境不生效
test_secret = os.environ.get("KB_TEST_SECRET")
if test_secret:
    os.environ["MAXKB_PRODUCT_TENANT_SECRET"] = test_secret
import django  # noqa: E402

django.setup()

from common.auth.product_tenant import issue_product_tenant_token, parse_product_tenant_token  # noqa: E402

args = sys.argv[1:]
if args and args[0] == "--issue":
    print(issue_product_tenant_token(args[1], args[2], args[3]))
    sys.exit(0)
if args and args[0] == "--verify":
    try:
        ctx = parse_product_tenant_token(args[1])
        print(json.dumps({"ok": True, "productId": ctx.product_id, "userId": ctx.user_id, "role": ctx.role}))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}))
    sys.exit(0)
print("usage: --issue <productId> <userId> <role> | --verify <token>", file=sys.stderr)
sys.exit(2)
