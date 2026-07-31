from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx


class VideoSourceError(RuntimeError):
    """视频链接或上游接口无法处理。"""


_BVID_RE = re.compile(r"(BV[0-9A-Za-z]{10})")
_ALLOWED_HOSTS = {"bilibili.com", "www.bilibili.com", "m.bilibili.com", "b23.tv", "www.b23.tv"}
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0 Safari/537.36"
)


def extract_bvid(url: str) -> str:
    match = _BVID_RE.search(url)
    if not match:
        raise VideoSourceError("链接中没有找到有效的 BVID。")
    return match.group(1)


def extract_page_number(url: str) -> int:
    value = parse_qs(urlparse(url).query).get("p", ["1"])[0]
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 1


def _normalized_input_url(url: str) -> str:
    value = url.strip()
    if not value:
        raise VideoSourceError("视频链接不能为空。")
    if "://" not in value:
        value = "https://" + value
    parsed = urlparse(value)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise VideoSourceError("视频链接必须使用 HTTP 或 HTTPS。")
    host = (parsed.hostname or "").lower()
    if host not in _ALLOWED_HOSTS and not host.endswith(".bilibili.com"):
        raise VideoSourceError("第一版仅支持 bilibili.com 和 b23.tv 链接。")
    return value


def _headers(referer: str | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "application/json,text/plain,*/*",
    }
    if referer:
        headers["Referer"] = referer
    cookie = os.getenv("BILIBILI_COOKIE", "").strip()
    if cookie:
        headers["Cookie"] = cookie
    return headers


async def resolve_bilibili_url(url: str) -> str:
    value = _normalized_input_url(url)
    host = (urlparse(value).hostname or "").lower()
    if host not in {"b23.tv", "www.b23.tv"}:
        return value

    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0, headers=_headers()) as client:
        response = await client.get(value)
        response.raise_for_status()
        final_url = str(response.url)
    _normalized_input_url(final_url)
    return final_url


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = await client.get(url, params=params)
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict) and payload.get("code") not in (None, 0):
        message = payload.get("message") or payload.get("msg") or "B 站接口返回错误"
        raise VideoSourceError(f"{message}（code={payload.get('code')}）")
    if not isinstance(payload, dict):
        raise VideoSourceError("B 站接口返回了无法识别的数据。")
    return payload


def _pick_subtitle(
    subtitles: list[dict[str, Any]], preferred_language: str
) -> dict[str, Any] | None:
    if not subtitles:
        return None
    preferred = preferred_language.lower()
    for subtitle in subtitles:
        language = str(subtitle.get("lan", "")).lower()
        if language == preferred:
            return subtitle
    for subtitle in subtitles:
        language = str(subtitle.get("lan", "")).lower()
        if language.startswith("zh"):
            return subtitle
    return subtitles[0]


async def fetch_bilibili_source(
    url: str,
    *,
    include_transcript: bool = True,
    max_chars: int = 60_000,
    preferred_language: str = "zh-CN",
) -> dict[str, Any]:
    """读取 B 站视频公开元数据与字幕。不会下载视频文件。"""
    safe_max_chars = max(1_000, min(max_chars, 120_000))
    resolved_url = await resolve_bilibili_url(url)
    bvid = extract_bvid(resolved_url)
    requested_page = extract_page_number(resolved_url)
    referer = f"https://www.bilibili.com/video/{bvid}"

    async with httpx.AsyncClient(timeout=20.0, headers=_headers(referer)) as client:
        view_payload = await _get_json(
            client,
            "https://api.bilibili.com/x/web-interface/view",
            params={"bvid": bvid},
        )
        data = view_payload.get("data") or {}
        pages = data.get("pages") or []
        if not pages:
            raise VideoSourceError("没有读取到视频分 P 信息。")
        page_index = min(requested_page, len(pages)) - 1
        page = pages[page_index]
        cid = page.get("cid")
        if not cid:
            raise VideoSourceError("没有读取到视频 CID。")

        owner = data.get("owner") or {}
        stat = data.get("stat") or {}
        metadata: dict[str, Any] = {
            "platform": "bilibili",
            "url": resolved_url,
            "canonical_url": referer + (f"?p={page_index + 1}" if len(pages) > 1 else ""),
            "bvid": bvid,
            "aid": data.get("aid"),
            "cid": cid,
            "page": page_index + 1,
            "page_count": len(pages),
            "title": data.get("title") or page.get("part") or bvid,
            "page_title": page.get("part"),
            "description": data.get("desc") or "",
            "duration_seconds": page.get("duration") or data.get("duration"),
            "published_at": data.get("pubdate"),
            "cover_url": data.get("pic"),
            "uploader": {
                "name": owner.get("name"),
                "mid": owner.get("mid"),
            },
            "stats": {
                "view": stat.get("view"),
                "like": stat.get("like"),
                "coin": stat.get("coin"),
                "favorite": stat.get("favorite"),
                "reply": stat.get("reply"),
            },
        }

        result: dict[str, Any] = {
            "video": metadata,
            "subtitle": None,
            "transcript": "",
            "segments": [],
            "transcript_truncated": False,
            "warnings": [],
        }
        if not include_transcript:
            return result

        player_payload = await _get_json(
            client,
            "https://api.bilibili.com/x/player/v2",
            params={"bvid": bvid, "cid": cid},
        )
        subtitle_data = ((player_payload.get("data") or {}).get("subtitle") or {})
        subtitles = subtitle_data.get("subtitles") or []
        selected = _pick_subtitle(subtitles, preferred_language)
        if not selected:
            result["warnings"].append(
                "该视频没有可公开读取的字幕。第一版尚未自动下载音频转写。"
            )
            return result

        subtitle_url = str(selected.get("subtitle_url") or "")
        if subtitle_url.startswith("//"):
            subtitle_url = "https:" + subtitle_url
        if not subtitle_url.startswith("https://"):
            raise VideoSourceError("字幕地址无效。")

        subtitle_payload = await _get_json(client, subtitle_url)
        body = subtitle_payload.get("body") or []
        segments: list[dict[str, Any]] = []
        text_parts: list[str] = []
        current_chars = 0
        truncated = False
        for item in body:
            text = str(item.get("content") or "").strip()
            if not text:
                continue
            addition = len(text) + (1 if text_parts else 0)
            if current_chars + addition > safe_max_chars:
                remaining = safe_max_chars - current_chars
                if remaining > 0:
                    text_parts.append(text[:remaining])
                truncated = True
                break
            text_parts.append(text)
            current_chars += addition
            segments.append(
                {
                    "start": item.get("from"),
                    "end": item.get("to"),
                    "text": text,
                }
            )

        result.update(
            {
                "subtitle": {
                    "language": selected.get("lan"),
                    "language_name": selected.get("lan_doc"),
                    "source_url": subtitle_url,
                },
                "transcript": "\n".join(text_parts),
                "segments": segments,
                "transcript_truncated": truncated,
            }
        )
        if truncated:
            result["warnings"].append(f"字幕超过 {safe_max_chars} 字符，已截断。")
        return result
