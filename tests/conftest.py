from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from navigator.store import EducationStore, PolicyStore, RecordStore
from tests.fixtures import FixtureStores, build_fixture_stores


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
