import json
from typing import Optional, Tuple, List, Dict, Any

from openai import OpenAI

from transcribe.prompts import get_process_mapping_prompt
from transcribe.errors import ProcessMappingError
from transcribe.retry import api_retry
from transcribe.summarizer import calculate_cost, summarize_long_transcript, split_into_semantic_chunks


def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ProcessMappingError("Model did not return valid JSON.")
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ProcessMappingError("Model returned malformed JSON.") from exc


def _truncate_transcript(transcript_text: str, limit: int = 60000) -> str:
    if len(transcript_text) <= limit:
        return transcript_text
    head = transcript_text[:40000]
    tail = transcript_text[-20000:]
    return f"{head}\n\n...[truncated]...\n\n{tail}"


def _call_process_mapping(
    client: OpenAI,
    system_prompt: str,
    transcript_text: str,
    context_text: Optional[str],
) -> Tuple[str, object]:
    context_block = f"\n\nEXTERNAL CONTEXT:\n{context_text}" if context_text else ""
    response = client.chat.completions.create(
        model="gpt-5.1",
        max_completion_tokens=4096,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"TRANSCRIPT:\n{transcript_text}{context_block}\n\nReturn JSON only.",
            },
        ],
    )
    return response.choices[0].message.content or "", response


def _compress_transcript_for_mapping(transcript_text: str, language: str) -> str:
    summary_text, _in_tokens, _out_tokens, _cost = summarize_long_transcript(
        transcript_text=transcript_text,
        style="detailed",
        language=language or "en",
    )
    return summary_text


def _compress_context_for_mapping(context_text: str, language: str) -> str:
    summary_text, _in_tokens, _out_tokens, _cost = summarize_long_transcript(
        transcript_text=context_text,
        style="detailed",
        language=language or "en",
    )
    return summary_text


def _merge_process_mappings(mappings: List[dict]) -> dict:
    if not mappings:
        return {"process": {}, "steps": []}
    merged: Dict[str, Any] = {"process": {}, "steps": []}

    def _uniq_list(items):
        seen = set()
        out = []
        for item in items:
            key = json.dumps(item, sort_keys=True) if isinstance(item, dict) else str(item)
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    process_keys_list = [
        "inputs",
        "outputs",
        "roles",
        "systems",
        "decisions",
        "pain_points",
        "risks_controls",
        "metrics",
        "open_questions",
    ]

    for mapping in mappings:
        process = mapping.get("process", {})
        for key in ["name", "trigger"]:
            if not merged["process"].get(key) and process.get(key):
                merged["process"][key] = process.get(key)
        for key in process_keys_list:
            existing = merged["process"].get(key, [])
            merged["process"][key] = _uniq_list(existing + (process.get(key) or []))

        for step in mapping.get("steps", []) or []:
            merged["steps"].append(step)

        for key in ["controls", "checkpoints"]:
            if key in mapping:
                existing = merged.get(key, [])
                merged[key] = _uniq_list(existing + (mapping.get(key) or []))

    return merged


@api_retry
def build_process_mapping_json(
    transcript_text: str,
    context_text: Optional[str],
    template: str = "standard",
    language: str = "en",
) -> Tuple[dict, int, int, float]:
    client = OpenAI()
    system_prompt = get_process_mapping_prompt(template, language)
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0.0

    estimated_tokens = len(transcript_text) // 4
    context_tokens = len(context_text) // 4 if context_text else 0
    chunk_threshold = 2000 if template != "standard" else 4000
    if estimated_tokens > chunk_threshold:
        context_for_chunks = context_text
        if context_tokens > 2000:
            context_for_chunks = _compress_context_for_mapping(context_text, language)
        chunks = split_into_semantic_chunks(transcript_text, max_tokens=4000)
        mappings = []
        for chunk in chunks:
            raw, response = _call_process_mapping(client, system_prompt, chunk, context_for_chunks)
            choice = response.choices[0]
            if not raw.strip():
                finish_reason = getattr(choice, "finish_reason", None) or "unknown"
                if finish_reason == "length":
                    condensed = _compress_transcript_for_mapping(chunk, language)
                    raw, response = _call_process_mapping(
                        client, system_prompt, condensed, context_for_chunks
                    )
                    choice = response.choices[0]
                if not raw.strip():
                    finish_reason = getattr(choice, "finish_reason", None) or "unknown"
                    raise ProcessMappingError(
                        f"Empty response from model (finish_reason={finish_reason})."
                    )
            mappings.append(_extract_json(raw))
            usage = response.usage
            total_input_tokens += usage.prompt_tokens
            total_output_tokens += usage.completion_tokens
            total_cost += calculate_cost(usage.prompt_tokens, usage.completion_tokens)

        merged = _merge_process_mappings(mappings)
        return merged, total_input_tokens, total_output_tokens, total_cost

    raw, response = _call_process_mapping(client, system_prompt, transcript_text, context_text)
    choice = response.choices[0]
    if not raw.strip():
        finish_reason = getattr(choice, "finish_reason", None) or "unknown"
        if finish_reason == "length":
            condensed = _compress_transcript_for_mapping(transcript_text, language)
            raw, response = _call_process_mapping(client, system_prompt, condensed, context_text)
            choice = response.choices[0]
            if not raw.strip():
                finish_reason = getattr(choice, "finish_reason", None) or "unknown"
                raise ProcessMappingError(
                    f"Empty response from model (finish_reason={finish_reason})."
                )
        else:
            raise ProcessMappingError(f"Empty response from model (finish_reason={finish_reason}).")

    usage = response.usage
    input_tokens = usage.prompt_tokens
    output_tokens = usage.completion_tokens
    cost_usd = calculate_cost(input_tokens, output_tokens)
    return _extract_json(raw), input_tokens, output_tokens, cost_usd


def validate_process_mapping_json(process_json: dict) -> None:
    if "process" not in process_json or "steps" not in process_json:
        raise ValueError("process and steps are required")
    required_process_keys = [
        "name",
        "trigger",
        "inputs",
        "outputs",
        "roles",
        "systems",
        "decisions",
        "pain_points",
        "risks_controls",
        "metrics",
        "open_questions",
    ]
    process_block = process_json["process"]
    for key in required_process_keys:
        if key not in process_block:
            raise ValueError(f"process missing {key}")

    sourced_lists = [
        "decisions",
        "pain_points",
        "risks_controls",
        "metrics",
        "open_questions",
    ]
    for key in sourced_lists:
        items = process_block.get(key) or []
        if not isinstance(items, list):
            raise ValueError(f"process {key} must be a list")
        for item in items:
            if isinstance(item, dict):
                if "source" not in item:
                    raise ValueError(f"process {key} item missing source")
            else:
                raise ValueError(f"process {key} items must be objects")

    for step in process_json["steps"]:
        required_step_keys = [
            "id",
            "name",
            "description",
            "owner",
            "system",
            "inputs",
            "outputs",
            "source",
            "branches",
        ]
        for key in required_step_keys:
            if key not in step:
                raise ValueError(f"step missing {key}")
        branches = step.get("branches") or []
        if not isinstance(branches, list):
            raise ValueError("branches must be a list")
        for b in branches:
            if "if" not in b or "then" not in b or "source" not in b:
                raise ValueError("branch missing if/then/source")


def render_process_mapping_markdown(process_json: dict) -> str:
    validate_process_mapping_json(process_json)
    lines = []
    process = process_json.get("process", {})

    def _line(label: str, value: str):
        if value:
            lines.append(f"**{label}:** {value}")

    def _list_to_text(items):
        if not items:
            return ""
        normalized = []
        for item in items:
            if isinstance(item, dict):
                text = item.get("text") or item.get("name") or item.get("value")
                normalized.append(text if text is not None else json.dumps(item))
            else:
                normalized.append(str(item))
        return ", ".join(normalized)

    lines.append("# Process Mapping")
    lines.append("")
    _line("Process", process.get("name", ""))
    _line("Trigger", process.get("trigger", ""))
    _line("Inputs", _list_to_text(process.get("inputs", []) or []))
    _line("Outputs", _list_to_text(process.get("outputs", []) or []))
    _line("Roles", _list_to_text(process.get("roles", []) or []))
    _line("Systems", _list_to_text(process.get("systems", []) or []))
    lines.append("")

    def _section(title: str, items):
        if not items:
            return
        lines.append(f"## {title}")
        lines.append("")
        for item in items:
            if isinstance(item, dict):
                text = item.get("text") or item.get("name") or ""
                source = item.get("source")
                suffix = f" _(source: {source})_" if source else ""
                lines.append(f"- {text}{suffix}")
            else:
                lines.append(f"- {item}")
        lines.append("")

    _section("Decisions", process.get("decisions"))
    _section("Pain Points", process.get("pain_points"))
    _section("Risks and Controls", process.get("risks_controls"))
    _section("Metrics", process.get("metrics"))
    _section("Open Questions", process.get("open_questions"))

    steps = process_json.get("steps") or []
    if steps:
        lines.append("## Steps")
        lines.append("")
        for step in steps:
            name = step.get("name", "Step")
            source = step.get("source")
            suffix = f" _(source: {source})_" if source else ""
            lines.append(f"### {name}{suffix}")
            desc = step.get("description")
            if desc:
                lines.append(desc)
            branches = step.get("branches") or []
            if branches:
                lines.append("")
                lines.append("**Branches:**")
                for b in branches:
                    condition = b.get("if")
                    then = b.get("then")
                    bsource = b.get("source")
                    b_suffix = f" _(source: {bsource})_" if bsource else ""
                    lines.append(f"- If {condition} then {then}{b_suffix}")
            lines.append("")

    return "\n".join(lines).strip() + "\n"
