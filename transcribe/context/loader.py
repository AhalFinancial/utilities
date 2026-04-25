from pathlib import Path
from typing import List, Optional, Tuple


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_dir(path: Path) -> List[Tuple[str, str]]:
    sections = []
    for file in sorted(path.rglob("*")):
        if file.is_file() and file.suffix.lower() in {".md", ".txt"}:
            sections.append((str(file), _read_file(file)))
    return sections


def load_context(
    context_file: Optional[Path],
    context_text: Optional[str],
    context_dir: Optional[Path],
) -> List[Tuple[str, str]]:
    sections: List[Tuple[str, str]] = []
    if context_file:
        sections.append((str(context_file), _read_file(context_file)))
    if context_text:
        sections.append(("inline", context_text))
    if context_dir:
        sections.extend(_load_dir(context_dir))
    return sections
