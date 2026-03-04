"""RentRadar API — FastAPI application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rentradar.database import engine
from rentradar.routers import health, sse


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    yield
    await engine.dispose()


app = FastAPI(
    title="RentRadar API",
    description="Rental Intelligence Platform — NYC listings, scoring, and alerts",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(sse.router)
