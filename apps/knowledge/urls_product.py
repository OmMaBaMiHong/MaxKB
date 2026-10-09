# coding=utf-8
"""产品×用户矩阵租户（C 端开放面）路由。挂载前缀见 urls/web.py 的 product_api_prefix。"""
from django.urls import path

from .views.product_knowledge import ProductKnowledgeOperateView, ProductKnowledgeView

app_name = "product_knowledge"

urlpatterns = [
    path("knowledge", ProductKnowledgeView.as_view()),
    path("knowledge/<str:knowledge_id>", ProductKnowledgeOperateView.as_view()),
]
