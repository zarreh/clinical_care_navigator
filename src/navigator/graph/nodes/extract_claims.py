"""Extracts the draft's claims for post-flight citation checking (§5.3).

Runs the claim extractor over the draft *body*, plus the tool_call_ids and
education URLs the run actually recorded, so the extractor knows exactly what it
may cite. It re-derives the claims independently rather than reusing
`draft.claims`: the whole point of an independent extraction is that a draft
cannot mark an uncited clinical assertion "cited" by simply leaving it out of its
own claim list (§5.4, the narrow-projection argument).
"""

from __future__ import annotations

from collections.abc import Callable

from navigator.graph.protocols import ClaimExtractorChain
from navigator.graph.state import NavigatorState

_PAGES_KEY = "pages"
_URL_KEY = "url"


def _education_urls(state: NavigatorState) -> list[str]:
    urls: set[str] = set()
    for record in state.get("evidence", []):
        pages = record.result.get(_PAGES_KEY)
        if not isinstance(pages, list):
            continue
        for page in pages:
            if isinstance(page, dict):
                url = page.get(_URL_KEY)
                if isinstance(url, str) and url:
                    urls.add(url)
    return sorted(urls)


def build_extract_claims_node(
    claim_extractor_chain: ClaimExtractorChain,
) -> Callable[[NavigatorState], dict[str, object]]:
    def extract_claims_node(state: NavigatorState) -> dict[str, object]:
        draft = state["draft"]
        tool_call_ids = [record.tool_call_id for record in state.get("evidence", [])]
        education_urls = _education_urls(state)
        result = claim_extractor_chain.invoke(
            {
                "draft_body": draft.body,
                "tool_call_ids": "\n".join(tool_call_ids) or "(none)",
                "education_urls": "\n".join(education_urls) or "(none)",
            }
        )
        return {"claims": list(result.claims)}

    return extract_claims_node
