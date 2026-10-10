# coding=utf-8
"""
    @project: MaxKB
    @file: admin_graph.py
    @desc: 管理端知识图谱视图（M3）：登录管理员读图/触发建图。
           与产品面（product_graph.py，租户 JWT）共用 graph_extract 服务。
"""
from django.utils.translation import gettext_lazy as _
from rest_framework.request import Request
from rest_framework.views import APIView

from common.auth import TokenAuth
from common import result
from knowledge.graph_extract import build_graph_for_knowledge, get_graph
from knowledge.models import Knowledge


class GraphView(APIView):
    authentication_classes = [TokenAuth]

    def get(self, request: Request, knowledge_id: str):
        knowledge = Knowledge.objects.filter(id=knowledge_id).first()
        if knowledge is None:
            return result.success({"nodes": [], "edges": []})
        try:
            limit_nodes = int(request.query_params.get("limit_nodes") or 300)
        except (TypeError, ValueError):
            limit_nodes = 300
        return result.success(get_graph(knowledge, limit_nodes=max(10, min(limit_nodes, 1000))))


class GraphBuildView(APIView):
    authentication_classes = [TokenAuth]

    def post(self, request: Request, knowledge_id: str):
        knowledge = Knowledge.objects.filter(id=knowledge_id).first()
        if knowledge is None:
            return result.success({"nodes_added": 0, "edges_added": 0})
        try:
            limit = int((request.data or {}).get("limit") or 40)
        except (TypeError, ValueError):
            limit = 40
        return result.success(build_graph_for_knowledge(knowledge, limit=max(1, min(limit, 500))))
