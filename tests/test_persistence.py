from complexity_lab.persistence import list_saved_views, save_view


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
