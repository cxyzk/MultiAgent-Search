"""文档切分器：按行聚合切块，块间保留重叠（防止答案正好卡在切割线上）。"""


def _hard_split(text: str, size: int) -> list[str]:
    """超长单段硬切"""
    return [text[i:i + size] for i in range(0, len(text), size)]


def split_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """先按行拆开，再贪心聚合到接近 chunk_size；相邻块保留 overlap 字符重叠"""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    chunks: list[str] = []
    buf = ""
    for line in lines:
        parts = _hard_split(line, chunk_size) if len(line) > chunk_size else [line]
        for part in parts:
            if not buf:
                buf = part
            elif len(buf) + len(part) + 1 <= chunk_size:
                buf += "\n" + part
            else:
                chunks.append(buf)
                tail = buf[-overlap:] if overlap > 0 else ""
                buf = f"{tail}\n{part}" if tail else part
    if buf:
        chunks.append(buf)
    return chunks
