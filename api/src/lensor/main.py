from fastapi import FastAPI

from lensor.routes import contracts, health

app = FastAPI(title="Lensor")
app.include_router(health.router)
app.include_router(contracts.router)
