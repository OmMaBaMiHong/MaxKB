# coding=utf-8
"""
    中医典籍切分模板（M2 领域适配）：以"条文 / 一张方"为切分单元，
    每块携带 书名·卷·篇·条号（或方名）元数据进标题，供证据引用渲染。

    识别规则（按行扫描，优先级从上到下）：
      1. 篇/卷头：`辨X病脉证并治` / `卷N` / `第N篇` —— 更新当前篇上下文，另起一块
      2. 方剂：行首出现 `X汤|丸|散|膏|丹|饮` 且带 `：` 或组成字样 —— 另起一张方
      3. 条文：行首编号 `12.` / `十二、` / `第十二条` —— 另起一条
      4. 其余行归入当前块；单块超长（>2000 字）按空行硬切

    输出：[{"title": "伤寒论·辨太阳病脉证并治·桂枝汤", "content": "..."}, ...]
    与 DocumentSerializers.Create 的 paragraphs 字段（title/content）直接对齐。
"""
import re

_PIAN_RE = re.compile(r"^(辨.{1,8}病脉证并治.*|卷[〇一二三四五六七八九十百\d]+.*|第[〇一二三四五六七八九十百\d]+篇.*)$")
_FORMULA_RE = re.compile(r"([\u4e00-\u9fa5]{1,8}(?:汤|丸|散|膏|丹|饮))\s*[:：]")
_ITEM_RE = re.compile(r"^(\d{1,3})[\.、．]\s*")
_TIAO_RE = re.compile(r"^第([〇一二三四五六七八九十百\d]+)条")
_MAX_BLOCK = 2000


def _hard_split(text: str, limit: int = _MAX_BLOCK) -> list:
    """单块超长兜底：按空行聚合到 limit，超长硬切。"""
    buf, out = "", []
    for block in (b.strip() for b in text.replace("\r\n", "\n").split("\n\n")):
        while len(block) > limit:
            if buf:
                out.append(buf)
                buf = ""
            out.append(block[:limit])
            block = block[limit:]
        if buf and len(buf) + len(block) + 1 > limit:
            out.append(buf)
            buf = block
        else:
            buf = f"{buf}\n{block}" if buf else block
    if buf.strip():
        out.append(buf)
    return [b for b in out if b.strip()] or [text[:limit]]


def tcm_split(content: str, book: str = "", juan: str = "", pian: str = "") -> list:
    """中医典籍文本 → 按条文/方剂切分的段落列表。

    :param content: 原文全文
    :param book/juan/pian: 书名/卷/篇 元数据（可由调用方补充默认值）
    :return: [{"title": "书·卷·篇·第N条|方名", "content": "..."}]
    """
    blocks = []
    cur_pian = pian
    cur_kind = None  # 'tiao' | 'fang'
    cur_no = None
    cur_formula = None
    cur_lines = []

    def flush():
        text = "\n".join(cur_lines).strip()
        cur_lines.clear()
        if not text:
            return
        parts = [p for p in (book, juan, cur_pian) if p]
        if cur_kind == "tiao" and cur_no:
            parts.append(f"第{cur_no}条")
        elif cur_kind == "fang" and cur_formula:
            parts.append(cur_formula)
        title = "·".join(parts)
        for piece in _hard_split(text):
            blocks.append({"title": title, "content": piece})

    for raw_line in content.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()

        pian_match = _PIAN_RE.match(line)
        if pian_match and len(line) <= 24:
            flush()
            cur_pian = line
            cur_kind = None
            continue

        formula_match = _FORMULA_RE.match(line)
        if formula_match:
            flush()
            cur_kind = "fang"
            cur_formula = formula_match.group(1)
            cur_lines.append(line)
            continue

        item_match = _ITEM_RE.match(line)
        tiao_match = _TIAO_RE.match(line)
        if item_match or tiao_match:
            flush()
            cur_kind = "tiao"
            cur_no = (item_match or tiao_match).group(1)
            cur_lines.append(line)
            continue

        cur_lines.append(line)

    flush()
    return blocks if blocks else [{"title": book or "", "content": content}]
