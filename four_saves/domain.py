from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class JobStatus(str, Enum):
    ANALYZING = "analyzing"
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    NEEDS_ATTENTION = "needs_attention"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DownloadPreset(str, Enum):
    BEST = "best"
    UNIVERSAL = "universal"
    EDIT_READY = "edit_ready"
    SMALL = "small"
    AUDIO = "audio"

    @property
    def label(self) -> str:
        return {
            self.BEST: "Best quality",
            self.UNIVERSAL: "Universal MP4",
            self.EDIT_READY: "Edit-ready MP4",
            self.SMALL: "Small MP4",
            self.AUDIO: "Audio (M4A)",
        }[self]


@dataclass(slots=True)
class DownloadJob:
    id: str
    url: str
    title: str
    platform: str
    preset: DownloadPreset
    output_dir: str
    status: JobStatus
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
    output_path: str = ""
    error: str = ""
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def create(
        cls,
        *,
        url: str,
        title: str,
        platform: str,
        preset: DownloadPreset,
        output_dir: str | Path,
    ) -> DownloadJob:
        now = utc_now()
        return cls(
            id=uuid4().hex,
            url=url,
            title=title or "Untitled download",
            platform=platform or "Unknown site",
            preset=preset,
            output_dir=str(Path(output_dir).expanduser()),
            status=JobStatus.QUEUED,
            created_at=now,
            updated_at=now,
        )
