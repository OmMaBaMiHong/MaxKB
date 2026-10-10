# coding=utf-8
"""
    @project: MaxKB
    @file: product_document.py
    @desc: 产品×用户矩阵租户（C 端开放面）文档 API。
           遵循复用优先：创建/删除委托 MaxKB 既有管线（DocumentSerializers.Create 的
           段落切分/问题关联/@post 向量化钩子；Operate.delete 的向量/问题/文件清理），
           本层只做租户矩阵校验和参数适配。归属经知识库校验（_knowledge_for）。
"""
from django.utils.translation import gettext_lazy as _
from rest_framework.request import Request
from rest_framework.views import APIView

from common.auth.product_tenant import ProductTenantAuthentication
from common.exception.app_exception import AppApiException
from common import result
from common.handle.tcm_split import tcm_split
from common.utils.split_model import get_split_model
from knowledge.models import Document
from knowledge.serializers.document import DocumentSerializers
from knowledge.views.product_knowledge import _knowledge_for


def _document_for(request: Request, knowledge, document_id: str) -> Document:
    obj = Document.objects.filter(id=document_id, knowledge=knowledge).first()
    if obj is None:
        raise AppApiException(1404, _("文档不存在或无权访问"))
    return obj


def _detail(obj: Document) -> dict:
    return {
        "id": str(obj.id),
        "knowledge_id": str(obj.knowledge_id),
        "name": obj.name,
        "char_length": obj.char_length,
        "status": obj.status,
        "create_time": obj.create_time,
    }


class ProductDocumentView(APIView):
    authentication_classes = [ProductTenantAuthentication]

    def get(self, request: Request, knowledge_id: str):
        knowledge = _knowledge_for(request, knowledge_id)
        rows = Document.objects.filter(knowledge=knowledge).order_by("-create_time")[:200]
        return result.success([_detail(d) for d in rows])

    def post(self, request: Request, knowledge_id: str):
        knowledge = _knowledge_for(request, knowledge_id)
        payload = request.data or {}
        name = str(payload.get("name") or "").strip()
        content = str(payload.get("content") or "")
        if not name:
            raise AppApiException(500, _("文档名称不能为空"))
        raw_paragraphs = payload.get("paragraphs")
        if not content.strip() and not (isinstance(raw_paragraphs, list) and raw_paragraphs):
            raise AppApiException(500, _("文档内容不能为空"))
        # MaxKB 的 @post 钩子在创建后会触发向量化，模型未绑定时会抛错——前置拦截给出明确指引
        if knowledge.embedding_model_id is None:
            raise AppApiException(400, _("该知识库尚未绑定向量化模型，请先绑定模型再上传文档"))
        # 预切分直灌（对接已拆完的内容，如 Skoob 章节）：paragraphs=[{title,content}] 原样过管线，
        # 不做二次切分；每段 title 即证据标题（如 "第12章 章节名"）。上限 2000 段防滥用。
        if isinstance(raw_paragraphs, list) and raw_paragraphs:
            if len(raw_paragraphs) > 2000:
                raise AppApiException(500, _("单文档段落上限 2000，请按卷拆分文档"))
            paragraphs = []
            for item in raw_paragraphs:
                if not isinstance(item, dict):
                    continue
                piece_content = str(item.get("content") or "").strip()
                if not piece_content:
                    continue
                paragraphs.append({
                    "title": str(item.get("title") or "")[:256],
                    "content": piece_content[:102400],
                })
            if not paragraphs:
                raise AppApiException(500, _("paragraphs 内没有有效内容"))
        else:
            # 领域切分（M2）：split.mode=tcm 走中医条文/方剂切分模板，块标题携带 书名·卷·篇·条号
            split = payload.get("split") or {}
            if isinstance(split, dict) and split.get("mode") == "tcm":
                paragraphs = tcm_split(
                    content,
                    book=str(split.get("book") or name)[:64],
                    juan=str(split.get("juan") or ""),
                    pian=str(split.get("pian") or ""),
                )
            else:
                paragraphs = get_split_model("web.md").parse(content)
        # 委托既有管线：段落切分、问题关联、@post 向量化（celery 异步）。
        # 注意：@post 装饰后 save() 返回单个 detail dict；且本函数不得再用 `_` 作解包名（会遮蔽 gettext 的 `_`）
        detail = DocumentSerializers.Create(
            data={"knowledge_id": str(knowledge.id)}
        ).save(instance={"name": name[:150], "paragraphs": paragraphs})
        return result.success(detail)


class ProductDocumentOperateView(APIView):
    authentication_classes = [ProductTenantAuthentication]

    def get(self, request: Request, knowledge_id: str, document_id: str):
        knowledge = _knowledge_for(request, knowledge_id)
        obj = _document_for(request, knowledge, document_id)
        return result.success(_detail(obj))

    def put(self, request: Request, knowledge_id: str, document_id: str):
        knowledge = _knowledge_for(request, knowledge_id)
        obj = _document_for(request, knowledge, document_id)
        payload = request.data or {}
        if "name" in payload:
            name = str(payload.get("name") or "").strip()
            if not name:
                raise AppApiException(500, _("文档名称不能为空"))
            obj.name = name[:150]
        obj.save()
        return result.success(_detail(obj))

    def delete(self, request: Request, knowledge_id: str, document_id: str):
        knowledge = _knowledge_for(request, knowledge_id)
        _document_for(request, knowledge, document_id)
        # 委托既有删除管线：段落/问题关联/向量索引/文件 一并清理
        DocumentSerializers.Operate(
            data={"knowledge_id": str(knowledge.id), "document_id": document_id}
        ).delete()
        return result.success(True)
