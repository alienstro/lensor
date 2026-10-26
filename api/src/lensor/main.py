from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from lensor.routes import chat, contracts, health

app = FastAPI(title="Lensor")
app.state.limiter = chat.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.include_router(health.router)
app.include_router(contracts.router)
app.include_router(chat.router)
