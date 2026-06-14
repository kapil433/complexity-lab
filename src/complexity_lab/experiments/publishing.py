"""Visual result bundles and gallery discovery for experiment runs."""

from __future__ import annotations

import html
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _font(size: int, bold: bool = False):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _metric_lines(metrics: dict, limit: int = 5) -> list[str]:
    lines = []
    for key, value in metrics.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            lines.append(f"{key.replace('_', ' ').title()}: {value}")
        if len(lines) >= limit:
            break
    return lines or ["Run completed; inspect tables and diagnostics."]


def primary_finding(metrics: dict) -> str:
    return _metric_lines(metrics, limit=1)[0]


def render_share_card(
    out_path: Path,
    *,
    title: str,
    finding: str,
    cutoff: str,
    status: str,
) -> Path:
    image = Image.new("RGB", (1200, 630), "#10131A")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 24, 630), fill="#E4572E")
    draw.text((70, 60), "COMPLEXITY LAB", fill="#FF8A5B", font=_font(26, bold=True))
    draw.text((70, 120), title, fill="#F7F4EF", font=_font(48, bold=True))
    draw.multiline_text(
        (70, 235),
        finding,
        fill="#F7F4EF",
        font=_font(34),
        spacing=12,
    )
    draw.text((70, 530), f"Data cutoff: {cutoff}", fill="#B9C1CD", font=_font(22))
    draw.text((900, 530), status.upper(), fill="#65C18C", font=_font(22, bold=True))
    image.save(out_path)
    return out_path


def render_hero(
    out_path: Path,
    *,
    title: str,
    metrics: dict,
) -> Path:
    image = Image.new("RGB", (1400, 800), "#F6F2EC")
    draw = ImageDraw.Draw(image)
    draw.text((70, 55), title, fill="#1B1B1B", font=_font(42, bold=True))
    lines = _metric_lines(metrics)
    numeric = [
        (key, float(value))
        for key, value in metrics.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ][:6]
    if numeric:
        max_value = max(abs(value) for _, value in numeric) or 1
        for index, (key, value) in enumerate(numeric):
            y = 150 + index * 92
            width = int(850 * abs(value) / max_value)
            draw.rectangle((390, y, 390 + width, y + 48), fill="#E4572E")
            draw.text((70, y + 5), key.replace("_", " ").title(), fill="#333333", font=_font(24))
            draw.text((400 + width, y + 5), f"{value:,.3g}", fill="#333333", font=_font(24))
    else:
        draw.multiline_text((70, 180), "\n".join(lines), fill="#333333", font=_font(30), spacing=18)
    draw.text(
        (70, 735),
        "Observed inputs and model outputs retain their truth labels and limitations.",
        fill="#6A6A6A",
        font=_font(20),
    )
    image.save(out_path)
    return out_path


def render_diagnostic(
    out_path: Path,
    *,
    input_facts: dict,
    limitations: list[str],
) -> Path:
    image = Image.new("RGB", (1400, 800), "#10131A")
    draw = ImageDraw.Draw(image)
    draw.text((70, 55), "Run diagnostics", fill="#F7F4EF", font=_font(42, bold=True))
    draw.text((70, 125), "Declared inputs", fill="#FF8A5B", font=_font(28, bold=True))
    y = 180
    for name, facts in list(input_facts.items())[:7]:
        available = facts.get("available", False)
        rows = facts.get("rows", "n/a")
        color = "#65C18C" if available else "#E4572E"
        draw.ellipse((70, y + 7, 88, y + 25), fill=color)
        draw.text((110, y), f"{name}: {rows:,} rows" if isinstance(rows, int) else f"{name}: {rows}",
                  fill="#F7F4EF", font=_font(23))
        y += 52
    draw.text((760, 125), "Interpretation limits", fill="#FF8A5B", font=_font(28, bold=True))
    y = 180
    for index, limitation in enumerate(limitations[:5], start=1):
        text = limitation if len(limitation) <= 72 else limitation[:69] + "..."
        draw.text((760, y), f"{index}. {text}", fill="#D7DCE4", font=_font(20))
        y += 78
    draw.text(
        (70, 735),
        "A successful run still inherits the source, coverage, and identification limits above.",
        fill="#B9C1CD",
        font=_font(20),
    )
    image.save(out_path)
    return out_path


def build_result_pages(out_dir: Path, manifest: dict) -> list[Path]:
    figures = out_dir / "figures"
    figures.mkdir(exist_ok=True)
    finding = manifest["primary_finding"]
    hero = render_hero(
        out_dir / "hero.png",
        title=manifest["description"],
        metrics=manifest["metrics"],
    )
    primary = render_hero(
        figures / "01-primary.png",
        title=manifest["description"],
        metrics=manifest["metrics"],
    )
    diagnostic = render_diagnostic(
        figures / "02-diagnostic.png",
        input_facts=manifest["input_facts"],
        limitations=manifest["limitations"],
    )
    share = render_share_card(
        out_dir / "share-card.png",
        title=manifest["experiment"],
        finding=finding,
        cutoff=manifest["data_cutoff"]["vahan"],
        status=manifest["status"],
    )
    hero_html = out_dir / "hero.html"
    hero_html.write_text(
        f"""<!doctype html><meta charset="utf-8"><title>{html.escape(manifest["experiment"])}</title>
        <style>body{{font-family:system-ui;max-width:960px;margin:3rem auto;padding:0 1rem}}
        .finding{{border-left:5px solid #E4572E;padding:1rem;background:#fff5ef}}</style>
        <h1>{html.escape(manifest["description"])}</h1>
        <div class="finding"><strong>Primary finding</strong><br>{html.escape(finding)}</div>
        <h2>Metrics</h2><pre>{html.escape(json.dumps(manifest["metrics"], indent=2, default=str))}</pre>
        <h2>Limitations</h2><ul>{"".join(f"<li>{html.escape(item)}</li>" for item in manifest["limitations"])}</ul>
        """,
        encoding="utf-8",
    )
    result_md = out_dir / "result.md"
    result_md.write_text(
        "\n".join(
            [
                f"# {manifest['description']}",
                "",
                f"**Primary finding:** {finding}",
                "",
                f"**Data cutoff:** {manifest['data_cutoff']['vahan']}",
                "",
                "## Metrics",
                "```json",
                json.dumps(manifest["metrics"], indent=2, default=str),
                "```",
                "",
                "## Limitations",
                *[f"- {item}" for item in manifest["limitations"]],
            ]
        ),
        encoding="utf-8",
    )
    return [hero, primary, diagnostic, share, hero_html, result_md]


def discover_runs(outputs_dir: Path) -> list[dict]:
    runs = []
    if not outputs_dir.exists():
        return runs
    for manifest_path in outputs_dir.glob("*/*/manifest.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        manifest["_manifest_path"] = str(manifest_path)
        manifest["_run_dir"] = str(manifest_path.parent)
        runs.append(manifest)
    return sorted(runs, key=lambda item: item.get("timestamp_utc", ""), reverse=True)


def latest_runs_by_experiment(outputs_dir: Path) -> dict[str, dict]:
    latest = {}
    for run in discover_runs(outputs_dir):
        latest.setdefault(run["experiment"], run)
    return latest
