# coding=utf-8
"""
    @project: MaxKB
    @file: product_search.py
    @desc: 产品×用户矩阵租户（C 端开放面）检索 API。
           复用优先：检索本体完全委托 MaxKB 既有 KnowledgeSerializer.HitTest
           （模型解析 + pgvector embedding/keywords/blend + 段落组装），
           本层只做租户矩阵校验（_knowledge_for）和参数适配。
"""
import uuid as _uuid

from django.utils.translation import gettext_lazy as _
from rest_framework.request import Request
from rest_framework.views import APIView

from common.auth.product_tenant import ProductTenantAuthentication
from common.exception.app_exception import AppApiException
from common import result
from knowledge.serializers.knowledge import KnowledgeSerializer
from knowledge.views.product_knowledge import _knowledge_for

_MODES = ("embedding", "keywords", "blend")


class ProductSearchView(APIView):
    authentication_classes = [ProductTenantAuthentication]

    def post(self, request: Request, knowledge_id: str):
        knowledge = _knowledge_for(request, knowledge_id)
        payload = request.data or {}
        query = str(payload.get("query") or "").strip()
        if not query:
            raise AppApiException(500, _("检索内容不能为空"))
        if knowledge.embedding_model_id is None:
            raise AppApiException(400, _("该知识库尚未绑定向量化模型，请先绑定模型"))
        search_mode = str(payload.get("search_mode") or "blend")
        if search_mode not in _MODES:
            raise AppApiException(500, _("search_mode 仅支持 embedding|keywords|blend"))
        try:
            top_number = max(1, int(payload.get("top_number") or 5))
            similarity = float(payload.get("similarity") if payload.get("similarity") is not None else 0.6)
        except (TypeError, ValueError):
            raise AppApiException(500, _("top_number/similarity 参数非法"))
        # 委托既有检索：模型解析 + pgvector 混合检索 + 段落组装。
        # HitTest 声明 user_id 可选且检索逻辑不使用，产品面以随机 UUID 过字段校验
        data = {
            "workspace_id": knowledge.workspace_id,
            "knowledge_id": str(knowledge.id),
            "user_id": str(_uuid.uuid4()),
            "query_text": query,
            "top_number": top_number,
            "similarity": similarity,
            "search_mode": search_mode,
        }
        return result.success(KnowledgeSerializer.HitTest(data=data).hit_test())
