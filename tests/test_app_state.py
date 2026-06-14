from complexity_lab.app_state import GlobalContext


def test_global_context_query_round_trip():
    context = GlobalContext(
        year_start=2018,
        year_end=2025,
        states=("KA", "MH"),
        fuels=("EV", "CNG"),
        oems=("TATA MOTORS",),
        source="vahan",
        coverage="complete",
    )

    restored = GlobalContext.from_query_params(
        context.to_query_params(),
        min_year=2012,
        max_year=2026,
        default_end=2025,
    )

    assert restored == context
    assert restored.to_payload()["states"] == ["KA", "MH"]


def test_global_context_sanitizes_invalid_url_values():
    context = GlobalContext.from_query_params(
        {"from": "bad", "to": "2040", "coverage": "wishful"},
        min_year=2012,
        max_year=2026,
        default_end=2025,
    )

    assert context.year_start == 2012
    assert context.year_end == 2026
    assert context.coverage == "complete"
