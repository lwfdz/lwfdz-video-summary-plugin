from __future__ import annotations

import os
from typing import Any

from openai import AsyncOpenAI

from video_summary.evidence import source_evidence

_DETAIL_GUIDANCE = {
    "brief": "控制在约 400—700 字，突出结论和最关键论据。",
    "standard": "控制在约 900—1500 字，兼顾结构、观点、证据和知识延伸。",
    "deep": "尽可能深入，系统整理论证链、隐含前提、争议点和可迁移知识。",
}


def _client_summary_package(source: dict[str, Any], focus: str, detail: str) -> dict[str, Any]:
    video = source.get("video") or {}
    evidence = source_evidence(source)
    instruction = f"""
请基于下面的字幕材料完成中文视频总结。{_DETAIL_GUIDANCE.get(detail, _DETAIL_GUIDANCE['standard'])}
重点关注：{focus or '视频的核心观点、论证结构、关键事实与值得质疑之处'}。

输出结构：
1. 一句话结论
2. 内容脉络
3. 核心观点与证据
4. 值得学习的新知识
5. 可能的偏见、漏洞或待核实信息
6. 证据等级与总结依据
7. 与用户长期知识库相关的标签

不要把字幕里的说法自动当作事实；区分“视频作者主张”和“可确认事实”。
""".strip()
    return {
        "status": "ready_for_client_summary",
        "mode": "chatgpt_client",
        "message": (
            "服务器未配置 OPENAI_API_KEY；请由调用该工具的 ChatGPT 基于 source_material "
            "生成最终总结。"
        ),
        "summary_instruction": instruction,
        "evidence_level": evidence["level"],
        "source_type": evidence["source_type"],
        "knowledge_card_draft": {
            "evidence_level": evidence["level"],
            "source_type": evidence["source_type"],
            "evidence_basis": evidence["basis"],
            "learning_status": "summarized",
            "topics": [],
            "tags": [],
            "fact_check": [],
            "personal_value": "",
        },
        "source_material": {
            "video": video,
            "transcript": source.get("transcript") or "",
            "transcript_truncated": source.get("transcript_truncated", False),
            "warnings": source.get("warnings") or [],
            "evidence": evidence,
        },
    }


async def summarize_source(
    source: dict[str, Any],
    *,
    focus: str = "",
    detail: str = "standard",
) -> dict[str, Any]:
    transcript = str(source.get("transcript") or "").strip()
    video = source.get("video") or {}
    evidence = source_evidence(source)
    if not transcript:
        return {
            "status": "no_transcript",
            "mode": "none",
            "message": "没有获得可用字幕，暂时无法可靠总结。",
            "video": video,
            "evidence_level": evidence["level"],
            "source_type": evidence["source_type"],
            "evidence": evidence,
            "warnings": source.get("warnings") or [],
        }

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return _client_summary_package(source, focus, detail)

    model = os.getenv("SUMMARY_MODEL", "gpt-5.6-luna").strip() or "gpt-5.6-luna"
    prompt = f"""
你是“视频总结”知识整理助手。请根据字幕生成中文总结。

视频标题：{video.get('title')}
UP 主：{(video.get('uploader') or {}).get('name')}
视频简介：{video.get('description') or '无'}
重点关注：{focus or '核心观点、论据、知识价值与可信度'}
详细程度：{detail}。{_DETAIL_GUIDANCE.get(detail, _DETAIL_GUIDANCE['standard'])}

必须做到：
- 区分作者主张、字幕原话与可验证事实。
- 不因字幕缺少标点而虚构信息。
- 说明论证中可能存在的跳跃、偏见或待核实内容。
- 给出 3—8 个适合个人知识库的标签。

输出结构：
## 一句话结论
## 内容脉络
## 核心观点与依据
## 新知识与延伸
## 可信度与争议点
## 证据等级与事实核查
## 知识库标签

字幕：
{transcript}
""".strip()

    try:
        async with AsyncOpenAI(api_key=api_key) as client:
            response = await client.responses.create(
                model=model,
                input=prompt,
                reasoning={"effort": "low"},
            )
        summary = (response.output_text or "").strip()
        if not summary:
            raise RuntimeError("模型没有返回文本。")
        return {
            "status": "completed",
            "mode": "server_openai",
            "model": model,
            "video": video,
            "summary": summary,
            "evidence_level": evidence["level"],
            "source_type": evidence["source_type"],
            "evidence": evidence,
            "transcript_truncated": source.get("transcript_truncated", False),
            "warnings": source.get("warnings") or [],
        }
    except Exception as exc:  # noqa: BLE001 - 失败时回退给 ChatGPT 客户端总结
        package = _client_summary_package(source, focus, detail)
        package["message"] = f"服务端总结失败，已回退到客户端总结模式：{type(exc).__name__}"
        return package
