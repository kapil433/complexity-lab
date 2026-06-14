from complexity_lab.app_state import normalized_year_range


def test_normalized_year_range_rejects_scalar_widget_state():
    assert normalized_year_range(
        2012,
        fallback=(2012, 2025),
        min_year=2012,
        max_year=2026,
    ) == (2012, 2025)


def test_normalized_year_range_clamps_and_orders_values():
    assert normalized_year_range(
        (2040, 2010),
        fallback=(2012, 2025),
        min_year=2012,
        max_year=2026,
    ) == (2012, 2026)
