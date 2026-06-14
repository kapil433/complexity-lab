from complexity_lab.persistence import (
    add_watchlist_item,
    list_research_items,
    list_saved_views,
    list_watchlist,
    save_research_item,
    save_view,
)


def test_saved_view_round_trip(tmp_path):
    path = tmp_path / "research.duckdb"
    view_id = save_view(
        title="EV leaders",
        page="Market Brief",
        payload={"states": ["KA"], "year_end": 2025},
        data_cutoff="April 2026",
        notes="Track quarterly.",
        path=path,
    )

    saved = list_saved_views(path)

    assert saved.loc[0, "id"] == view_id
    assert saved.loc[0, "title"] == "EV leaders"
    assert saved.loc[0, "data_cutoff"] == "April 2026"


def test_research_items_and_watchlist_round_trip(tmp_path):
    path = tmp_path / "research.duckdb"
    item_id = save_research_item(
        "forecast",
        title="KA EV six-month forecast",
        parameters={"state": "KA", "series": "ev_regs"},
        result={"model": "seasonal_naive", "mape": 0.12},
        data_cutoff="April 2026",
        path=path,
    )
    watch_id = add_watchlist_item(
        item_type="state",
        item_key="KA",
        label="Karnataka",
        path=path,
    )

    research = list_research_items(path)
    watchlist = list_watchlist(path)

    assert item_id in research["id"].tolist()
    assert research.loc[research["id"] == item_id, "kind"].iloc[0] == "forecast"
    assert watch_id in watchlist["id"].tolist()
