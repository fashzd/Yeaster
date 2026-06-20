"""Yeaster API application factory.

Router-structured FastAPI app. Run with::

    uvicorn yeaster.api.app:app --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from yeaster import __version__
from yeaster.api.routers import agent, chat, daemon, health, market, proof, skills, wallet, x402


def create_app() -> FastAPI:
    app = FastAPI(
        title="Yeaster",
        version=__version__,
        summary="Autonomous BNB momentum trading agent — single mind, orchestrated stages.",
    )

    # The web client is a separate origin in dev; allow it broadly here.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api")
    app.include_router(agent.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")
    app.include_router(wallet.router, prefix="/api")
    app.include_router(market.router, prefix="/api")
    app.include_router(proof.router, prefix="/api")
    app.include_router(daemon.router, prefix="/api")
    app.include_router(x402.router, prefix="/api")
    app.include_router(skills.router, prefix="/api")

    @app.on_event("startup")
    def _resume() -> None:
        from yeaster.runtime.daemon import auto_resume
        auto_resume()

    return app


app = create_app()
