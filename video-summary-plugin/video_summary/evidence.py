from __future__ import annotations

from typing import Any

EVIDENCE_LEVELS = {"A", "B", "C", "D"}
DEFAULT_SOURCE_TYPE = "public_subtitle"


def source_evidence(source: dict[str, Any]) -> dict[str, Any]:
    """Describe how much of a video is actually available to the summarizer."""
    transcript = str(source.get("transcript") or "").strip()
    video = source.get("video") or {}
    subtitle = source.get("subtitle") or {}
    warnings = source.get("warnings") or []

    if transcript and subtitle:
        return {
            "level": "B",
            "source_type": "public_subtitle",
            "basis": ["public_subtitle", "video_metadata"],
            "limitation": "字幕可以支持内容总结，但事实仍需独立核查。",
        }
    if transcript:
        return {
            "level": "B",
            "source_type": "transcript",
            "basis": ["transcript", "video_metadata"],
            "limitation": "已有文字材料可以支持内容总结，但来源和事实仍需说明。",
        }
    if video.get("description") or warnings:
        return {
            "level": "C",
            "source_type": "page_metadata",
            "basis": ["video_metadata"],
            "limitation": "没有完整字幕或转写，不能冒充逐字总结。",
        }
    if video.get("title"):
        return {
            "level": "D",
            "source_type": "page_metadata",
            "basis": ["title"],
            "limitation": "目前只有标题，不能可靠总结视频内容。",
        }
    return {
        "level": "D",
        "source_type": "link_only",
        "basis": ["url"],
        "limitation": "目前只有链接，不能可靠总结视频内容。",
    }


def normalize_evidence_level(value: str | None, default: str = "B") -> str:
    level = (value or default).strip().upper()
    return level if level in EVIDENCE_LEVELS else default
