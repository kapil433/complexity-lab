from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).parents[1]


def test_market_brief_smoke():
    app = AppTest.from_file(str(ROOT / "app" / "Home.py"), default_timeout=45)
    app.run()

    assert not app.exception
    assert {metric.label for metric in app.metric} >= {
        "Latest complete year",
        "Registrations",
        "EV share",
    }
    assert len(app.get("plotly_chart")) >= 2


def test_every_page_uses_shared_truth_shell():
    pages = sorted((ROOT / "app" / "pages").glob("*.py"))

    assert len(pages) == 10
    for page in pages:
        source = page.read_text(encoding="utf-8")
        assert "render_app_shell(" in source, page.name
