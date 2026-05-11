"""
LLM-assisted regex generation. The model only returns pattern metadata (JSON).
Sample matches are computed locally against the stored column, never from the model.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pandas as pd
from django.conf import settings
from openai import OpenAI

SYSTEM_PROMPT = """You propose a single Python `re` pattern from a user's goal.
Return one JSON object with exactly these keys:
- "regex_pattern": string, usable with Python `re.compile()` (no embedded flag prefixes like (?i) unless truly needed).
- "explanation": short plain-English line for an end user (keep under 400 characters).
- "warnings": JSON array of strings. Use [] if the goal is clear. If the request is ambiguous, broad, or risky, add brief warnings (what to clarify or double-check).

Hard rules:
- Output JSON only. No markdown, no code fences, no text before or after the JSON.
- Do not include sample matches, row numbers, rewritten data, or replacement text.
- Do not instruct anyone to change, delete, or export user data.
- Prefer a tighter pattern when example values show a clear structure."""


class LlmInvocationError(Exception):
    """Raised when the LLM call or its payload cannot be used."""


def collect_prompt_samples(
    series: pd.Series,
    *,
    max_values: int = 20,
    max_len: int = 120,
) -> list[str]:
    """Non-null example strings for the prompt (truncated, de-duplicated)."""
    seen: set[str] = set()
    out: list[str] = []
    for val in series:
        if pd.isna(val):
            continue
        s = str(val).strip()
        if not s:
            continue
        clip = s if len(s) <= max_len else s[: max_len - 3] + "..."
        if clip in seen:
            continue
        seen.add(clip)
        out.append(clip)
        if len(out) >= max_values:
            break
    return out


def collect_sample_matches(
    series: pd.Series,
    compiled: re.Pattern[str],
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """First distinct full matches found by scanning the column (server-side only)."""
    results: list[dict[str, Any]] = []
    seen_text: set[str] = set()
    scan_limit = min(len(series), settings.MAX_SAMPLE_SCAN_ROWS)
    for pos in range(scan_limit):
        val = series.iloc[pos]
        if pd.isna(val):
            continue
        s = str(val)
        searchable = s[: settings.MAX_CELL_CHARS]
        match = compiled.search(searchable)
        if not match:
            continue
        matched = match.group(0)
        if matched in seen_text:
            continue
        seen_text.add(matched)
        display = s if len(s) <= 500 else s[:497] + "..."
        results.append(
            {
                "row_index": pos,
                "source_value": display,
                "matched_text": matched,
            }
        )
        if len(results) >= limit:
            break
    return results


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.split("\n")
    if lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _parse_json_object(content: str) -> dict[str, Any]:
    try:
        return json.loads(_strip_code_fence(content))
    except json.JSONDecodeError as exc:
        raise LlmInvocationError(
            "The language model returned invalid JSON. Please try again."
        ) from exc


def call_llm_for_regex(
    column_name: str,
    user_prompt: str,
    samples: list[str],
) -> dict[str, Any]:
    """Request JSON with regex_pattern, explanation, warnings from the chat model."""
    payload = {
        "column_name": column_name,
        "user_request": user_prompt,
        "example_cell_values": samples,
    }
    user_message = (
        "Produce regex_pattern, explanation, and warnings for this task.\n"
        + json.dumps(payload, ensure_ascii=False)
    )

    client_kwargs: dict[str, str] = {"api_key": settings.OPENAI_API_KEY}
    if settings.OPENAI_BASE_URL:
        client_kwargs["base_url"] = settings.OPENAI_BASE_URL

    client = OpenAI(**client_kwargs)

    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=800,
        )
    except Exception as exc:
        raise LlmInvocationError(
            "The language model request failed. Please try again in a moment."
        ) from exc

    content = response.choices[0].message.content
    if not content or not content.strip():
        raise LlmInvocationError("The language model returned an empty response.")

    return _parse_json_object(content)


def normalize_llm_regex_payload(data: dict[str, Any]) -> tuple[str, str, list[str]]:
    """Validate shapes; raise LlmInvocationError if the model output is unusable."""
    raw_pattern = data.get("regex_pattern")
    if not isinstance(raw_pattern, str) or not raw_pattern.strip():
        raise LlmInvocationError(
            "The language model did not return a usable regex pattern."
        )

    explanation = data.get("explanation")
    if isinstance(explanation, str):
        explanation = explanation.strip()
    else:
        explanation = ""

    warnings_raw = data.get("warnings")
    warnings: list[str]
    if warnings_raw is None:
        warnings = []
    elif isinstance(warnings_raw, str):
        warnings = [warnings_raw.strip()] if warnings_raw.strip() else []
    elif isinstance(warnings_raw, list):
        warnings = [str(w).strip() for w in warnings_raw if str(w).strip()]
    else:
        warnings = [str(warnings_raw).strip()]

    return raw_pattern.strip(), explanation, warnings
