from complexity_lab.experiments.publishing import build_result_pages, discover_runs


def test_visual_result_bundle_and_discovery(tmp_path):
    run_dir = tmp_path / "demo" / "20260614T000000Z"
    run_dir.mkdir(parents=True)
    manifest = {
        "experiment": "demo",
        "description": "Demo experiment",
        "status": "success",
        "primary_finding": "Effect: 1.2",
        "metrics": {"effect": 1.2, "n": 42},
        "limitations": ["Illustrative result."],
        "input_facts": {"panel_state_month": {"available": True, "rows": 100}},
        "data_cutoff": {"vahan": "2026-04-01"},
    }

    paths = build_result_pages(run_dir, manifest)

    assert all(path.exists() for path in paths)
    assert (run_dir / "hero.png").exists()
    assert (run_dir / "figures" / "01-primary.png").exists()
    assert (run_dir / "figures" / "02-diagnostic.png").exists()
    assert (run_dir / "share-card.png").exists()

    (run_dir / "manifest.json").write_text(
        '{"experiment":"demo","timestamp_utc":"20260614T000000Z"}',
        encoding="utf-8",
    )
    assert discover_runs(tmp_path)[0]["experiment"] == "demo"
