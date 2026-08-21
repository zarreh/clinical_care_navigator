from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

AutonomyLevel = Literal["L1_conservative", "L2_balanced", "L3_permissive"]


class Settings(BaseSettings):
    """Application configuration, sourced from the environment."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="NAVIGATOR_", extra="ignore")

    environment: str = "development"
    openai_api_key: str = ""

    langsmith_api_key: str = ""
    langsmith_project: str = "clinical-care-navigator"

    data_dir: str = "data"
    record_db_path: str = "data/records.db"
    education_db_path: str = "data/education.db"
    policy_db_path: str = "data/policy.db"
    run_store_path: str = "data/runs.db"

    # docs/PLAN.md §5.9 — moves the inform/recommend boundary only, never the
    # escalation boundary.
    autonomy_level: AutonomyLevel = "L2_balanced"

    # docs/PLAN.md §5.5 — a clinical answer is truncated conservatively, never silently.
    max_tool_calls: int = 12
    max_evidence_passes: int = 1
    max_run_seconds: float = 90.0
    citation_coverage_floor: float = 1.0

    rate_limit_per_minute: int = 20
    max_request_body_bytes: int = 8_192


@lru_cache
def get_settings() -> Settings:
    return Settings()
