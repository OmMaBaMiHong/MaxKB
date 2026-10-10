# coding=utf-8
"""
    @project: MaxKB
    @file: product_tenant.py
    @desc: 产品×用户矩阵租户上下文（C 端开放面专用）。
           令牌 = 标准 JWT HS256（手动实现，零外部依赖），由 Chaos 网关
           （apps/api/src/open/knowledge-gateway.ts）用共享密钥 KNOWLEDGE_TENANT_SECRET
           签发，本服务只验签不签发用户令牌；三层查询矩阵见
           docs/project/kb-product-plan-2026-10-09.md：
           L1 按产品查 / L2 产品下按用户查 / L3 超管按 User ID 跨产品查
"""
import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _
from rest_framework.authentication import TokenAuthentication

from common.exception.app_exception import AppAuthenticationFailed
from maxkb.const import CONFIG

TENANT_SALT = "kb.product.tenant"  # 兼容保留：现契约已迁移到标准 JWT，salt 不再参与签名
ROLE_USER = "user"
ROLE_PRODUCT_ADMIN = "product_admin"
ROLE_SUPER_ADMIN = "super_admin"
_ROLES = (ROLE_USER, ROLE_PRODUCT_ADMIN, ROLE_SUPER_ADMIN)


def _secret() -> str:
    secret = str(CONFIG.get('PRODUCT_TENANT_SECRET', '') or '')
    if not secret:
        raise AppAuthenticationFailed(1500, _("产品租户上下文未配置（PRODUCT_TENANT_SECRET）"))
    return secret


def _b64url_decode(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _hmac_signature(signing_input: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest()
    return _b64url_encode(digest)


@dataclass
class ProductTenantContext:
    product_id: str
    user_id: str
    role: str = ROLE_USER

    def knowledge_filters(self, owner_user_id: str | None = None) -> dict:
        """
        三层查询矩阵 → Knowledge 查询过滤条件
        """
        if self.role == ROLE_SUPER_ADMIN:
            # L3：超管默认全量，可显式按用户收敛（跨产品）
            return {"owner_user_id": owner_user_id} if owner_user_id else {}
        if self.role == ROLE_PRODUCT_ADMIN:
            # L1：产品内全量；显式 owner_user_id 时下钻到 L2（产品内按用户）
            filters = {"workspace_id": self.product_id}
            if owner_user_id:
                filters["owner_user_id"] = owner_user_id
            return filters
        # C 端用户永远双过滤：自己的产品 + 自己；显式指定他人属主直接拒绝
        if owner_user_id and owner_user_id != self.user_id:
            raise AppAuthenticationFailed(1403, _("无权访问其他用户的数据"))
        return {"workspace_id": self.product_id, "owner_user_id": self.user_id}


def issue_product_tenant_token(product_id: str, user_id: str, role: str, expires_seconds: int = 300) -> str:
    """签发标准 JWT HS256（与 Chaos 网关 knowledge-gateway.ts 逐字节对齐）；
    生产由网关持有共享密钥，此处供联调测试。"""
    if role not in _ROLES:
        raise ValueError(f"unknown tenant role: {role}")
    now = int(time.time())
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode("utf-8"))
    payload = _b64url_encode(
        json.dumps(
            {"productId": product_id, "userId": user_id, "role": role, "iat": now, "exp": now + expires_seconds},
            separators=(",", ":"),
        ).encode("utf-8")
    )
    return f"{header}.{payload}.{_hmac_signature(f'{header}.{payload}', _secret())}"


def parse_product_tenant_token(token: str) -> ProductTenantContext:
    try:
        header_b64, payload_b64, signature = token.split(".")
        if not hmac.compare_digest(signature, _hmac_signature(f"{header_b64}.{payload_b64}", _secret())):
            raise ValueError("bad signature")
        header = json.loads(_b64url_decode(header_b64))
        if header.get("alg") != "HS256":
            raise ValueError("bad alg")
        payload = json.loads(_b64url_decode(payload_b64))
    except AppAuthenticationFailed:
        raise
    except Exception:
        raise AppAuthenticationFailed(1401, _("租户上下文无效"))
    if not isinstance(payload, dict) or int(payload.get("exp", 0)) < time.time():
        raise AppAuthenticationFailed(1401, _("租户上下文已过期"))
    role = payload.get("role") or payload.get("r") or ROLE_USER
    product_id = payload.get("productId") or payload.get("p")
    user_id = payload.get("userId") or payload.get("u")
    if role not in _ROLES or not product_id or not user_id:
        raise AppAuthenticationFailed(1401, _("租户上下文字段非法"))
    return ProductTenantContext(product_id=product_id, user_id=user_id, role=role)


class ProductTenantAuthentication(TokenAuthentication):
    """
    C 端开放面专用认证：Authorization: Bearer <租户令牌>（兼容 X-KB-Tenant 头）。
    不注册进全局 AUTH_HANDLES，只挂在产品路由上，不影响管理端 Bearer 语义。
    认证通过后 request.product_tenant = ProductTenantContext。
    """
    keyword = "Bearer"

    def authenticate(self, request):
        tenant_token = request.META.get('HTTP_X_KB_TENANT')
        if not tenant_token:
            auth = request.META.get('HTTP_AUTHORIZATION', '')
            tenant_token = auth[7:] if auth.startswith('Bearer ') else None
        if not tenant_token:
            raise AppAuthenticationFailed(1003, _("缺少产品租户上下文"))
        context = parse_product_tenant_token(tenant_token)
        request.product_tenant = context
        return context, None
