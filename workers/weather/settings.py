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

``weather_scenario`` / ``weather_scenario_day``
    Which recorded weather this deployment is standing in, and which day of it
    is "today". Both are operator inputs in the sense ADR 0019 means: a
    parameter with no usable default, unset in every shipped deployment, and
    the app runs on the baseline recording until somebody sets one. They are
    **not** a test hook. An operator who wants to watch 38 mm of rain clear a
    due watering before trusting the app with their garden takes exactly this
    path, and so does Workstream L's end-to-end suite; a second, private route
    for the suite would prove only that the private route works.

    Both are read by the API *and* by the worker, from the same settings
    object, so the endpoint and the job that writes ``water_balance`` cannot
    disagree about what the weather was.
"""

from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Sent on every outbound request. NWS requires a contact address in the
#: User-Agent and will refuse traffic without one; Open-Meteo merely deserves it.
DEFAULT_USER_AGENT = (
    "MinistryOfHerbology/1.0 (self-hosted plant care; "
    "+https://github.com/mtaylor45/ministry-of-herbology)"
)


class WeatherSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MOH_", env_file=".env", extra="ignore"
    )

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

    #: Name of a file in ``fixtures/scenarios/``, without the extension —
    #: ``drought``, ``storm`` or ``frost`` today, and whatever L adds next.
    #: ``None`` (the shipped default) means the baseline recording, which is
    #: what every deployment gets until an operator asks for something else.
    weather_scenario: str | None = None

    #: Which day of that recording is "today". The water balance is a history
    #: ending now, so a scenario replayed past its rain shows the deficit that
    #: has since rebuilt — which is correct, and is not what somebody wanting to
    #: *see* the rain land is asking for. Unset means the recording's last day.
    weather_scenario_day: date | None = None

    @field_validator("weather_scenario")
    @classmethod
    def _scenario_is_a_plain_name(cls, value: str | None) -> str | None:
        """A scenario name becomes a path, so it may only be a bare name.

        ``fixtures_dir / f"scenarios/{value}.json"`` with a value of
        ``../../etc/passwd`` reads whatever the API process can read. The
        setting is an operator's, not a request's, so this is a guard rail
        rather than a security boundary — but a guard rail on the one line in
        this package that turns configuration into a filesystem path is cheap.
        """
        if value is None:
            return None
        name = value.strip()
        if not name:
            return None
        if not name.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                "MOH_WEATHER_SCENARIO must be a plain fixture name such as "
                f"'storm' (letters, digits, '-' and '_'), not {value!r}"
            )
        return name


@lru_cache
def get_settings() -> WeatherSettings:
    return WeatherSettings()
