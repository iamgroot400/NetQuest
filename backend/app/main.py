"""NetQuest API.

The simulation engine under `app/simulation/` has no dependency on FastAPI —
this module only exposes it over HTTP.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1 import router as v1_router
from .core.config import settings

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description=(
        "Backend for NetQuest, an open-source network simulator. "
        "The frontend owns the topology document and sends it with every "
        "request, so these endpoints are pure functions over a network."
    ),
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router, prefix=settings.api_prefix)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "version": settings.version,
        "docs": "/docs",
        "api": settings.api_prefix,
    }
