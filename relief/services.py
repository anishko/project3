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
        # A title is required; the URL is optional (e.g. a pasted document with no public link).
        key = url or title
        if not title or key in seen_urls: continue
        seen_urls.add(key)
        citations.append(Citation(title=title, url=url, source_name=_safe_text(source.get("source_name")), published_date=_safe_text(source.get("published_date")), excerpt=_safe_text(source.get("excerpt")), disaster=_safe_text(source.get("disaster"))))
    return {"answer": answer, "citations": citations}

def ask_rag(question: str) -> dict[str, Any]:
    """Story #4 integration point, now backed by the real RAG pipeline (chat/rag.py)."""
    from chat.rag import answer_question
    return answer_question(question)

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
