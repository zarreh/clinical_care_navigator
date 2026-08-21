"""Build the education store from public-domain NLM services.

This is the script that decides whether the app has a thesis (docs/PLAN.md §4.2).
Every citation the assistant emits has to point at a page a patient can actually
open, so education content is **fetched**, never generated:

- **MedlinePlus Connect** maps a LOINC code to the matching lab-test page and an
  RxCUI to the matching drug page. That is the `source_id -> citation_url` link,
  done properly.
- **RxNav** normalises a Synthea prescription RxCUI (usually a fully specified
  clinical drug) to its **ingredient**, which is the concept MedlinePlus keys its
  drug pages on. Brand/generic resolution comes free with it.

Three rules this script enforces rather than assumes:

1. **A code with no vetted page becomes a declared gap**, recorded in the store.
   It is never filled with a similar test and never with generated text.
2. **Every emitted citation URL is verified reachable** before the build passes.
   An unreachable citation fails launch gate §11.8, so it fails the build.
3. **The cache is a build artifact, not a corpus.** Only what the service
   returned is stored, with `retrieved_at`, inside NLM's recommended 12–24 hour
   window. It is gitignored and never published (NOTICE.md).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent
DEFAULT_RECORDS_DB = DATA_DIR / "records.db"
DEFAULT_EDUCATION_DB = DATA_DIR / "education.db"
CACHE_DIR = DATA_DIR / "education_cache"
COVERAGE_REPORT = DATA_DIR / "education_coverage.json"

CONNECT_URL = "https://connect.medlineplus.gov/service"
RXNAV_URL = "https://rxnav.nlm.nih.gov/REST"

# HL7 OIDs, as MedlinePlus Connect requires them.
LOINC_OID = "2.16.840.1.113883.6.1"
RXCUI_OID = "2.16.840.1.113883.6.88"

# NOTICE.md records the verified terms. Connect allows 100 requests/minute and
# RxNav 20/second; both are held well below the ceiling because a build has no
# reason to race.
CONNECT_MIN_INTERVAL = 0.7
RXNAV_MIN_INTERVAL = 0.2

# NLM recommends caching for 12–24 hours. The build sits at the conservative end.
CACHE_TTL = timedelta(hours=12)

CONTACT_EMAIL = "noreply@zarreh.ai"
TOOL_NAME = "clinical-care-navigator-build"
USER_AGENT = f"{TOOL_NAME}/0.1 ({CONTACT_EMAIL})"

SCHEMA = """
CREATE TABLE education_pages (
    code_system  TEXT NOT NULL,
    code         TEXT NOT NULL,
    title        TEXT NOT NULL,
    url          TEXT NOT NULL,
    summary_html TEXT NOT NULL,
    attribution  TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    PRIMARY KEY (code_system, code, url)
);

CREATE TABLE coverage_gaps (
    code_system TEXT NOT NULL,
    code        TEXT NOT NULL,
    label       TEXT NOT NULL,
    checked_at  TEXT NOT NULL,
    PRIMARY KEY (code_system, code)
);

CREATE TABLE rxcui_normalisation (
    source_rxcui     TEXT PRIMARY KEY,
    ingredient_rxcui TEXT,
    ingredient_name  TEXT,
    resolved_at      TEXT NOT NULL
);

CREATE INDEX idx_pages_code ON education_pages(code_system, code);
"""


class RateLimiter:
    """A minimum interval between calls to one host."""

    def __init__(self, min_interval: float) -> None:
        self._min_interval = min_interval
        self._last = 0.0

    def wait(self) -> None:
        elapsed = time.monotonic() - self._last
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last = time.monotonic()


@dataclass(frozen=True)
class Page:
    code_system: str
    code: str
    title: str
    url: str
    summary_html: str
    attribution: str
    retrieved_at: str


def _get_json(url: str, limiter: RateLimiter) -> dict[str, Any]:
    limiter.wait()
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - fixed https hosts
        payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
    return payload


def _cache_path(code_system: str, code: str) -> Path:
    safe = urllib.parse.quote(code, safe="")
    return CACHE_DIR / code_system / f"{safe}.json"


def _cached(code_system: str, code: str) -> dict[str, Any] | None:
    path = _cache_path(code_system, code)
    if not path.exists():
        return None
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    retrieved = datetime.fromisoformat(payload["retrieved_at"])
    if datetime.now(UTC) - retrieved > CACHE_TTL:
        return None
    return payload


def _cache(code_system: str, code: str, response: dict[str, Any]) -> dict[str, Any]:
    payload = {"retrieved_at": datetime.now(UTC).isoformat(), "response": response}
    path = _cache_path(code_system, code)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _text(node: Any) -> str:
    if isinstance(node, dict):
        return str(node.get("_value", ""))
    return str(node or "")


def connect_lookup(code_system: str, oid: str, code: str, limiter: RateLimiter) -> list[Page]:
    """Ask MedlinePlus Connect for the pages matching one code."""
    payload = _cached(code_system, code)
    if payload is None:
        query = urllib.parse.urlencode(
            {
                "mainSearchCriteria.v.cs": oid,
                "mainSearchCriteria.v.c": code,
                "knowledgeResponseType": "application/json",
                "informationRecipient.languageCode.c": "en",
            }
        )
        payload = _cache(code_system, code, _get_json(f"{CONNECT_URL}?{query}", limiter))

    retrieved_at = str(payload["retrieved_at"])
    feed = payload["response"].get("feed", {})
    pages: list[Page] = []
    for entry in _as_list(feed.get("entry")):
        links = _as_list(entry.get("link"))
        url = next((str(link.get("href", "")) for link in links if link.get("href")), "")
        if not url:
            continue
        pages.append(
            Page(
                code_system=code_system,
                code=code,
                title=_text(entry.get("title")),
                url=url,
                summary_html=_text(entry.get("summary")),
                attribution=_text(_as_list(entry.get("author"))[0].get("name"))
                if _as_list(entry.get("author"))
                else "U.S. National Library of Medicine",
                retrieved_at=retrieved_at,
            )
        )
    return pages


def rxnav_ingredient(rxcui: str, limiter: RateLimiter) -> tuple[str | None, str | None]:
    """Normalise a prescription RxCUI to its ingredient RxCUI.

    Synthea records the fully specified clinical drug ("metformin 500 MG Oral
    Tablet"); MedlinePlus keys its drug pages on the ingredient. Without this
    step most medications would look like coverage gaps when the gap is really a
    granularity mismatch — a wrong number in the honest direction is still wrong.
    """
    payload = _cached("rxnav", rxcui)
    if payload is None:
        url = f"{RXNAV_URL}/rxcui/{urllib.parse.quote(rxcui)}/related.json?tty=IN"
        try:
            payload = _cache("rxnav", rxcui, _get_json(url, limiter))
        except urllib.error.HTTPError as error:
            if error.code == 404:
                payload = _cache("rxnav", rxcui, {})
            else:
                raise

    groups = payload["response"].get("relatedGroup", {}).get("conceptGroup", [])
    for group in _as_list(groups):
        for concept in _as_list(group.get("conceptProperties")):
            return str(concept.get("rxcui")), str(concept.get("name"))
    return None, None


def url_is_reachable(url: str, limiter: RateLimiter) -> bool:
    limiter.wait()
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:  # noqa: S310
            return 200 <= int(response.status) < 400
    except urllib.error.HTTPError as error:
        return 200 <= error.code < 400
    except (urllib.error.URLError, TimeoutError):
        return False


def wanted_codes(records_db: Path) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    connection = sqlite3.connect(records_db)
    try:
        labs = connection.execute(
            "SELECT DISTINCT loinc_code, description FROM observations "
            "WHERE category = 'laboratory' ORDER BY loinc_code"
        ).fetchall()
        medications = connection.execute(
            "SELECT DISTINCT rxcui, description FROM medications ORDER BY rxcui"
        ).fetchall()
    finally:
        connection.close()
    return [(str(a), str(b)) for a, b in labs], [(str(a), str(b)) for a, b in medications]


def build(records_db: Path, education_db: Path, *, verify_urls: bool) -> dict[str, Any]:
    labs, medications = wanted_codes(records_db)
    connect_limiter = RateLimiter(CONNECT_MIN_INTERVAL)
    rxnav_limiter = RateLimiter(RXNAV_MIN_INTERVAL)

    pages: list[Page] = []
    gaps: list[tuple[str, str, str, str]] = []
    normalisations: list[tuple[str, str | None, str | None, str]] = []
    now = datetime.now(UTC).isoformat()

    print(f"  labs      {len(labs)} distinct LOINC codes")
    for index, (code, label) in enumerate(labs, start=1):
        found = connect_lookup("loinc", LOINC_OID, code, connect_limiter)
        pages.extend(found)
        if not found:
            gaps.append(("loinc", code, label, now))
        if index % 25 == 0:
            print(f"    ...{index}/{len(labs)}")

    print(f"  meds      {len(medications)} distinct RxCUIs")
    for index, (rxcui, label) in enumerate(medications, start=1):
        found = connect_lookup("rxcui", RXCUI_OID, rxcui, connect_limiter)
        ingredient_rxcui, ingredient_name = None, None
        if not found:
            ingredient_rxcui, ingredient_name = rxnav_ingredient(rxcui, rxnav_limiter)
            if ingredient_rxcui:
                for page in connect_lookup("rxcui", RXCUI_OID, ingredient_rxcui, connect_limiter):
                    # Attribute the page to the prescription the patient actually has.
                    found.append(
                        Page(
                            code_system="rxcui",
                            code=rxcui,
                            title=page.title,
                            url=page.url,
                            summary_html=page.summary_html,
                            attribution=page.attribution,
                            retrieved_at=page.retrieved_at,
                        )
                    )
        normalisations.append((rxcui, ingredient_rxcui, ingredient_name, now))
        pages.extend(found)
        if not found:
            gaps.append(("rxcui", rxcui, label, now))
        if index % 25 == 0:
            print(f"    ...{index}/{len(medications)}")

    unreachable: list[str] = []
    if verify_urls:
        distinct_urls = sorted({page.url for page in pages})
        print(f"  verify    {len(distinct_urls)} distinct citation URLs")
        for url in distinct_urls:
            if not url_is_reachable(url, connect_limiter):
                unreachable.append(url)

    if unreachable:
        raise SystemExit(
            "Unreachable citation URLs — launch gate §11.8 requires every emitted "
            "citation to resolve:\n  " + "\n  ".join(unreachable)
        )

    education_db.parent.mkdir(parents=True, exist_ok=True)
    education_db.unlink(missing_ok=True)
    connection = sqlite3.connect(education_db)
    try:
        connection.executescript(SCHEMA)
        connection.executemany(
            "INSERT OR REPLACE INTO education_pages VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    p.code_system,
                    p.code,
                    p.title,
                    p.url,
                    p.summary_html,
                    p.attribution,
                    p.retrieved_at,
                )
                for p in pages
            ],
        )
        connection.executemany("INSERT OR REPLACE INTO coverage_gaps VALUES (?, ?, ?, ?)", gaps)
        connection.executemany(
            "INSERT OR REPLACE INTO rxcui_normalisation VALUES (?, ?, ?, ?)", normalisations
        )
        connection.commit()
    finally:
        connection.close()

    covered_labs = len({p.code for p in pages if p.code_system == "loinc"})
    covered_meds = len({p.code for p in pages if p.code_system == "rxcui"})
    report = {
        "generated_at": now,
        "labs": {
            "requested": len(labs),
            "covered": covered_labs,
            "gaps": len(labs) - covered_labs,
            "coverage": round(covered_labs / len(labs), 4) if labs else 0.0,
        },
        "medications": {
            "requested": len(medications),
            "covered": covered_meds,
            "gaps": len(medications) - covered_meds,
            "coverage": round(covered_meds / len(medications), 4) if medications else 0.0,
            "normalised_via_rxnav": sum(1 for _, ing, _, _ in normalisations if ing),
        },
        "pages": len(pages),
        "distinct_urls": len({p.url for p in pages}),
        "urls_verified": verify_urls,
        "unreachable_urls": unreachable,
    }
    COVERAGE_REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records-db", type=Path, default=DEFAULT_RECORDS_DB)
    parser.add_argument("--education-db", type=Path, default=DEFAULT_EDUCATION_DB)
    parser.add_argument(
        "--skip-url-verification",
        action="store_true",
        help="Skip the reachability pass. For local iteration only; CI must not use it.",
    )
    args = parser.parse_args(argv)

    print("fetch_education")
    report = build(args.records_db, args.education_db, verify_urls=not args.skip_url_verification)
    labs, meds = report["labs"], report["medications"]
    print(f"  pages     {report['pages']} across {report['distinct_urls']} distinct URLs")
    print(f"  labs      {labs['covered']}/{labs['requested']} covered ({labs['coverage']:.0%})")
    print(f"  meds      {meds['covered']}/{meds['requested']} covered ({meds['coverage']:.0%})")
    print(f"  gaps      {labs['gaps']} labs, {meds['gaps']} medications — declared, never filled")
    print(f"  report    {COVERAGE_REPORT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
