# coding=utf-8
"""
    @project: MaxKB
    @file: product_tenant.py
    @desc: 产品×用户矩阵租户上下文（C 端开放面专用）
           令牌由 Chaos 网关签发（django signing / HMAC，共享密钥 PRODUCT_TENANT_SECRET），
           本服务只验证不签发；三层查询矩阵见 docs/project/kb-product-plan-2026-10-09.md：
           L1 按产品查 / L2 产品下按用户查 / L3 超管按 User ID 跨产品查
"""
import time
from dataclasses import dataclass

from django.core import signing
from django.utils.translation import gettext_lazy as _
from rest_framework.authentication import TokenAuthentication

from common.exception.app_exception import AppAuthenticationFailed
from maxkb.const import CONFIG

TENANT_SALT = "kb.product.tenant"
# 角色：user=C端用户(仅自己产品下自己的资料) / product_admin=产品管理员(产品内全部) / super_admin=生态超管(可跨产品)
ROLE_USER = "user"
ROLE_PRODUCT_ADMIN = "product_admin"
ROLE_SUPER_ADMIN = "super_admin"
_ROLES = (ROLE_USER, ROLE_PRODUCT_ADMIN, ROLE_SUPER_ADMIN)


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


def _secret() -> str:
    secret = str(CONFIG.get('PRODUCT_TENANT_SECRET', '') or '')
    if not secret:
        raise AppAuthenticationFailed(1500, _("产品租户上下文未配置（PRODUCT_TENANT_SECRET）"))
    return secret


def issue_product_tenant_token(product_id: str, user_id: str, role: str, expires_seconds: int = 300) -> str:
    """供 Chaos 网关/联调测试签发；生产环境密钥只存于网关与本服务"""
    if role not in _ROLES:
        raise ValueError(f"unknown tenant role: {role}")
    payload = {"p": product_id, "u": user_id, "r": role, "exp": int(time.time()) + expires_seconds}
    return signing.dumps(payload, key=_secret(), salt=TENANT_SALT)


def parse_product_tenant_token(token: str) -> ProductTenantContext:
    try:
        payload = signing.loads(token, key=_secret(), salt=TENANT_SALT)
    except Exception:
        raise AppAuthenticationFailed(1401, _("租户上下文无效"))
    if not isinstance(payload, dict) or int(payload.get('exp', 0)) < time.time():
        raise AppAuthenticationFailed(1401, _("租户上下文已过期"))
    role = payload.get('r', ROLE_USER)
    if role not in _ROLES or not payload.get('p') or not payload.get('u'):
        raise AppAuthenticationFailed(1401, _("租户上下文字段非法"))
    return ProductTenantContext(product_id=payload['p'], user_id=payload['u'], role=role)


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
