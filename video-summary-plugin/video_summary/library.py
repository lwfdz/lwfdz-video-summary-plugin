from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


def _normalized_identity(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _same_video(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left.get("bvid") and right.get("bvid"):
        return _normalized_identity(left["bvid"]) == _normalized_identity(right["bvid"])
    for key in ("canonical_url", "url"):
        left_value = _normalized_identity(left.get(key))
        right_value = _normalized_identity(right.get(key))
        if left_value and right_value and left_value == right_value:
            return True
    return False


class VideoLibrary:
    """轻量 JSON 知识库；适合单实例 MVP。"""

    def __init__(self, data_dir: str = "data") -> None:
        self.directory = Path(data_dir)
        self.path = self.directory / "library.json"
        self._lock = asyncio.Lock()

    def _read_sync(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(payload, list):
            return []
        return [item for item in payload if isinstance(item, dict)]

    def _write_sync(self, items: list[dict[str, Any]]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temp_path, self.path)

    async def save(self, item: dict[str, Any]) -> dict[str, Any]:
        async with self._lock:
            items = await asyncio.to_thread(self._read_sync)
            record = {
                **item,
                "id": item.get("id") or uuid4().hex[:12],
                "saved_at": item.get("saved_at")
                or datetime.now(UTC).isoformat(),
            }
            matching_index = next(
                (index for index, existing in enumerate(items) if _same_video(existing, record)),
                None,
            )
            if matching_index is None:
                items.insert(0, record)
            else:
                existing = items.pop(matching_index)
                record = {
                    **existing,
                    **record,
                    "id": existing.get("id") or record["id"],
                    "saved_at": existing.get("saved_at") or record["saved_at"],
                    "updated_at": datetime.now(UTC).isoformat(),
                }
                items.insert(0, record)
            await asyncio.to_thread(self._write_sync, items)
            return record

    async def search(self, query: str = "", limit: int = 10) -> list[dict[str, Any]]:
        items = await asyncio.to_thread(self._read_sync)
        needle = query.strip().lower()
        if needle:
            items = [
                item
                for item in items
                if needle
                in " ".join(
                    str(item.get(key) or "")
                    for key in (
                        "title",
                        "summary",
                        "tags",
                        "topics",
                        "evidence_level",
                        "learning_status",
                        "url",
                    )
                ).lower()
            ]
        results: list[dict[str, Any]] = []
        for item in items[: max(0, min(limit, 50))]:
            summary = str(item.get("summary") or "")
            results.append(
                {
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "tags": item.get("tags") or [],
                    "topics": item.get("topics") or [],
                    "evidence_level": item.get("evidence_level"),
                    "learning_status": item.get("learning_status"),
                    "saved_at": item.get("saved_at"),
                    "updated_at": item.get("updated_at"),
                    "summary_excerpt": summary[:500],
                }
            )
        return results

    async def get(self, item_id: str) -> dict[str, Any] | None:
        items = await asyncio.to_thread(self._read_sync)
        return next((item for item in items if item.get("id") == item_id), None)

    async def stats(self) -> dict[str, Any]:
        items = await asyncio.to_thread(self._read_sync)
        evidence: dict[str, int] = {}
        statuses: dict[str, int] = {}
        tags: dict[str, int] = {}
        topics: dict[str, int] = {}
        for item in items:
            evidence_level = str(item.get("evidence_level") or "unknown")
            evidence[evidence_level] = evidence.get(evidence_level, 0) + 1
            status = str(item.get("learning_status") or "summarized")
            statuses[status] = statuses.get(status, 0) + 1
            for field, counts in (("tags", tags), ("topics", topics)):
                values = item.get(field) or []
                if isinstance(values, str):
                    values = [values]
                for value in values:
                    label = str(value).strip()
                    if label:
                        counts[label] = counts.get(label, 0) + 1
        return {
            "count": len(items),
            "by_evidence_level": dict(sorted(evidence.items())),
            "by_learning_status": dict(sorted(statuses.items())),
            "top_tags": dict(sorted(tags.items(), key=lambda pair: (-pair[1], pair[0]))[:20]),
            "top_topics": dict(sorted(topics.items(), key=lambda pair: (-pair[1], pair[0]))[:20]),
        }
