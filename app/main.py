from fastapi import FastAPI

from app.api.routes import auth, portfolio, user, trade
from app import models  # noqa: F401 - ensures all models are registered before mappers configure

app = FastAPI(title="Portfolio Tracker")

app.include_router(auth.router)
app.include_router(portfolio.router)
app.include_router(user.router)
app.include_router(trade.router)