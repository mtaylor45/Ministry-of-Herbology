"""API entrypoint.

Workstream A owns this module and the contract it serves. The routers it mounts
are owned by C, D, E, F, G, H and K; each ships fixture-backed mocks until its
real implementation lands (ADR 0003, rule 3).
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Workstream D's routes live under workers/, which the API image puts on
# PYTHONPATH alongside api/ (ADR 0011 §4).
from workers.botany.router import router as botany_router

from almanac.router import router as almanac_router
from app.log_redaction import install as install_log_redaction
from app.settings import get_settings
from grounds.router import router as grounds_router
from inventory.router import router as inventory_router
from tending.router import router as tending_router

CONTRACT_VERSION = (
    (Path(__file__).resolve().parents[2] / "contracts" / "VERSION").read_text().strip()
)

# The calendar token rides in the URL because Google's and Apple's fetchers
# carry no session (ADR 0019). Redact it out of the access log before anything
# serves a request, so the promise that it "is never logged" is true of this
# process and not only of the package that issues it.
install_log_redaction()

app = FastAPI(
    title="The Ministry of Herbology API",
    version=CONTRACT_VERSION,
    description="Implementation of contracts/openapi/openapi.yaml.",
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(inventory_router, prefix="/api/v1")
app.include_router(botany_router, prefix="/api/v1")
app.include_router(almanac_router, prefix="/api/v1")
app.include_router(tending_router, prefix="/api/v1")
app.include_router(grounds_router, prefix="/api/v1")


@app.get("/api/v1/healthz", tags=["platform"])
async def healthz() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "contract_version": CONTRACT_VERSION,
        "mode": "mock" if settings.mock_mode else "live",
    }
