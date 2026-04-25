from __future__ import annotations

from html import escape, unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

from transcribe.errors import TranscriptionError


def _require_markdown():
    try:
        from markdown import markdown  # type: ignore
    except Exception as exc:  # pragma: no cover - import guard
        raise TranscriptionError(
            "PDF export requires the 'markdown' package.",
            "Install it with: pip install markdown",
        ) from exc
    return markdown


def _require_weasyprint():
    try:
        from weasyprint import HTML  # type: ignore
    except Exception as exc:  # pragma: no cover - import guard
        raise TranscriptionError(
            "PDF export requires WeasyPrint.",
            "Install WeasyPrint and its system dependencies, then retry.",
        ) from exc
    return HTML


def _require_reportlab():
    try:
        from reportlab.lib.pagesizes import letter  # type: ignore
        from reportlab.lib.styles import getSampleStyleSheet  # type: ignore
        from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer  # type: ignore
    except Exception as exc:  # pragma: no cover - import guard
        raise TranscriptionError(
            "PDF export requires WeasyPrint or ReportLab.",
            "Install one with: pip install weasyprint or pip install reportlab",
        ) from exc
    return letter, getSampleStyleSheet, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer


class _HTMLToFlowables(HTMLParser):
    def __init__(self, styles, Paragraph, Spacer, ListFlowable, ListItem):
        super().__init__()
        self._styles = styles
        self._Paragraph = Paragraph
        self._Spacer = Spacer
        self._ListFlowable = ListFlowable
        self._ListItem = ListItem
        self._buffer: list[str] = []
        self._current_tag: Optional[str] = None
        self._list_items: list = []
        self.flowables: list = []

    def handle_starttag(self, tag, attrs):
        if tag in ("h1", "h2", "h3", "p"):
            self._flush_buffer()
            self._current_tag = tag
        elif tag in ("ul", "ol"):
            self._flush_buffer()
            self._list_items = []
        elif tag == "li":
            self._flush_buffer()
            self._current_tag = "li"
        elif tag == "br":
            self._buffer.append("\n")

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3", "p", "li"):
            self._emit_paragraph(tag)
        elif tag in ("ul", "ol"):
            if self._list_items:
                self.flowables.append(self._ListFlowable(self._list_items, bulletType="bullet"))
                self.flowables.append(self._Spacer(1, 6))
            self._list_items = []

    def handle_data(self, data):
        if data:
            self._buffer.append(data)

    def _flush_buffer(self):
        if self._buffer:
            # Preserve text if we encounter unexpected structure
            text = unescape("".join(self._buffer)).strip()
            if text:
                self.flowables.append(self._Paragraph(escape(text), self._styles["BodyText"]))
                self.flowables.append(self._Spacer(1, 6))
            self._buffer = []

    def _emit_paragraph(self, tag):
        text = unescape("".join(self._buffer)).strip()
        self._buffer = []
        if not text:
            return
        if tag == "h1":
            style = self._styles["Heading1"]
        elif tag == "h2":
            style = self._styles["Heading2"]
        elif tag == "h3":
            style = self._styles["Heading3"]
        else:
            style = self._styles["BodyText"]

        para = self._Paragraph(escape(text), style)
        if tag == "li":
            self._list_items.append(self._ListItem(para))
        else:
            self.flowables.append(para)
            self.flowables.append(self._Spacer(1, 6))


def export_markdown_pdf(markdown_text: str, output_path: Path, title: Optional[str] = None) -> Path:
    markdown = _require_markdown()

    html_body = markdown(
        markdown_text,
        extensions=["fenced_code", "tables"],
        output_format="html5",
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc_title = escape(title or "Transcript Export")
    html_doc = (
        "<!doctype html>"
        "<html><head><meta charset=\"utf-8\">"
        f"<title>{doc_title}</title>"
        "</head><body>"
        f"{html_body}"
        "</body></html>"
    )

    try:
        HTML = _require_weasyprint()
        HTML(string=html_doc).write_pdf(str(output_path))
        return output_path
    except TranscriptionError:
        # Fall back to ReportLab when WeasyPrint dependencies are missing.
        pass

    letter, getSampleStyleSheet, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer = _require_reportlab()
    styles = getSampleStyleSheet()
    parser = _HTMLToFlowables(styles, Paragraph, Spacer, ListFlowable, ListItem)
    parser.feed(html_body)
    flowables = parser.flowables or [Paragraph(escape(markdown_text), styles["BodyText"])]
    doc = SimpleDocTemplate(str(output_path), pagesize=letter, title=doc_title)
    doc.build(flowables)
    return output_path
