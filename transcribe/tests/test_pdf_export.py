import importlib.util
from pathlib import Path

import pytest

from transcribe.exporters.pdf import export_markdown_pdf


def test_export_markdown_pdf(tmp_path: Path):
    pytest.importorskip("markdown")
    has_weasyprint = importlib.util.find_spec("weasyprint") is not None
    has_reportlab = importlib.util.find_spec("reportlab") is not None
    if not (has_weasyprint or has_reportlab):
        pytest.skip("No PDF engine available (weasyprint or reportlab).")
    output_path = tmp_path / "sample.pdf"
    pdf_path = export_markdown_pdf("# Title\n\nHello world.\n", output_path, title="Sample")
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0
