from transcribe.summaries.process_mapping import render_process_mapping_markdown


def test_process_mapping_markdown_render():
    process_json = {
        "process": {
            "name": "Order Intake",
            "trigger": "New order",
            "inputs": ["Order form"],
            "outputs": ["Confirmed order"],
            "roles": ["Sales"],
            "systems": ["CRM"],
            "decisions": [{"text": "Use CRM workflow", "source": "transcript"}],
            "pain_points": [],
            "risks_controls": [],
            "metrics": [],
            "open_questions": [],
        },
        "steps": [],
    }
    md = render_process_mapping_markdown(process_json)
    assert "Process Mapping" in md
    assert "Order Intake" in md
