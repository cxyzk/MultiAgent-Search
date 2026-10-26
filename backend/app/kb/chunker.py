"""文档切分器：Markdown 结构感知（标题层级 / 代码围栏保护 / 段落聚合 + 重叠）。

与旧版（纯按行聚合）的区别：
- 旧版 `if ln.strip()` 把所有空行过滤掉了 → 代码缩进、段落结构全丢
- 新版保留空行（段落分隔），代码围栏（```）整块成块、不会被腰斩
- 标题更新 heading_path，并强制切开新块（一个块不跨标题）
- 每块正文前带 heading_path 前缀，让 BM25 / 向量检索都能利用层级信息
"""
import re

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")


def _hard_split(text: str, size: int) -> list[str]:
    """超长单段硬切（兜底：正常文档不应触发）"""
    return [text[i:i + size] for i in range(0, len(text), size)]


def split_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """按 Markdown 结构切分，返回带标题前缀的文本块列表。"""
    chunks: list[str] = []
    heading_stack: list[tuple[int, str]] = []   # (level, title)，用来拼 heading_path
    body_lines: list[str] = []                  # 当前块已累积的正文
    body_len = 0
    code_block: list[str] | None = None         # 非 None 表示正在代码围栏内

    def current_heading() -> str:
        # 取最近 3 层做前缀：h1 也要保留（在 HTML / 单节文档里它就是唯一上下文），
        # 但过深的层级截断，避免前缀比正文还长
        titles = [title for _, title in heading_stack]
        return " / ".join(titles[-3:])

    def emit(body: str) -> None:
        """一段正文（带标题前缀）写入 chunks；超长才硬切"""
        if not body.strip():
            return
        prefix = f"## {current_heading()}\n" if current_heading() else ""
        block = prefix + body.strip()
        if len(block) <= chunk_size:
            chunks.append(block)
        else:
            chunks.extend(_hard_split(block, chunk_size))

    def emit_code(lines: list[str]) -> None:
        """代码块整体成块；超长时按行切，并给每块补上成对的围栏"""
        code_text = "\n".join(lines)
        if len(code_text) <= chunk_size:
            chunks.append(code_text)
            return

        fence = lines[0]                       # 开头围栏（可能带语言标记）
        body = lines[1:-1] if len(lines) > 1 and _FENCE_RE.match(lines[-1]) else lines[1:]
        current: list[str] = []
        size = len(fence) + 4                  # 预留闭合围栏的空间
        for line in body:
            if size + len(line) + 1 > chunk_size and current:
                chunks.append(fence + "\n" + "\n".join(current) + "\n```")
                current = []
                size = len(fence) + 4
            current.append(line)
            size += len(line) + 1
        if current:
            chunks.append(fence + "\n" + "\n".join(current) + "\n```")

    def flush_body(keep_tail: bool = True) -> None:
        """结束当前正文块。

        keep_tail=True 只在"正文超长、要续切"时用——留最后一行给下一块做重叠。
        遇到标题 / 代码围栏 / 文档结束时传 False：这些是硬边界，tail 会变成重复内容。
        """
        nonlocal body_lines, body_len
        if not body_lines:
            return
        text_so_far = "\n".join(body_lines)
        emit(text_so_far)
        lines = [ln for ln in text_so_far.splitlines() if ln.strip()]
        tail = lines[-1] if (keep_tail and overlap > 0 and lines) else ""
        body_lines = [tail] if tail else []
        body_len = len(tail)

    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        # ① 代码围栏：整块收集，不参与正文聚合
        if _FENCE_RE.match(line):
            if code_block is None:
                flush_body(keep_tail=False)   # 代码围栏是硬边界，不重叠
                code_block = [line]
            else:
                code_block.append(line)
                emit_code(code_block)        # 代码块整体成块（超长时按行切 + 补围栏）
                code_block = None
            continue
        if code_block is not None:
            code_block.append(line)
            continue

        # ② 标题：更新层级，并强制切开当前块（块不跨标题）
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            flush_body(keep_tail=False)       # 标题是硬边界，不重叠
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()          # 弹掉同级和更深的旧标题
            heading_stack.append((level, title))
            continue

        # ③ 空行：保留为段落分隔（不参与长度计算）
        if not line.strip():
            if body_lines and body_lines[-1] != "":
                body_lines.append("")
            continue

        # ④ 普通正文：累计到 chunk_size 就切
        body_lines.append(line)
        body_len += len(line) + 1
        if body_len >= chunk_size:
            flush_body()

    # 收尾：未闭合的代码块 + 剩余正文
    if code_block is not None:
        emit_code(code_block)
    flush_body(keep_tail=False)
    return chunks
