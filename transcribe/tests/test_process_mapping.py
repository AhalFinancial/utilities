from transcribe.summaries.process_mapping import validate_process_mapping_json


def test_process_mapping_schema_validation():
    process_json = {
        "process": {
            "name": "Order Intake",
            "trigger": "New order received",
            "inputs": ["Order form"],
            "outputs": ["Confirmed order"],
            "roles": ["Sales"],
            "systems": ["CRM"],
            "decisions": [{"text": "Use CRM workflow", "source": "transcript"}],
            "pain_points": [{"text": "Manual data entry", "source": "context"}],
            "risks_controls": [{"text": "Duplicate orders", "source": "transcript"}],
            "metrics": [{"text": "Order cycle time", "source": "context"}],
            "open_questions": [{"text": "When to escalate?", "source": "transcript"}],
        },
        "steps": [
            {
                "id": "1",
                "name": "Receive order",
                "description": "Sales receives an order",
                "owner": "Sales",
                "system": "CRM",
                "inputs": ["Order form"],
                "outputs": ["Order logged"],
                "source": "transcript",
                "branches": [{"if": "order incomplete", "then": "request missing info", "source": "transcript"}],
            }
        ],
    }
    validate_process_mapping_json(process_json)
