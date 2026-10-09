# coding=utf-8
"""
    @project: MaxKB
    @file: product_document.py
    @desc: 产品×用户矩阵租户（C 端开放面）文档 API。
           文档归属经知识库的租户矩阵校验（_knowledge_for），段落为入库试点版切块；
           向量化/索引仍走 MaxKB 既有管线，在本切片中未触发（状态可见，索引 pending）。
"""
from django.utils.translation import gettext_lazy as _
from rest_framework.request import Request
from rest_framework.views import APIView

from common.auth.product_tenant import ProductTenantAuthentication
from common.exception.app_exception import AppApiException
from common import result
from knowledge.models import Document, Paragraph
from knowledge.views.product_knowledge import _knowledge_for

_PARAGRAPH_LIMIT = 4000


def _split_paragraphs(content: str, limit: int = _PARAGRAPH_LIMIT) -> list[str]:
    """入库试点版切块：先按空行聚到 limit，超长段硬切。正式领域切分模板在 M2 接入。"""
    content = content.replace("\r\n", "\n")
    buf, out = "", []
    for block in (b.strip() for b in content.split("\n\n")):
        while len(block) > limit:
            if buf:
                out.append(buf)
                buf = ""
            out.append(block[:limit])
            block = block[limit:]
        if buf and len(buf) + len(block) + 2 > limit:
            out.append(buf)
            buf = block
        else:
            buf = f"{buf}\n\n{block}" if buf else block
    if buf.strip():
        out.append(buf)
    return [b for b in out if b.strip()] or [content[:limit]]


def _document_for(request: Request, knowledge, document_id: str) -> Document:
    obj = Document.objects.filter(id=document_id, knowledge=knowledge).first()
    if obj is None:
        raise AppApiException(1404, _("文档不存在或无权访问"))
    return obj


def _detail(obj: Document, paragraph_count: int | None = None) -> dict:
    data = {
        "id": str(obj.id),
        "knowledge_id": str(obj.knowledge_id),
        "name": obj.name,
        "char_length": obj.char_length,
        "status": obj.status,
        "create_time": obj.create_time,
    }
    if paragraph_count is not None:
        data["paragraph_count"] = paragraph_count
    return data


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
        if not content.strip():
            raise AppApiException(500, _("文档内容不能为空"))
        document = Document.objects.create(
            knowledge=knowledge,
            name=name[:150],
            char_length=len(content),
        )
        paragraphs = _split_paragraphs(content)
        Paragraph.objects.bulk_create(
            Paragraph(document=document, knowledge=knowledge, content=p, title=name[:256], position=i)
            for i, p in enumerate(paragraphs)
        )
        return result.success(_detail(document, paragraph_count=len(paragraphs)))


class ProductDocumentOperateView(APIView):
    authentication_classes = [ProductTenantAuthentication]

    def get(self, request: Request, knowledge_id: str, document_id: str):
        knowledge = _knowledge_for(request, knowledge_id)
        obj = _document_for(request, knowledge, document_id)
        paragraph_count = Paragraph.objects.filter(document=obj).count()
        return result.success(_detail(obj, paragraph_count))

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
        obj = _document_for(request, knowledge, document_id)
        detail = _detail(obj)
        Paragraph.objects.filter(document=obj).delete()
        obj.delete()
        return result.success(detail)
