from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, portfolio, user, trade, holding
from app.core.config import settings
from app import models  # noqa: F401 - ensures all models are registered before mappers configure

app = FastAPI(title="Portfolio Tracker")

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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
