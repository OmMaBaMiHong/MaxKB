# coding=utf-8
"""
    DeepDoc OCR 单例：混沌海文档解析共用的推理入口。
    模型目录由 CHAOSSEA_DEEPDOC_MODEL_DIR 指定（默认 models/deepdoc，见 PROVENANCE 台账）。
    首次调用加载（~90MB 权重），此后进程内复用。
"""
import os
import threading

from common.utils.logger import maxkb_logger

DEFAULT_MODEL_DIR = os.environ.get("CHAOSSEA_DEEPDOC_MODEL_DIR", "models/deepdoc")
_ocr = None
_lock = threading.Lock()


def get_ocr():
    global _ocr
    if _ocr is None:
        with _lock:
            if _ocr is None:
                from deepdoc.vision.ocr import OCR

                _ocr = OCR(model_dir=DEFAULT_MODEL_DIR)
                maxkb_logger.info(f"DeepDoc OCR 已加载（模型目录 {DEFAULT_MODEL_DIR}）")
    return _ocr


def ocr_to_text(image) -> str:
    """图片 → OCR 文本。OCR 返回扁平交错列表 [四点框, (文本, 置信度), ...]，
    跳过框、按版面顺序拼接文本。"""
    result = get_ocr()(image)
    lines = []
    for item in result or []:
        # 条目 = (四点框, (文本, 置信度))；与上游 pdf_parser 消费模式一致
        if isinstance(item, tuple) and len(item) == 2 and isinstance(item[1], tuple):
            lines.append(item[1][0])
    return "\n".join(lines)
