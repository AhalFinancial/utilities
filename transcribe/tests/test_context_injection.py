from transcribe.context.selector import build_strategies


def test_context_strategy_costs():
    transcript = "order intake process sales crm"
    sections = [
        ("a", "sales uses crm for orders"),
        ("b", "unrelated marketing notes"),
    ]
    strategies = build_strategies(transcript, sections, top_n=1, char_cap=20)
    assert len(strategies) == 3
    assert strategies[0].estimated_cost_usd > 0
    assert len(strategies[2].text) <= 20
