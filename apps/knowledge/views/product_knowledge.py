# coding=utf-8
"""
    @project: MaxKB
    @file: product_knowledge.py
    @desc: 产品×用户矩阵租户（C 端开放面）知识库 API。
           与 B 端 workspace 管理面完全隔离：认证走 ProductTenantAuthentication
           （Chaos 网关签发的租户上下文），查询/写入按 knowledge_filters() 三层矩阵过滤；
           B 端的角色/权限机器在本面不生效。 Chaos 网关以 /open/v1/knowledge/* 代理本面前缀。
"""
from django.utils.translation import gettext_lazy as _
from rest_framework.request import Request
from rest_framework.views import APIView

from common.auth.product_tenant import ProductTenantAuthentication
from common.exception.app_exception import AppApiException
from common import result
from knowledge.models import Knowledge


def _tenant_queryset(request: Request):
    """三层矩阵 → 过滤条件。C 端永远双过滤；product_admin 默认产品内全量；
    super_admin 全量，可用 ?owner_user_id= 收敛到某个用户（跨产品）。"""
    ctx = request.product_tenant
    return Knowledge.objects.filter(
        **ctx.knowledge_filters(owner_user_id=request.query_params.get("owner_user_id"))
    )


def _knowledge_for(request: Request, knowledge_id: str) -> Knowledge:
    """按租户矩阵取知识库；不存在或越权一律 404（不暴露存在性）。"""
    ctx = request.product_tenant
    obj = Knowledge.objects.filter(
        id=knowledge_id,
        **ctx.knowledge_filters(owner_user_id=request.query_params.get("owner_user_id")),
    ).first()
    if obj is None:
        raise AppApiException(1404, _("知识库不存在或无权访问"))
    return obj


def _detail(obj: Knowledge) -> dict:
    return {
        "id": str(obj.id),
        "name": obj.name,
        "desc": obj.desc,
        "workspace_id": obj.workspace_id,
        "owner_user_id": obj.owner_user_id,
        "create_time": obj.create_time,
    }


class ProductKnowledgeView(APIView):
    authentication_classes = [ProductTenantAuthentication]

    def get(self, request: Request):
        rows = _tenant_queryset(request).order_by("-create_time")
        return result.success([_detail(k) for k in rows[:200]])

    def post(self, request: Request):
        ctx = request.product_tenant
        payload = request.data or {}
        name = str(payload.get("name") or "").strip()
        if not name:
            raise AppApiException(500, _("知识库名称不能为空"))
        knowledge = Knowledge.objects.create(
            name=name[:150],
            desc=str(payload.get("desc") or "")[:256],
            # 归属由已验证上下文决定，请求体传什么都不作数
            workspace_id=ctx.product_id,
            owner_user_id=ctx.user_id,
        )
        return result.success(_detail(knowledge))


class ProductKnowledgeOperateView(APIView):
    authentication_classes = [ProductTenantAuthentication]

    def _get(self, request: Request, knowledge_id: str) -> Knowledge:
        return _knowledge_for(request, knowledge_id)

    def get(self, request: Request, knowledge_id: str):
        return result.success(_detail(self._get(request, knowledge_id)))

    def put(self, request: Request, knowledge_id: str):
        obj = self._get(request, knowledge_id)
        payload = request.data or {}
        if "name" in payload:
            name = str(payload.get("name") or "").strip()
            if not name:
                raise AppApiException(500, _("知识库名称不能为空"))
            obj.name = name[:150]
        if "desc" in payload:
            obj.desc = str(payload.get("desc") or "")[:256]
        obj.save()
        return result.success(_detail(obj))

    def delete(self, request: Request, knowledge_id: str):
        obj = self._get(request, knowledge_id)
        detail = _detail(obj)
        obj.delete()
        return result.success(detail)
