"""文档文本提取：md/txt 直读，pdf 用 pypdf，html 用标准库转 Markdown。

统一输出 Markdown——下游 chunker 是结构感知的（标题层级 / 代码围栏），
所以 HTML 的标题和代码块要转成 Markdown 记号，而不是拍平成纯文本。
"""
import io
from html.parser import HTMLParser

from pypdf import PdfReader

_TEXT_EXTS = {"md", "markdown", "txt", "text"}
_HTML_EXTS = {"html", "htm"}


class _MarkdownExtractor(HTMLParser):
    """HTML → Markdown 的极简提取：标题 / 代码块 / 列表 / 段落，跳过 script/style。"""

    _HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
    _BLOCKS = {"p", "div", "br", "tr", "blockquote", "section", "article"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ("script", "style"):
            self._skip_depth += 1
        elif tag in self._HEADINGS:
            self.parts.append("\n" + "#" * int(tag[1]) + " ")
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag == "pre":
            self.parts.append("\n\n```\n")
        elif tag in self._BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag == "pre":
            self.parts.append("\n```\n\n")
        elif tag in self._HEADINGS or tag in self._BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)


def _decode_text(data: bytes) -> str:
    """常见编码逐个尝试：中文的 txt/html 里有不少 GBK。"""
    for encoding in ("utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _extract_html(data: bytes) -> str:
    parser = _MarkdownExtractor()
    parser.feed(_decode_text(data))
    text = "".join(parser.parts)
    # 压缩连续空行（最多保留一个）
    lines = [line.rstrip() for line in text.splitlines()]
    result: list[str] = []
    for line in lines:
        if line.strip() or (result and result[-1].strip()):
            result.append(line)
    return "\n".join(result).strip()


def _extract_pdf(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text.strip())
    return "\n\n".join(pages)


def extract_text(filename: str, data: bytes) -> str:
    """按扩展名分发；不支持的类型抛 ValueError（接口层转 400）。"""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in _TEXT_EXTS:
        return _decode_text(data)
    if ext in _HTML_EXTS:
        return _extract_html(data)
    if ext == "pdf":
        return _extract_pdf(data)
    raise ValueError(f"不支持的文件类型：.{ext or '未知'}（支持 md / txt / pdf / html）")
