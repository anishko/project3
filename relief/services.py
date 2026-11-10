from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
from django.conf import settings

@dataclass(frozen=True)
class Citation:
    title: str
    url: str
    source_name: str = ""
    published_date: str = ""
    excerpt: str = ""
    disaster: str = ""

def _safe_text(value: Any) -> str:
    return str(value or "").strip()

def normalize_rag_response(payload: dict[str, Any]) -> dict[str, Any]:
    answer = _safe_text(payload.get("answer"))
    raw_sources = payload.get("sources") or []
    citations, seen_urls = [], set()
    for source in raw_sources:
        if not isinstance(source, dict): continue
        title, url = _safe_text(source.get("title")), _safe_text(source.get("url"))
        if not title or not url or url in seen_urls: continue
        seen_urls.add(url)
        citations.append(Citation(title=title, url=url, source_name=_safe_text(source.get("source_name")), published_date=_safe_text(source.get("published_date")), excerpt=_safe_text(source.get("excerpt")), disaster=_safe_text(source.get("disaster"))))
    return {"answer": answer, "citations": citations}

def ask_rag(question: str) -> dict[str, Any]:
    # TEMPORARY demo adapter. Replace this function with the real RAG call later.
    q = question.lower()
    if "texas" in q or "flood" in q:
        return {"answer":"The curated project material describes severe Texas Hill Country flash flooding. Use the linked sources below to verify details.","sources":[
            {"title":"What to know about the flash floods in Texas that killed over 100 people","url":"https://apnews.com/article/aec9181a07d3ce8ff85197922e108b13","source_name":"Associated Press","published_date":"2025","excerpt":"Project-curated source covering the Texas Hill Country floods.","disaster":"Texas Hill Country floods"},
            {"title":"Texas Hill Country floods: What we know so far","url":"https://www.texastribune.org/2025/07/11/texas-hill-country-floods-what-we-know/","source_name":"The Texas Tribune","published_date":"2025-07-11","excerpt":"Project-curated source summarizing known flood impacts and developments.","disaster":"Texas Hill Country floods"}
        ]}
    return {"answer":"For Hurricane Helene recovery questions, ReliefRoute should ground its response in the team's curated material and expose the exact sources used.","sources":[
        {"title":"The Fight to Get FEMA Aid After Hurricane Helene in Hardest-Hit North Carolina Counties","url":"https://www.propublica.org/article/fema-aid-hurricane-helene-income-disparities","source_name":"ProPublica","published_date":"","excerpt":"Project-curated source about FEMA aid access after Hurricane Helene.","disaster":"Hurricane Helene"},
        {"title":"Hurricane Helene Aftermath Updates and Resources","url":"https://www.wncw.org/news/2024-10-15/hurricane-helene-aftermath-updates-and-resources","source_name":"WNCW","published_date":"2024-10-15","excerpt":"Project-curated source containing aftermath updates and recovery resources.","disaster":"Hurricane Helene"}
    ]}

def _load_resources():
    path = Path(settings.BASE_DIR) / "relief" / "data" / "resources.json"
    return json.loads(path.read_text(encoding="utf-8"))

def find_resources(location: str, need: str, constraints: list[str]) -> list[dict[str, Any]]:
    location_query = location.strip().lower()
    requested = set(constraints or [])
    results = []
    for resource in _load_resources():
        if resource["need"] != need: continue
        searchable = " ".join([resource.get("city",""),resource.get("state",""),resource.get("region","")]).lower()
        parts = [p.strip() for p in location_query.replace(","," ").split() if p.strip()]
        score, reasons = 0, []
        if any(p in searchable for p in parts): score += 40; reasons.append("Location match")
        elif resource.get("region","").lower() == "national": score += 10; reasons.append("Available nationally")
        else: continue
        if resource.get("verified"): score += 25; reasons.append("Verified source")
        supported = set(resource.get("constraints",[]))
        matched = requested & supported
        if requested:
            score += 8 * len(matched)
            if matched: reasons.append("Matches " + ", ".join(sorted(x.replace("_"," ") for x in matched)))
            score -= 4 * len(requested - supported)
        item = dict(resource); item["score"] = score; item["match_reason"] = " • ".join(reasons); results.append(item)
    results.sort(key=lambda i:(i["score"], i.get("source_date",""), i.get("name","")), reverse=True)
    return results
