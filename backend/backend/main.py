import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)

from backend.middleware.request_size import RequestSizeLimitMiddleware
from backend.routers.agents import router as agents_router
from backend.routers.ecg import router as ecg_router
from backend.routers.screening import router as screening_router

LOCAL_VITE_ORIGINS = [
    "http://localhost:45260",
    "http://127.0.0.1:45260",
]

app = FastAPI(title="VenusHacks Screening API")

app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=LOCAL_VITE_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-ID"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "venus-hacks-backend"}


app.include_router(agents_router)
app.include_router(screening_router)
app.include_router(ecg_router)
