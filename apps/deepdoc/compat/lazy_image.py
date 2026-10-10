# 吸收自 RAGFlow v0.27.2 rag/utils/lazy_image.py 与 rag/nlp/__init__.py concat_img
# （Apache-2.0，InfiniFlow Authors）；去除对 rag.nlp 的反向依赖，concat_img 就地合并。
import logging
from io import BytesIO

from PIL import Image


def concat_img(img1, img2):
    if img1 is img2:
        return img1
    if (img1 is None or isinstance(img1, LazyImage)) and (img2 is None or isinstance(img2, LazyImage)):
        if img1 and not img2:
            return img1
        if not img1 and img2:
            return img2
        if not img1 and not img2:
            return None
        return LazyImage.merge(img1, img2)

    img1 = ensure_pil_image(img1) or img1
    img2 = ensure_pil_image(img2) or img2
    if not img1:
        return img2
    if not img2:
        return img1
    if img1 is img2:
        return img1
    if isinstance(img1, Image.Image) and isinstance(img2, Image.Image):
        if img1.tobytes() == img2.tobytes():
            return img1
    width1, height1 = img1.size
    width2, height2 = img2.size
    new_image = Image.new("RGB", (max(width1, width2), height1 + height2))
    new_image.paste(img1, (0, 0))
    new_image.paste(img2, (0, height1))
    return new_image


class LazyImage:
    def __init__(self, blobs, source=None):
        self._blobs = [b for b in (blobs or []) if b]
        self.source = source
        self._pil = None

    def __bool__(self):
        return bool(self._blobs)

    def to_pil(self):
        if self._pil is not None:
            try:
                self._pil.load()
                return self._pil
            except Exception:
                try:
                    self._pil.close()
                except Exception:
                    pass
                self._pil = None
        res_img = None
        for blob in self._blobs:
            try:
                image = Image.open(BytesIO(blob)).convert("RGB")
            except Exception as e:
                logging.info(f"LazyImage: skip bad image blob: {e}")
                continue
            if res_img is None:
                res_img = image
                continue
            new_img = concat_img(res_img, image)
            if new_img is not res_img:
                try:
                    res_img.close()
                except Exception:
                    pass
            try:
                image.close()
            except Exception:
                pass
            res_img = new_img
        self._pil = res_img
        return self._pil

    def to_pil_detached(self):
        pil = self.to_pil()
        self._pil = None
        return pil

    def close(self):
        if self._pil is not None:
            try:
                self._pil.close()
            except Exception:
                pass
            self._pil = None
        return None

    def __getattr__(self, name):
        if name in ("_pil", "_blobs", "source"):
            raise AttributeError(name)
        return getattr(self.to_pil(), name)

    @staticmethod
    def merge(img1, img2):
        blobs = list(getattr(img1, "_blobs", [])) + list(getattr(img2, "_blobs", []))
        return LazyImage(blobs, source=getattr(img1, "source", None) or getattr(img2, "source", None))


def open_image_for_processing(img, allow_bytes=False):
    if isinstance(img, Image.Image):
        return img, False
    if isinstance(img, LazyImage):
        return img.to_pil_detached(), True
    if allow_bytes and isinstance(img, (bytes, bytearray)):
        try:
            pil = Image.open(BytesIO(img)).convert("RGB")
            return pil, True
        except Exception as e:
            logging.info(f"open_image_for_processing: bad bytes: {e}")
            return None, False
    return img, False


def ensure_pil_image(img, allow_bytes=False):
    """上游语义：把任意输入规范成 PIL Image，返回 (pil, 是否来自 LazyImage)。"""
    if isinstance(img, Image.Image):
        return img, False
    if isinstance(img, LazyImage):
        return img.to_pil_detached(), True
    if allow_bytes and isinstance(img, (bytes, bytearray)):
        try:
            pil = Image.open(BytesIO(img)).convert("RGB")
            return pil, True
        except Exception as e:
            logging.info(f"ensure_pil_image: bad bytes: {e}")
            return None, False
    return img, False
