from __future__ import annotations

import contextlib
import os
from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from video_summary.bilibili import VideoSourceError, fetch_bilibili_source
from video_summary.evidence import normalize_evidence_level, source_evidence
from video_summary.library import VideoLibrary
from video_summary.summarizer import summarize_source

mcp = FastMCP(
    "视频总结",
    instructions=(
        "提取 B 站视频公开字幕并总结；按证据等级区分视频主张、可核实事实和推测，"
        "可把高质量总结保存到个人视频知识库。"
        "当 summarize_video 返回 ready_for_client_summary 时，请直接依据其 source_material "
        "生成最终中文总结，不要要求用户另外复制字幕。完成总结后，可调用 save_video_note 保存。"
    ),
    stateless_http=True,
    json_response=True,
)
library = VideoLibrary(os.getenv("DATA_DIR", "data"))


def _error_payload(exc: Exception) -> dict[str, Any]:
    return {
        "status": "error",
        "error_type": type(exc).__name__,
        "message": str(exc),
    }


@mcp.tool()
async def get_video_info(url: str) -> dict[str, Any]:
    """读取 B 站视频标题、UP 主、简介、时长、分 P 和互动数据，不读取完整字幕。"""
    try:
        source = await fetch_bilibili_source(url, include_transcript=False)
        return {
            "status": "completed",
            "video": source["video"],
            "evidence": source_evidence(source),
        }
    except (VideoSourceError, Exception) as exc:
        return _error_payload(exc)


@mcp.tool()
async def extract_video_transcript(
    url: str,
    max_chars: int = 60_000,
    preferred_language: str = "zh-CN",
) -> dict[str, Any]:
    """提取 B 站视频公开字幕。适合用户要求逐段分析、核对原话或自行指定总结方式时调用。"""
    try:
        safe_max = max(1_000, min(max_chars, 120_000))
        return await fetch_bilibili_source(
            url,
            include_transcript=True,
            max_chars=safe_max,
            preferred_language=preferred_language,
        )
    except (VideoSourceError, Exception) as exc:
        return _error_payload(exc)


@mcp.tool()
async def summarize_video(
    url: str,
    focus: str = "",
    detail: str = "standard",
    save: bool = True,
) -> dict[str, Any]:
    """总结 B 站视频。

    detail 可选 brief、standard、deep；focus 可指定财经、论证漏洞、知识点等关注方向。
    """
    try:
        normalized_detail = detail if detail in {"brief", "standard", "deep"} else "standard"
        max_chars = 35_000 if normalized_detail == "brief" else 60_000
        source = await fetch_bilibili_source(url, include_transcript=True, max_chars=max_chars)
        result = await summarize_source(source, focus=focus, detail=normalized_detail)
        if save and result.get("status") == "completed" and result.get("summary"):
            video = source.get("video") or {}
            evidence = result.get("evidence") or source_evidence(source)
            record = await library.save(
                {
                    "url": video.get("canonical_url") or video.get("url") or url,
                    "title": video.get("title") or "未命名视频",
                    "summary": result["summary"],
                    "tags": [],
                    "platform": "bilibili",
                    "bvid": video.get("bvid"),
                    "metadata": video,
                    "evidence_level": evidence.get("level") or result.get("evidence_level"),
                    "source_type": result.get("source_type") or evidence.get("source_type"),
                    "evidence_basis": evidence.get("basis") or [],
                    "learning_status": "summarized",
                    "topics": [],
                    "fact_check": [],
                    "personal_value": "",
                }
            )
            result["saved_note_id"] = record["id"]
        elif save and result.get("status") == "ready_for_client_summary":
            result["save_after_summary"] = (
                "请在生成最终总结后调用 save_video_note，把总结写入知识库。"
            )
        return result
    except (VideoSourceError, Exception) as exc:
        return _error_payload(exc)


@mcp.tool()
async def save_video_note(
    url: str,
    title: str,
    summary: str,
    tags: str = "",
    evidence_level: str = "B",
    source_type: str = "public_subtitle",
    topics: str = "",
    learning_status: str = "summarized",
    personal_value: str = "",
    fact_check: str = "",
) -> dict[str, Any]:
    """保存已完成的视频知识卡；标签、主题和核查结论均用逗号分隔。"""
    if not summary.strip():
        return {"status": "error", "message": "summary 不能为空。"}

    def split_values(value: str) -> list[str]:
        return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]

    tag_list = split_values(tags)
    topic_list = split_values(topics)
    fact_check_items = split_values(fact_check)
    record = await library.save(
        {
            "url": url.strip(),
            "title": title.strip() or "未命名视频",
            "summary": summary.strip(),
            "tags": tag_list,
            "platform": "bilibili" if "bilibili" in url or "b23.tv" in url else "other",
            "evidence_level": normalize_evidence_level(evidence_level),
            "source_type": source_type.strip() or "public_subtitle",
            "topics": topic_list,
            "learning_status": learning_status.strip() or "summarized",
            "personal_value": personal_value.strip(),
            "fact_check": fact_check_items,
        }
    )
    return {"status": "completed", "note": record}


@mcp.tool()
async def search_video_library(query: str = "", limit: int = 10) -> dict[str, Any]:
    """按标题、总结、标签或链接搜索个人视频知识库。query 留空时返回最近保存的内容。"""
    results = await library.search(query=query, limit=limit)
    return {"status": "completed", "count": len(results), "items": results}


@mcp.tool()
async def get_video_note(item_id: str) -> dict[str, Any]:
    """根据知识库条目 ID 读取完整视频总结。"""
    item = await library.get(item_id)
    if not item:
        return {"status": "not_found", "message": "没有找到对应条目。"}
    return {"status": "completed", "item": item}


@mcp.tool()
async def video_knowledge_base_stats() -> dict[str, Any]:
    """查看个人视频知识库总数、证据等级、学习状态、标签和主题统计。"""
    return {"status": "completed", "stats": await library.stats()}


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "video-summary-mcp", "mcp_endpoint": "/mcp"})


@contextlib.asynccontextmanager
async def lifespan(_: Starlette):
    async with mcp.session_manager.run():
        yield


mcp_app = mcp.streamable_http_app()
app = Starlette(
    routes=[
        Route("/health", endpoint=health, methods=["GET"]),
        Mount("/", app=mcp_app),
    ],
    lifespan=lifespan,
)
app = CORSMiddleware(
    app,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Mcp-Session-Id"],
)
