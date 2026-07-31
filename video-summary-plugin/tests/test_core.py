from __future__ import annotations

import asyncio
import json

from video_summary.bilibili import (
    VideoSourceError,
    _normalized_input_url,
    extract_bvid,
    extract_page_number,
)
from video_summary.evidence import source_evidence
from video_summary.library import VideoLibrary
from video_summary.summarizer import summarize_source


def test_extract_bvid() -> None:
    assert extract_bvid("https://www.bilibili.com/video/BV1xx411c7mD") == "BV1xx411c7mD"


def test_extract_page_number() -> None:
    assert extract_page_number("https://www.bilibili.com/video/BV1xx411c7mD?p=3") == 3
    assert extract_page_number("https://www.bilibili.com/video/BV1xx411c7mD") == 1
    assert extract_page_number("https://www.bilibili.com/video/BV1xx411c7mD?p=bad") == 1


def test_invalid_bvid() -> None:
    try:
        extract_bvid("https://www.bilibili.com/video/not-a-bvid")
    except VideoSourceError:
        return
    raise AssertionError("invalid BVID should raise VideoSourceError")


def test_only_http_urls_are_supported() -> None:
    assert _normalized_input_url("b23.tv/abc").startswith("https://")
    try:
        _normalized_input_url("ftp://www.bilibili.com/video/BV1xx411c7mD")
    except VideoSourceError:
        return
    raise AssertionError("non-HTTP URLs should raise VideoSourceError")


def test_summarize_without_api_key_returns_client_package(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = asyncio.run(
        summarize_source(
            {
                "video": {"title": "测试视频"},
                "transcript": "这是公开字幕。",
                "warnings": [],
            },
            focus="核心论点",
            detail="brief",
        )
    )

    assert result["status"] == "ready_for_client_summary"
    assert result["source_material"]["transcript"] == "这是公开字幕。"
    assert result["evidence_level"] == "B"


def test_evidence_level_does_not_claim_metadata_is_a_transcript() -> None:
    result = source_evidence(
        {"video": {"title": "只有标题", "description": "视频简介和来源线索"}, "warnings": []}
    )
    assert result["level"] == "C"
    assert result["source_type"] == "page_metadata"


def test_library_round_trip(tmp_path) -> None:
    async def run() -> None:
        library = VideoLibrary(str(tmp_path))
        record = await library.save(
            {
                "title": "测试视频",
                "url": "https://example.com/video",
                "summary": "这是一个测试总结。",
                "tags": ["测试"],
            }
        )
        results = await library.search("测试", limit=5)
        assert results[0]["id"] == record["id"]

        updated = await library.save(
            {
                "title": "测试视频",
                "url": "https://example.com/video",
                "summary": "更新后的测试总结。",
                "tags": ["更新"],
                "evidence_level": "B",
            }
        )
        assert updated["id"] == record["id"]
        assert updated["updated_at"]
        stats = await library.stats()
        assert stats["count"] == 1
        assert stats["by_evidence_level"] == {"B": 1}

        loaded = await library.get(record["id"])
        assert loaded is not None
        assert loaded["summary"] == "更新后的测试总结。"

        library.path.write_text(
            json.dumps(["损坏条目", record], ensure_ascii=False),
            encoding="utf-8",
        )
        results = await library.search("测试", limit=5)
        assert [item["id"] for item in results] == [record["id"]]

    asyncio.run(run())
