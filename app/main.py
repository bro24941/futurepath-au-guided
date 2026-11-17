"""Serve the website and the six-agent workflow on the local computer."""
import logging
import os
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.llm import GoalLLM, Settings
from app.models import Opportunity, PathwayRequest, PathwayResponse
from app.orchestrator import build_pathway
from data.validate import load_records, validate

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def create_app(llm: GoalLLM | None = None) -> FastAPI:
    """Load the catalogue once and share the Gemini client across requests."""
    service = llm or GoalLLM(Settings.from_env())
    records = load_records()
    fixed_date = os.getenv("AS_OF_DATE")
    assessment_date = date.fromisoformat(fixed_date) if fixed_date else None
    problems, _ = validate()
    if problems:
        raise ValueError("Dataset validation failed. Run python -m data.validate.")

    @asynccontextmanager
    async def lifespan(api):
        service.startup_check()
        yield
        service.close()

    api = FastAPI(title="FuturePath AU", lifespan=lifespan, docs_url=None, redoc_url=None)
    api.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])

    @api.middleware("http")
    async def boundaries(request: Request, call_next):
        # Only the local page should submit the form, and submissions are small.
        if request.method == "POST":
            origin = request.headers.get("origin")
            if origin and origin != str(request.base_url).rstrip("/"):
                return JSONResponse({"detail": "Use the local FuturePath AU page."}, status_code=403)
            chunks, size = [], 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > 16000:
                    return JSONResponse({"detail": "That request is too large. Shorten the goal and try again."}, status_code=413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers.update({"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer", "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"})
        return response

    @api.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # FastAPI's default detail echoes inputs, which could contain accidental personal text.
        return JSONResponse({"detail": "Check the goal, consent boxes and profile fields. Only fictitious adult profiles are accepted."}, status_code=422)

    @api.exception_handler(Exception)
    async def safe_error(request, exc):
        return JSONResponse({"detail": "We couldn’t check this goal. Try again, or reopen the website if the problem continues."}, status_code=500)

    @api.get("/api/health")
    def health():
        # The launcher waits for this marker before opening the default browser.
        return {"status": "ok", "app": "futurepath-au-guided", "llm_mode": service.settings.mode,
                "configured_model": service.settings.model, "fallback_model": service.settings.fallback,
                "api_key_configured": bool(service.settings.api_key), "records": len(records),
                "as_of_date": (assessment_date or date.today()).isoformat()}

    @api.get("/api/opportunities", response_model=list[Opportunity])
    def catalogue():
        return records

    @api.get("/api/opportunities/{opportunity_id}", response_model=Opportunity)
    def detail(opportunity_id: str):
        match = next((r for r in records if r.id == opportunity_id), None)
        if match is None:
            raise HTTPException(404, "Opportunity not found.")
        return match

    @api.post("/api/pathway", response_model=PathwayResponse)
    def pathway(request: PathwayRequest):
        # The form has already passed consent and profile checks by this point.
        return build_pathway(request, records, service, assessment_date or date.today())

    @api.get("/")
    def index():
        return FileResponse(ROOT / "static/index.html")

    @api.get("/favicon.ico", include_in_schema=False)
    def favicon():
        return Response(status_code=204)

    api.mount("/static", StaticFiles(directory=ROOT / "static", check_dir=False), name="static")
    return api


app = create_app()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("google_genai").setLevel(logging.WARNING)
    uvicorn.run(app, host="127.0.0.1", port=8000, access_log=False)
