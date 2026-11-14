"""Thin wrapper around the chat-completion API so it is easy to mock in tests."""
from __future__ import annotations

from django.conf import settings

SYSTEM_PROMPT = """You are ReliefRoute, an assistant for disaster preparedness and recovery \
(hurricanes, floods and related evacuations).

Rules:
- Answer ONLY using the numbered context passages provided below. Do not use outside knowledge.
- If the context does not contain the answer, say plainly that you don't know based on the \
current sources, and suggest checking official authorities (local emergency management, FEMA, \
the National Weather Service).
- Cite the passages you used with their numbers in square brackets, e.g. [1] or [2][3].
- Be concise and practical. Use short bullet lists for steps.
- For life-threatening situations, tell the user to call 911 or follow official evacuation orders."""


class LLMError(RuntimeError):
    pass


def build_messages(question: str, contexts: list[dict]) -> list[dict]:
    blocks = [f"[{i}] {c['title']}\n{c['text']}" for i, c in enumerate(contexts, start=1)]
    user = "Context passages:\n\n" + "\n\n".join(blocks) + f"\n\nQuestion: {question}"
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def generate_answer(question: str, contexts: list[dict]) -> str:
    if not settings.OPENAI_API_KEY:
        raise LLMError("OPENAI_API_KEY is not set.")
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=45, max_retries=1)
        resp = client.chat.completions.create(
            model=settings.OPENAI_CHAT_MODEL,
            messages=build_messages(question, contexts),
            temperature=0.2,
            max_tokens=600,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        raise LLMError(f"Chat completion failed: {exc}") from exc
