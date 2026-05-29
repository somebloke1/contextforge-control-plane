#!/usr/bin/env python3
"""Local Exa MCP backend with Gemini post-processing."""

from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP


server = FastMCP("exa-search")

EXA_API_BASE = os.getenv("EXA_API_BASE", "https://api.exa.ai").rstrip("/")
GEMINI_API_BASE = os.getenv("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
REQUEST_TIMEOUT = float(os.getenv("EXA_GEMINI_TIMEOUT_SECONDS", "45"))


def _secret(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _trim(value: str | None, max_chars: int) -> str | None:
    if value is None:
        return None
    if len(value) <= max_chars:
        return value
    return value[: max(0, max_chars - 20)] + "\n...[truncated]"


def _result_summary(result: dict[str, Any], max_text_chars: int = 1200) -> dict[str, Any]:
    return {
        "title": result.get("title"),
        "url": result.get("url"),
        "publishedDate": result.get("publishedDate"),
        "author": result.get("author"),
        "id": result.get("id"),
        "text": _trim(result.get("text"), max_text_chars),
        "summary": result.get("summary"),
        "highlights": result.get("highlights") or [],
    }


def _exa_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    headers = {
        "x-api-key": _secret("EXA_API_KEY"),
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        response = client.post(f"{EXA_API_BASE}{path}", headers=headers, json=payload)
        response.raise_for_status()
        return response.json()


def _gemini_generate(prompt: str, model: str | None = None) -> str:
    selected_model = model or GEMINI_MODEL
    headers = {
        "x-goog-api-key": _secret("GEMINI_API_KEY"),
        "Content-Type": "application/json",
    }
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ]
    }
    url = f"{GEMINI_API_BASE}/models/{selected_model}:generateContent"
    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    parts: list[str] = []
    for candidate in data.get("candidates", []):
        content = candidate.get("content") or {}
        for part in content.get("parts", []):
            text = part.get("text")
            if text:
                parts.append(text)
    if not parts:
        raise RuntimeError("Gemini returned no text")
    return "\n".join(parts)


@server.tool()
def web_search_exa(
    query: str,
    numResults: int = 10,
    searchType: str = "auto",
    maxCharacters: int = 1000,
) -> dict[str, Any]:
    """Search the web with Exa and return clean result metadata plus highlights."""
    payload = {
        "query": query,
        "numResults": max(1, min(int(numResults), 20)),
        "type": searchType,
        "contents": {
            "highlights": {
                "query": query,
                "maxCharacters": max(200, min(int(maxCharacters), 4000)),
            }
        },
    }
    data = _exa_post("/search", payload)
    return {
        "requestId": data.get("requestId"),
        "resolvedSearchType": data.get("resolvedSearchType") or data.get("searchType"),
        "results": [_result_summary(item, max_text_chars=0) for item in data.get("results", [])],
        "costDollars": data.get("costDollars"),
    }


@server.tool()
def web_fetch_exa(urls: list[str], maxCharacters: int = 3000) -> dict[str, Any]:
    """Read one or more webpages with Exa and return clean markdown text."""
    payload = {
        "ids": urls,
        "contents": {
            "text": {
                "maxCharacters": max(200, min(int(maxCharacters), 20000)),
            }
        },
    }
    data = _exa_post("/contents", payload)
    return {
        "requestId": data.get("requestId"),
        "results": [_result_summary(item, max_text_chars=maxCharacters) for item in data.get("results", [])],
        "statuses": data.get("statuses", []),
        "costDollars": data.get("costDollars"),
    }


@server.tool()
def web_search_gemini_exa(
    query: str,
    numResults: int = 5,
    instructions: str = "Answer the query using only the cited search results. Include concise source citations by number.",
    model: str | None = None,
    maxCharacters: int = 12000,
) -> dict[str, Any]:
    """Search with Exa, then use Gemini to synthesize an answer from the results."""
    payload = {
        "query": query,
        "numResults": max(1, min(int(numResults), 10)),
        "type": "auto",
        "contents": {
            "text": {
                "maxCharacters": max(1000, min(int(maxCharacters), 30000)),
            }
        },
    }
    search_data = _exa_post("/search", payload)
    results = [_result_summary(item, max_text_chars=3000) for item in search_data.get("results", [])]

    source_blocks = []
    for index, result in enumerate(results, start=1):
        source_blocks.append(
            "\n".join(
                [
                    f"[{index}] {result.get('title') or 'Untitled'}",
                    f"URL: {result.get('url')}",
                    f"Published: {result.get('publishedDate') or 'unknown'}",
                    f"Text: {result.get('text') or result.get('summary') or ''}",
                ]
            )
        )
    prompt = "\n\n".join(
        [
            instructions,
            f"Query: {query}",
            "Sources:",
            "\n\n".join(source_blocks),
        ]
    )
    answer = _gemini_generate(prompt, model=model)
    return {
        "query": query,
        "answer": answer,
        "sources": [
            {
                "index": index,
                "title": result.get("title"),
                "url": result.get("url"),
                "publishedDate": result.get("publishedDate"),
            }
            for index, result in enumerate(results, start=1)
        ],
        "exaRequestId": search_data.get("requestId"),
        "geminiModel": model or GEMINI_MODEL,
        "costDollars": search_data.get("costDollars"),
    }


if __name__ == "__main__":
    server.run()
