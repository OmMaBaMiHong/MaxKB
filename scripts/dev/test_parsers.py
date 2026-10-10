"""M2 解析 handler 直测：图片 OCR / 扫描 PDF 回退 / PPTX 文本。

用法：仓库根目录 `uv run python scripts/dev/test_parsers.py`
前置：models/deepdoc 权重已就位（PROVENANCE 台账）。
"""
import io
import sys

sys.path.insert(0, "apps")
os_ = __import__("os")
os_.environ.setdefault("DJANGO_SETTINGS_MODULE", "maxkb.settings")
import django  # noqa: E402

django.setup()

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + ("  | " + str(detail)[:120] if detail else ""))


class FakeFile:
    def __init__(self, name: str, data: bytes):
        self.name = name
        self._data = data

    def read(self):
        return self._data

    def chunks(self):
        yield self._data

    def seek(self, pos):
        return None

    @property
    def size(self):
        return len(self._data)


FONT = ImageFont.truetype("/System/Library/Fonts/Supplemental/Songti.ttc", 28)


def render_text_image(lines):
    img = Image.new("RGB", (720, 40 * len(lines) + 40), "white")
    d = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        d.text((20, 20 + 40 * i), line, font=FONT, fill="black")
    return img


get_buffer = lambda f: f.read()

# ── 1. 图片 OCR ──
from common.handle.impl.text.image_split_handle import ImageSplitHandle  # noqa: E402

img = render_text_image(["桂枝汤主治风寒表虚证", "组成：桂枝 芍药 生姜 大枣"])
buf = io.BytesIO()
img.save(buf, format="PNG")
result = ImageSplitHandle().handle(FakeFile("方剂.png", buf.getvalue()), None, False, 4096, get_buffer, lambda *a: None)
text = "".join(p.get("content", "") for p in result.get("content", []))
check("1 图片 OCR", "桂枝汤" in text, text[:60])

# ── 2. 扫描 PDF（整页为图，无文本层）→ PdfSplitHandle OCR 回退 ──
from common.handle.impl.text.pdf_split_handle import PdfSplitHandle
from common.handle.impl.text.pptx_split_handle import PptxSplitHandle  # noqa: E402

buf = io.BytesIO()
img.save(buf, format="PDF")
result = PdfSplitHandle().handle(FakeFile("扫描件.pdf", buf.getvalue()), None, False, 4096, get_buffer, lambda *a: None)
text = "".join(p.get("content", "") for p in result.get("content", []))
check("2 扫描 PDF OCR 回退", "桂枝汤" in text, text[:60])

# ── 3. PPTX ──
from pptx import Presentation  # noqa: E402

prs = Presentation()
slide = prs.slides.add_slide(prs.slide_layouts[1])
slide.shapes.title.text = "中医方剂学"
slide.placeholders[1].text = "桂枝汤：解肌发表，调和营卫"
notes = slide.notes_slide
notes.notes_text_frame.text = "课堂提示：强调营卫不和的病机"
buf = io.BytesIO()
prs.save(buf)
result = PptxSplitHandle().handle(FakeFile("方剂课件.pptx", buf.getvalue()), None, False, 4096, get_buffer, lambda *a: None)
text = "".join(p.get("content", "") for p in result.get("content", []))
check("3 PPTX 文本", "中医方剂学" in text and "调和营卫" in text and "课堂提示" in text, text[:80])

fails = [x for x in results if not x[1]]
print(f"\n==== PARSER TEST {len(results) - len(fails)}/{len(results)} PASS ====")
sys.exit(1 if fails else 0)
