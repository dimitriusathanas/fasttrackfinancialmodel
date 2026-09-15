"""Market research tab: ask Claude to web-search current market conditions.

Falls back to a plain Google search link if no API key is configured.
"""
from __future__ import annotations

import os
import urllib.parse

import anthropic

MODEL = "claude-opus-4-7"


def _get_api_key() -> str | None:
    """Read the API key from the environment, or from Streamlit's secrets manager
    when running on Streamlit Community Cloud (Settings -> Secrets)."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    try:
        import streamlit as st

        return st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:
        return None


def api_key_available() -> bool:
    return bool(_get_api_key())


def google_search_url(keywords: str) -> str:
    return "https://www.google.com/search?q=" + urllib.parse.quote(keywords)


def run_market_research(keywords: str, context: str = "") -> str:
    """Call Claude with the server-side web_search tool to research market conditions.

    `keywords` are the user-selected search terms. `context` is optional extra
    context (e.g. the company's industry) to help Claude target the search.
    Returns the assembled text response, including inline citations where available.
    """
    client = anthropic.Anthropic(api_key=_get_api_key())

    prompt = (
        "You are helping a finance team assess current market conditions that could "
        "affect their forecasted revenue and cost growth rates. "
        f"Research the following topic using web search: {keywords}. "
    )
    if context:
        prompt += f"Additional context about the business: {context}. "
    prompt += (
        "Summarize the most relevant, recent findings (last few months where possible), "
        "and explicitly call out anything that could push forecasted growth rates up or down. "
        "Keep the summary concise and organized with short headers or bullet points."
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            thinking={"type": "adaptive"},
            tools=[{"type": "web_search_20260209", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.AuthenticationError:
        return "Authentication failed. Check that ANTHROPIC_API_KEY is set correctly."
    except anthropic.RateLimitError:
        return "Rate limit reached. Please wait a moment and try again."
    except anthropic.APIConnectionError:
        return "Could not connect to the Anthropic API. Check your internet connection."
    except anthropic.APIStatusError as e:
        return f"API error ({e.status_code}): {e.message}"

    parts: list[str] = []
    for block in response.content:
        if block.type == "text":
            parts.append(block.text)
    return "\n\n".join(parts) if parts else "No response text returned."
