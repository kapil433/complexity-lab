"""Data-layer tests run against a temp DuckDB built from synthetic fixtures."""

import duckdb
import pandas as pd
import pytest

from complexity_lab.data.reference import (
    build_reference_availability,
    load_reference_tables,
    validate_reference_catalog,
)


@pytest.fixture
def ref_dir(tmp_path):
    (tmp_path / "states.csv").write_text(
        "# test dim\n"
        "state_code,state_name,geojson_name,zone,is_ut\n"
        "ALL,All India,,National,0\n"
        "S1,State One,State One,North,0\n"
        "S2,State Two,State Two,South,0\n"
    )
    (tmp_path / "income.csv").write_text(
        "# test income\nstate_code,fy,pc_nsdp_current_inr\nS1,2020-21,100000\nS2,2020-21,50000\n"
    )
    return tmp_path


def test_load_reference_tables(ref_dir):
    con = duckdb.connect(":memory:")
    summary = load_reference_tables(con, reference_dir=ref_dir)
    assert summary == {"dim_state": 3, "ref_income": 2}
    assert con.execute("SELECT COUNT(*) FROM dim_state").fetchone()[0] == 3


def test_unknown_state_code_rejected(ref_dir):
    (ref_dir / "bad.csv").write_text("state_code,x\nZZ,1\n")
    con = duckdb.connect(":memory:")
    with pytest.raises(ValueError, match="unknown state codes"):
        load_reference_tables(con, reference_dir=ref_dir)


def test_duplicate_state_code_rejected(tmp_path):
    (tmp_path / "states.csv").write_text(
        "state_code,state_name,geojson_name,zone,is_ut\nS1,A,A,N,0\nS1,B,B,S,0\n"
    )
    con = duckdb.connect(":memory:")
    with pytest.raises(ValueError, match="duplicate state_code"):
        load_reference_tables(con, reference_dir=tmp_path)


def test_reference_catalog_matches_files(ref_dir):
    (ref_dir / "reference_catalog.csv").write_text(
        "dataset,file,status,geography,time_coverage,temporal_type,quality_summary,"
        "approved_use,not_available,app_behavior,source_url\n"
        "states,states.csv,usable,test,current,dimension,canonical,use,none,show,\n"
        "income,income.csv,constrained,test,2020,annual,unknown,use,missing years,warn,\n"
    )
    catalog = validate_reference_catalog(ref_dir)
    assert catalog is not None
    availability = build_reference_availability(ref_dir, catalog)
    income = availability.loc[availability["dataset"] == "income"].iloc[0]
    assert income["row_count"] == 2
    assert income["state_codes_present"] == 2


def test_reference_catalog_rejects_undeclared_file(ref_dir):
    pd.DataFrame(
        [
            {
                "dataset": "states",
                "file": "states.csv",
                "status": "usable",
                "geography": "test",
                "time_coverage": "current",
                "temporal_type": "dimension",
                "quality_summary": "canonical",
                "approved_use": "use",
                "not_available": "",
                "app_behavior": "show",
                "source_url": "",
            }
        ]
    ).to_csv(ref_dir / "reference_catalog.csv", index=False)
    with pytest.raises(ValueError, match="file mismatch"):
        validate_reference_catalog(ref_dir)


def test_real_database_grain_if_present():
    """Integration check against the locally built lab.duckdb (skipped in CI)."""
    from complexity_lab.config import settings

    if not settings.db_path.exists():
        pytest.skip("lab.duckdb not built")
    con = duckdb.connect(str(settings.db_path), read_only=True)
    dup = con.execute(
        """SELECT COUNT(*) FROM (
               SELECT state_code, year, month, maker, fuel, COUNT(*) c
               FROM registrations GROUP BY ALL HAVING c > 1)"""
    ).fetchone()[0]
    assert dup == 0, "registration grain must be unique"
    fuels = {r[0] for r in con.execute("SELECT DISTINCT fuel FROM registrations").fetchall()}
    assert fuels == {"Petrol", "Diesel", "CNG", "EV", "Strong Hybrid"}
    con.close()
