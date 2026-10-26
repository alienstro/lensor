from fastapi import FastAPI

from lensor.routes import health

app = FastAPI(title="Lensor")
app.include_router(health.router)
