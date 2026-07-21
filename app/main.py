from fastapi import FastAPI

from app.api.routes import auth, portfolio

app = FastAPI(title="Portfolio Tracker")

app.include_router(auth.router)
app.include_router(portfolio.router)