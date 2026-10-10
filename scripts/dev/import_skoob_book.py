"""Skoob 书籍 → 混沌海 迁移（预切分直灌演示）。

读 skoob 仓 books/<slug>/（book.json + chapters/*.md + story/**/*.md），
经产品租户 API 以 paragraphs 预切分模式灌入：
  - 一个知识库「skoob·<书名>」
  - 「正文」文档：每章一个段落，title="第N章 标题"
  - 「设定集」文档：story/**/*.md 每文件一个段落，title=相对路径

用法：仓库根目录 `uv run python scripts/dev/import_skoob_book.py <skoob书籍目录名>`
前置：web(8080) 已启动；maxkb_dev 已建 Qwen3 模型记录（自动绑定）。
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, "apps")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "maxkb.settings")
import django  # noqa: E402

django.setup()

import httpx  # noqa: E402

from common.auth.product_tenant import issue_product_tenant_token  # noqa: E402
from knowledge.models import Knowledge, Embedding  # noqa: E402
from models_provider.models import Model  # noqa: E402

SKOOB_BOOKS = Path(os.environ.get("SKOOB_BOOKS_DIR", "/Users/wade/work-space/skoob/books"))
BASE = "http://127.0.0.1:8080/product-api/api"
P, U = "pilot-gmoney", "u1001"

book_dir = SKOOB_BOOKS / (sys.argv[1] if len(sys.argv) > 1 else "觉醒-s级寝管-开局十万张床")
meta = json.loads((book_dir / "book.json").read_text(encoding="utf-8"))
book_title = meta.get("title") or book_dir.name
print(f"源书: {book_title} ({book_dir.name})")

token = issue_product_tenant_token(P, U, "user")
headers = {"Authorization": f"Bearer {token}"}
client = httpx.Client(base_url=BASE, timeout=120)

# 1. 建知识库并绑 Qwen3
r = client.post("/knowledge", json={"name": f"skoob·{book_title}"[:150]}, headers=headers)
kid = r.json()["data"]["id"]
qwen = Model.objects.get(name="Qwen3-Embedding-0.6B", model_type="EMBEDDING")
Knowledge.objects.filter(id=kid).update(embedding_model_id=qwen.id)
print("知识库已建:", kid)

# 2. 正文：每章一个段落（预切分直灌）
chapters = []
for md in sorted((book_dir / "chapters").glob("*.md")):
    stem = md.stem  # 形如 0001_凌晨三点，十万张床同时翻身
    num, _, title = stem.partition("_")
    chapters.append({"title": f"第{int(num)}章 {title}", "content": md.read_text(encoding="utf-8")})
print(f"正文章节: {len(chapters)} 章, 总字数 {sum(len(c['content']) for c in chapters)}")

r = client.post(f"/knowledge/{kid}/documents", json={"name": f"{book_title}·正文", "paragraphs": chapters}, headers=headers)
assert r.json().get("code") == 200, r.text[:300]
doc_main = r.json()["data"]["id"]
print("正文文档已入库:", doc_main)

# 3. 设定集：story/**/*.md 每文件一个段落
story_parts = []
for md in sorted((book_dir / "story").rglob("*.md")):
    rel = md.relative_to(book_dir / "story").as_posix()
    text = md.read_text(encoding="utf-8").strip()
    if not text:
        continue
    story_parts.append({"title": f"设定·{rel}", "content": text[:102400]})
if story_parts:
    r = client.post(f"/knowledge/{kid}/documents", json={"name": f"{book_title}·设定集", "paragraphs": story_parts[:2000]}, headers=headers)
    assert r.json().get("code") == 200, r.text[:300]
    print(f"设定集已入库: {len(story_parts)} 个文件")

# 4. 等待向量化完成
expected = len(chapters) + len(story_parts)
for _ in range(180):
    emb = Embedding.objects.filter(knowledge_id=kid, is_active=True).count()
    if emb >= expected:
        break
    time.sleep(2)
print(f"向量化: {emb}/{expected} 段完成")
print(f"知识库 id: {kid}")
