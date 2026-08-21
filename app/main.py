import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, demo, portfolio, user, trade, holding
from app.core.config import settings
from app.core.scheduler import start_scheduler, stop_scheduler
from app import models  # noqa: F401 - ensures all models are registered before mappers configure

# No logging is configured by default (Python's logging drops INFO records with
# no handler attached), which would leave background jobs like the price
# scheduler invisible. This is a no-op if a handler is already configured
# (e.g. when running under a WSGI/ASGI host that sets its own).
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Portfolio Tracker", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(portfolio.router)
app.include_router(user.router)
app.include_router(trade.router)
app.include_router(holding.router)
app.include_router(demo.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
