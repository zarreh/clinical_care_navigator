from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from navigator.store import EducationStore, PolicyStore, RecordStore
from tests.fixtures import FixtureStores, build_fixture_stores

if TYPE_CHECKING:
    from navigator.tools import ScopedToolExecutor, ToolRegistry


@pytest.fixture(scope="session")
def stores(tmp_path_factory: pytest.TempPathFactory) -> FixtureStores:
    return build_fixture_stores(tmp_path_factory.mktemp("fixture-stores"))


@pytest.fixture
def record_store(stores: FixtureStores) -> Iterator[RecordStore]:
    store = RecordStore(stores.records_db)
    yield store
    store.close()


@pytest.fixture
def education_store(stores: FixtureStores) -> Iterator[EducationStore]:
    store = EducationStore(stores.education_db)
    yield store
    store.close()


@pytest.fixture
def policy_store(stores: FixtureStores) -> Iterator[PolicyStore]:
    store = PolicyStore(stores.policy_db)
    yield store
    store.close()


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def patient_ids(stores: FixtureStores) -> list[str]:
    return list(stores.patient_ids)


@pytest.fixture
def registry(record_store: RecordStore, education_store: EducationStore) -> ToolRegistry:
    from navigator.tools import build_registry

    return build_registry(record_store, education_store)


@pytest.fixture
def executor(registry: ToolRegistry) -> ScopedToolExecutor:
    from navigator.tools import ScopedToolExecutor

    # A fixed clock keeps evidence timestamps deterministic in assertions.
    return ScopedToolExecutor(registry, now=lambda: "2026-08-20T00:00:00+00:00")
