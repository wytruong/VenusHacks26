from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers.screening import router as screening_router

LOCAL_VITE_ORIGINS = [
    "http://localhost:45260",
    "http://127.0.0.1:45260",
]

app = FastAPI(title="VenusHacks Screening API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=LOCAL_VITE_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "venus-hacks-backend"}


app.include_router(screening_router)
