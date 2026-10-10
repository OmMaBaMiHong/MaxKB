# coding=utf-8
"""
    @project: MaxKB
    @file: product_graph.py
    @desc: 产品×用户矩阵租户（C 端开放面）知识图谱 API（M3）。
           POST /knowledge/<id>/graph/build 触发抽取（同步，demo 规模；生产可转 celery）
           GET  /knowledge/<id>/graph       读图（节点+边，前端渲染用）
           复用优先：图本体委托 graph_extract 服务；本层只做租户矩阵校验。
"""
import uuid as _uuid

from django.utils.translation import gettext_lazy as _
from rest_framework.request import Request
from rest_framework.views import APIView

from common.auth.product_tenant import ProductTenantAuthentication
from common import result
from knowledge.graph_extract import build_graph_for_knowledge, get_graph
from knowledge.views.product_knowledge import _knowledge_for


class ProductGraphBuildView(APIView):
    authentication_classes = [ProductTenantAuthentication]

    def post(self, request: Request, knowledge_id: str):
        knowledge = _knowledge_for(request, knowledge_id)
        try:
            limit = int((request.data or {}).get("limit") or 40)
        except (TypeError, ValueError):
            limit = 40
        limit = max(1, min(limit, 500))
        return result.success(build_graph_for_knowledge(knowledge, limit=limit))


class ProductGraphView(APIView):
    authentication_classes = [ProductTenantAuthentication]

    def get(self, request: Request, knowledge_id: str):
        knowledge = _knowledge_for(request, knowledge_id)
        try:
            limit_nodes = int(request.query_params.get("limit_nodes") or 300)
        except (TypeError, ValueError):
            limit_nodes = 300
        return result.success(get_graph(knowledge, limit_nodes=max(10, min(limit_nodes, 1000))))
