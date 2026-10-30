"""A reviewed release snapshot; this value alone is not a production authorization credential."""

from dataclasses import dataclass

@dataclass(frozen=True)
class ApprovedRelease:
    candidate_id: str
    revision: int
    fingerprint: str
    path: str
    caption: str
    scheduled_for: str


