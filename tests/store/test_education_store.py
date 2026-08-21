"""Education store behaviour — exact lookup, and gaps that stay gaps."""

from __future__ import annotations

from urllib.parse import urlparse

from navigator.store import EducationStore, RecordStore


def test_lookup_is_exact_and_never_falls_back(education_store: EducationStore) -> None:
    """An unknown code returns nothing.

    There is deliberately no nearest-match path: substituting a similar test is
    the failure mode the declared-gap rule exists to prevent (§4.2, case 14).
    """
    assert education_store.for_loinc("99999-9") == []
    assert education_store.for_rxcui("00000") == []


def test_every_committed_citation_is_a_public_nlm_url(education_store: EducationStore) -> None:
    """Gate §11.8 in its offline form: every URL is well-formed and NLM-hosted.

    Reachability itself is verified at build time by `data/fetch_education.py`,
    which fails the build on a dead link. Asserting the host here keeps a
    fabricated or redirected citation from surviving a pull request.
    """
    urls = education_store.citation_urls()
    assert urls
    for url in urls:
        parsed = urlparse(url)
        assert parsed.scheme == "https", url
        assert parsed.netloc.endswith("medlineplus.gov") or parsed.netloc.endswith("nih.gov"), url


def test_fixture_population_labs_resolve_to_a_page_or_a_declared_gap(
    education_store: EducationStore, record_store: RecordStore
) -> None:
    """Phase 1 exit: every analyte the population carries is accounted for.

    Either it has a citable page or it is a recorded gap. What is not allowed is
    an analyte that is neither — that is the state in which an answer quietly
    invents a source.
    """
    for patient_id in record_store.patient_ids():
        for observation in record_store.observations(patient_id, limit=25):
            code = observation.loinc_code
            resolved = education_store.for_loinc(code) or education_store.gap("loinc", code)
            assert resolved, f"LOINC {code} is neither covered nor declared as a gap"


def test_pages_carry_attribution(education_store: EducationStore) -> None:
    pages = education_store.for_loinc("2823-3")
    for page in pages:
        assert page.attribution.strip()
        assert page.retrieved_at.strip()
