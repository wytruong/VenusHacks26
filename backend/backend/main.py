from fastapi import FastAPI

from backend.routers.screening import router as screening_router

app = FastAPI(title="VenusHacks Screening API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "venus-hacks-backend"}


app.include_router(screening_router)
