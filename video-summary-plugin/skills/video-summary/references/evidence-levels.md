# Evidence and knowledge-card reference

## Source mapping

| Source available | Default level | `source_type` | Safe conclusion |
| --- | --- | --- | --- |
| Public subtitle with usable transcript | B | `public_subtitle` | Summarize the transcript; fact-check important claims separately |
| User-provided or otherwise usable transcript | B | `transcript` | Summarize the supplied text and mark its provenance |
| Title, description, metadata, and listed sources only | C | `page_metadata` | Summarize available claims, not the full video |
| URL or title only | D | `link_only` | Ask for subtitles, transcript, audio, or video |

Level A is a final-answer designation, not an automatic downloader result. Use it only when the answer includes sufficient independent verification for the important factual claims.

## Card fields

```json
{
  "title": "视频标题",
  "url": "canonical URL",
  "summary": "完成的中文总结",
  "evidence_level": "B",
  "source_type": "public_subtitle",
  "evidence_basis": ["public_subtitle", "video_metadata"],
  "fact_check": ["已确认：...", "待核实：..."],
  "topics": ["AI与科技"],
  "tags": ["地区限制", "平台合规"],
  "personal_value": "对会计、财经或职业规划的意义",
  "learning_status": "summarized",
  "related_ids": []
}
```

Allowed learning statuses are `summarized`, `studying`, `learned`, and `review`. Keep facts, interpretations, and predictions in separate bullets so later updates can revise time-sensitive claims without rewriting the whole card.
