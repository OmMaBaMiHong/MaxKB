# coding=utf-8
"""
    图片解析 handler（M2，DeepDoc OCR）：png/jpg/jpeg/bmp/webp → 版面 OCR 文本。
    文本行按 OCR 返回顺序（自上而下）拼接，交给上游 SplitModel 切段。
"""
from typing import List

import cv2
import numpy as np

from common.handle.base_split_handle import BaseSplitHandle
from common.handle.impl.text.deepdoc_ocr import get_ocr
from common.handle.impl.text.pdf_split_handle import default_pattern_list
from common.utils.split_model import SplitModel

_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp", ".webp")


class ImageSplitHandle(BaseSplitHandle):
    def support(self, file, get_buffer):
        file_name: str = file.name.lower()
        return file_name.endswith(_SUFFIXES)

    def handle(self, file, pattern_list: List, with_filter: bool, limit: int, get_buffer, save_image):
        content = self.get_content(file, save_image)
        if pattern_list is not None and len(pattern_list) > 0:
            split_model = SplitModel(pattern_list, with_filter, limit)
        else:
            split_model = SplitModel(default_pattern_list, with_filter=with_filter, limit=limit)
        return {"name": file.name, "content": split_model.parse(content)}

    def get_content(self, file, save_image):
        from common.handle.impl.text.deepdoc_ocr import ocr_to_text

        file.seek(0)
        buffer = file.read()
        image = cv2.imdecode(np.frombuffer(buffer, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return ""
        from common.handle.impl.text.deepdoc_ocr import ocr_to_text

        return ocr_to_text(image)
