from dataclasses import dataclass
from typing import List, Tuple

from transcribe.summarizer import calculate_cost


@dataclass
class ContextSelection:
    label: str
    text: str
    estimated_cost_usd: float


def _token_estimate(text: str) -> int:
    return max(1, len(text) // 4)


def _estimate_cost(text: str, output_tokens: int = 2048) -> float:
    return calculate_cost(_token_estimate(text), output_tokens)


def _score_relevance(transcript_text: str, section_text: str) -> int:
    t_words = set(transcript_text.lower().split())
    s_words = set(section_text.lower().split())
    return len(t_words & s_words)


def build_strategies(
    transcript_text: str,
    sections: List[Tuple[str, str]],
    top_n: int = 3,
    char_cap: int = 6000,
) -> List[ContextSelection]:
    all_text = "\n\n".join(text for _, text in sections)
    full = ContextSelection("Full context", all_text, _estimate_cost(all_text))

    scored = sorted(
        sections,
        key=lambda s: _score_relevance(transcript_text, s[1]),
        reverse=True,
    )
    top_sections = scored[:top_n]
    top_text = "\n\n".join(text for _, text in top_sections)
    top = ContextSelection("Top-N relevant", top_text, _estimate_cost(top_text))

    capped_chunks = []
    total = 0
    for _, text in scored:
        if total >= char_cap:
            break
        remaining = char_cap - total
        capped_chunks.append(text[:remaining])
        total += len(capped_chunks[-1])
    capped_text = "\n\n".join(capped_chunks)
    capped = ContextSelection("Hard cap", capped_text, _estimate_cost(capped_text))

    return [full, top, capped]


def select_context_strategy(
    transcript_text: str,
    sections: List[Tuple[str, str]],
    choice_index: int,
    top_n: int = 3,
    char_cap: int = 6000,
) -> ContextSelection:
    strategies = build_strategies(transcript_text, sections, top_n=top_n, char_cap=char_cap)
    return strategies[choice_index]
