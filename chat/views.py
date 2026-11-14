import json
import logging
from dataclasses import asdict

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from relief.services import normalize_rag_response

from .rag import RAGError, answer_question

logger = logging.getLogger(__name__)
MAX_QUESTION_CHARS = 1000


@ensure_csrf_cookie
def index(request):
    return render(request, "chat/index.html", {"max_chars": MAX_QUESTION_CHARS})


@require_POST
def ask(request):
    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Request body must be JSON."}, status=400)

    question = str(payload.get("question", "")).strip() if isinstance(payload, dict) else ""
    if not question:
        return JsonResponse({"error": "Please type a question."}, status=400)
    if len(question) > MAX_QUESTION_CHARS:
        return JsonResponse({"error": f"Questions are limited to {MAX_QUESTION_CHARS} characters."}, status=400)

    try:
        result = answer_question(question)
    except RAGError as exc:
        logger.warning("RAG failure (%s): %s", type(exc).__name__, exc)
        return JsonResponse({"error": exc.user_message}, status=exc.status)
    except Exception:
        logger.exception("Unexpected error answering chat question")
        return JsonResponse({"error": RAGError.user_message}, status=500)

    normalized = normalize_rag_response(result)
    return JsonResponse(
        {"answer": normalized["answer"], "sources": [asdict(c) for c in normalized["citations"]]}
    )
