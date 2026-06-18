"""Serializable research sessions for restoring and rerunning app analyses."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from complexity_lab.app_state import GlobalContext


def _tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(item for item in value.split(",") if item)
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value if str(item))
    return (str(value),)


@dataclass(frozen=True)
class ResearchSession:
    """A reproducible snapshot of one interactive research step."""

    page: str
    global_context: GlobalContext
    page_params: dict[str, Any] = field(default_factory=dict)
    method_id: str | None = None
    evidence: str = "Derived"
    data_cutoff: str = ""
    limitations: tuple[str, ...] = field(default_factory=tuple)
    rerun_label: str | None = None
    artifacts: tuple[str, ...] = field(default_factory=tuple)

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["global_context"] = self.global_context.to_payload()
        payload["limitations"] = list(self.limitations)
        payload["artifacts"] = list(self.artifacts)
        return payload

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ResearchSession:
        context_payload = dict(payload.get("global_context", {}))
        context = GlobalContext(
            year_start=int(context_payload["year_start"]),
            year_end=int(context_payload["year_end"]),
            states=_tuple(context_payload.get("states")),
            fuels=_tuple(context_payload.get("fuels")),
            oems=_tuple(context_payload.get("oems")),
            segments=_tuple(context_payload.get("segments")),
            source=str(context_payload.get("source", "vahan")),
            coverage=str(context_payload.get("coverage", "complete")),
        )
        return cls(
            page=str(payload["page"]),
            global_context=context,
            page_params=dict(payload.get("page_params", {})),
            method_id=payload.get("method_id"),
            evidence=str(payload.get("evidence", "Derived")),
            data_cutoff=str(payload.get("data_cutoff", "")),
            limitations=_tuple(payload.get("limitations")),
            rerun_label=payload.get("rerun_label"),
            artifacts=_tuple(payload.get("artifacts")),
        )

    def restore_query_params(self) -> dict[str, str]:
        params = self.global_context.to_query_params()
        params["page"] = self.page
        if self.method_id:
            params["method"] = self.method_id
        for key, value in self.page_params.items():
            if value is None:
                continue
            params[f"p_{key}"] = ",".join(map(str, value)) if isinstance(value, (list, tuple)) else str(value)
        return params

    def markdown_summary(self) -> str:
        lines = [
            f"### {self.page}",
            f"- Evidence: {self.evidence}",
            f"- Data cutoff: {self.data_cutoff or 'not recorded'}",
        ]
        if self.method_id:
            lines.append(f"- Method: `{self.method_id}`")
        if self.page_params:
            lines.append(f"- Parameters: `{self.page_params}`")
        if self.limitations:
            lines.append("- Boundaries:")
            lines.extend(f"  - {item}" for item in self.limitations)
        return "\n".join(lines)
