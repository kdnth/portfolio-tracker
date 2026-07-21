from fastapi import FastAPI

from app.api.routes import auth, portfolio, user

app = FastAPI(title="Portfolio Tracker")

app.include_router(auth.router)
app.include_router(portfolio.router)
app.include_router(user.router)