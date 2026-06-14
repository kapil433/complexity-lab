import duckdb

from complexity_lab.app_state import GlobalContext
from complexity_lab.data.access import market_annual, vahan_cutoff, vahan_period_status


def _connection():
    con = duckdb.connect()
    con.execute(
        """
        CREATE TABLE panel_state_month (
            state_code VARCHAR, date DATE, year INTEGER, month INTEGER,
            total_regs INTEGER, ev_regs INTEGER, cng_regs INTEGER,
            petrol_regs INTEGER, diesel_regs INTEGER, hybrid_regs INTEGER
        )
        """
    )
    rows = []
    for month in range(1, 13):
        rows.append(("ALL", f"2024-{month:02d}-01", 2024, month, 100, 10, 20, 50, 15, 5))
    for month in range(1, 5):
        rows.append(("ALL", f"2025-{month:02d}-01", 2025, month, 120, 20, 20, 55, 20, 5))
    con.executemany("INSERT INTO panel_state_month VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    return con


def test_vahan_status_finds_complete_year_and_partial_cutoff():
    con = _connection()
    status = vahan_period_status(con)
    cutoff = vahan_cutoff(con)

    assert status["completeness_status"].tolist() == ["complete", "partial"]
    assert cutoff.latest_complete_year == 2024
    assert cutoff.latest_period == "April 2025"
    assert cutoff.observed_months_latest_year == 4


def test_market_annual_scopes_total_to_selected_fuels():
    con = _connection()
    context = GlobalContext(2024, 2024, fuels=("EV",))

    annual = market_annual(con, context)

    assert annual.loc[0, "total_regs"] == 120
    assert annual.loc[0, "ev_regs"] == 120
    assert annual.loc[0, "ev_share"] == 1.0
    assert "cng_regs" not in annual.columns
