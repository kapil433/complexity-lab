"""Serializable global context shared by every interactive lab page."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field


def _values(value: str | Sequence[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item for item in value.split(",") if item]
    return [str(item) for item in value if str(item)]


@dataclass(frozen=True)
class GlobalContext:
    year_start: int
    year_end: int
    states: tuple[str, ...] = field(default_factory=tuple)
    fuels: tuple[str, ...] = field(default_factory=tuple)
    oems: tuple[str, ...] = field(default_factory=tuple)
    segments: tuple[str, ...] = field(default_factory=tuple)
    source: str = "vahan"
    coverage: str = "complete"

    def __post_init__(self) -> None:
        if self.year_start > self.year_end:
            raise ValueError("year_start cannot be after year_end")
        if self.coverage not in {"complete", "available"}:
            raise ValueError("coverage must be 'complete' or 'available'")

    def to_query_params(self) -> dict[str, str]:
        params = {
            "from": str(self.year_start),
            "to": str(self.year_end),
            "source": self.source,
            "coverage": self.coverage,
        }
        for key in ("states", "fuels", "oems", "segments"):
            values = getattr(self, key)
            if values:
                params[key] = ",".join(values)
        return params

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        for key in ("states", "fuels", "oems", "segments"):
            payload[key] = list(payload[key])
        return payload

    @classmethod
    def from_query_params(
        cls,
        params: Mapping[str, str | Sequence[str]],
        *,
        min_year: int,
        max_year: int,
        default_end: int,
    ) -> GlobalContext:
        def integer(name: str, fallback: int) -> int:
            values = _values(params.get(name))
            try:
                return int(values[0]) if values else fallback
            except ValueError:
                return fallback

        year_start = min(max(integer("from", min_year), min_year), max_year)
        year_end = min(max(integer("to", default_end), min_year), max_year)
        if year_start > year_end:
            year_start, year_end = year_end, year_start

        coverage_values = _values(params.get("coverage"))
        coverage = coverage_values[0] if coverage_values else "complete"
        if coverage not in {"complete", "available"}:
            coverage = "complete"

        source_values = _values(params.get("source"))
        source = source_values[0] if source_values else "vahan"

        return cls(
            year_start=year_start,
            year_end=year_end,
            states=tuple(_values(params.get("states"))),
            fuels=tuple(_values(params.get("fuels"))),
            oems=tuple(_values(params.get("oems"))),
            segments=tuple(_values(params.get("segments"))),
            source=source,
            coverage=coverage,
        )
