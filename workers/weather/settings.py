"""Runtime configuration for the weather worker — Workstream E.

Mirrors ``api/app/settings.py`` and ``workers/botany/settings.py`` so one
``.env`` configures the whole stack: the same ``MOH_`` prefix, the same
``mock_mode`` default.

The extra keys here are E's own. Two of them decide how honest the engines can
be about their own inputs, so they are worth reading rather than skimming:

``stale_after_hours``
    How old the newest stored observation may be before the water balance
    stops calling itself current. Under ADR 0010 nothing measures the soil, so
    a stalled ingest is not a cosmetic problem — it is the deficit quietly
    freezing while the plant goes on drying.

``max_gap_days``
    How many days of missing ET₀ a balance series may carry before its answer
    is reported as ``unknown`` rather than merely degraded. ADR 0016 gives us a
    local fallback so a gap is rare; this is what happens when even that fails.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Sent on every outbound request. NWS requires a contact address in the
#: User-Agent and will refuse traffic without one; Open-Meteo merely deserves it.
DEFAULT_USER_AGENT = (
    "MinistryOfHerbology/1.0 (self-hosted plant care; "
    "+https://github.com/mtaylor45/ministry-of-herbology)"
)


class WeatherSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MOH_", env_file=".env", extra="ignore")

    #: With no network (or no database) the worker answers from the recordings
    #: and the frozen fixtures, so the whole stack runs offline (ADR 0003).
    mock_mode: bool = True
    fixtures_dir: Path = REPO_ROOT / "fixtures"

    user_agent: str = DEFAULT_USER_AGENT
    http_timeout_s: float = 15.0
    #: Minimum gap between two calls to the same host.
    min_request_interval_s: float = 0.2

    open_meteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    open_meteo_archive_url: str = "https://archive-api.open-meteo.com/v1/archive"
    nws_base_url: str = "https://api.weather.gov"

    #: The plan asks for a 1-day hourly and 10-day daily forecast.
    forecast_days: int = 10
    #: Hours of recent actuals to pull alongside the forecast. Open-Meteo's
    #: ``past_days`` re-serves them once they are measured, which is how a
    #: forecast hour becomes an observation without a second API.
    observation_past_days: int = 2

    #: The frost guard's window. The plan fixes it at 72 hours.
    frost_lookahead_hours: int = 72

    stale_after_hours: float = 6.0
    max_gap_days: int = 3


@lru_cache
def get_settings() -> WeatherSettings:
    return WeatherSettings()
