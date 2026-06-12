"""Cross-artifact consistency: cards ↔ experiments ↔ app pages ↔ site index.

These break silently otherwise: a renamed experiment leaves a dangling card id
in a page, or a new experiment never appears on the site index.
"""

import re
from pathlib import Path

from complexity_lab.experiments.cards import CARDS
from complexity_lab.experiments.registry import list_experiments

ROOT = Path(__file__).resolve().parents[1]


def test_every_page_card_id_exists():
    used = set()
    for page in (ROOT / "app").rglob("*.py"):
        used.update(re.findall(r"render_card\(\"([\w-]+)\"\)", page.read_text(encoding="utf-8")))
    missing = used - set(CARDS)
    assert not missing, f"pages reference unknown cards: {missing}"


def test_every_experiment_has_a_card():
    exps = {e.name for e in list_experiments()}
    # forecasting/hypothesis-tester are method cards without a registered experiment — fine.
    missing = {e for e in exps if e not in CARDS}
    assert not missing, f"experiments without an explainer card: {missing}"


def test_every_numbered_qmd_is_on_the_index():
    index = (ROOT / "experiments" / "index.qmd").read_text(encoding="utf-8")
    qmds = sorted(p.name for p in (ROOT / "experiments").glob("0*.qmd"))
    missing = [q for q in qmds if q not in index]
    assert not missing, f"experiments missing from index.qmd: {missing}"


def test_card_fields_nonempty():
    for cid, card in CARDS.items():
        assert card.question and card.method, f"{cid}: empty question/method"
        assert card.how_it_works and card.look_for, f"{cid}: empty how/look_for"
        assert card.limitations and card.decisions, f"{cid}: empty limits/decisions"
