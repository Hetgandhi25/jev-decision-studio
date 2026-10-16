import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder

from app.config import settings
from app.schemas import SystemOneRequest, DecisionsRequest, SystemOneResponse
from app.ollaya_client import ollaya_client
from app.ollama_fallback import ollama_fallback

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("decision-gateway")

DEMO_HTML_PATH = "/home/het/decision-service/demo/index.html"

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Jev Decision Gateway on %s:%s", settings.HOST, settings.PORT)
    ollaya_alive = await ollaya_client.check_health()
    ollama_alive = await ollama_fallback.check_health()
    logger.info("Backend status: Ollaya=%s (port 11435), Ollama=%s (port 11434)", ollaya_alive, ollama_alive)
    yield
    logger.info("Shutting down Decision Gateway")

app = FastAPI(
    title="Local Jev Decision Gateway",
    description="High-performance, free, local Jev-style decision API proxy for NVIDIA DGX Spark",
    version="1.0.1",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def enforce_payload_limit(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.MAX_REQUEST_SIZE_BYTES:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={"error": "Payload exceeds maximum allowed size", "max_bytes": settings.MAX_REQUEST_SIZE_BYTES}
        )
    return await call_next(request)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    safe_errors = jsonable_encoder(exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "Invalid request schema", "code": "VALIDATION_ERROR", "detail": safe_errors}
    )

@app.get("/", response_class=HTMLResponse)
@app.get("/demo", response_class=HTMLResponse)
async def serve_demo():
    if os.path.exists(DEMO_HTML_PATH):
        with open(DEMO_HTML_PATH, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    return HTMLResponse("<h2>Demo UI index.html not found</h2>", status_code=404)

@app.get("/health")
async def health_check():
    ollaya_ok = await ollaya_client.check_health()
    ollama_ok = await ollama_fallback.check_health()
    is_healthy = ollaya_ok or ollama_ok
    status_code = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if is_healthy else "degraded",
            "ollaya_primary": "up" if ollaya_ok else "down",
            "ollama_fallback": "up" if ollama_ok else "down",
            "gateway": "ready"
        }
    )

@app.get("/v1/models")
async def list_models():
    try:
        data = await ollaya_client.get_models()
        models = data.get("models", [])
    except Exception as e:
        logger.warning("Could not reach Ollaya for model list: %s", e)
        models = []

    models.append({
        "name": f"fallback:{settings.FALLBACK_MODEL}",
        "description": "Autoregressive LLM fallback via local Ollama (uncalibrated estimates)",
        "capabilities": ["choice", "noul", "score"]
    })
    return {"models": models}

async def process_decision(state: str, questions_dict: dict, requested_model: str = None) -> JSONResponse:
    simulated_fallback = requested_model in ("force-fallback", "fallback:nemotron-3-nano:4b", "fallback")
    
    if not simulated_fallback:
        target_model = requested_model or settings.DEFAULT_DECISION_MODEL
        ollaya_payload = {
            "model": target_model,
            "state": state,
            "questions": questions_dict
        }

        success, res_data, latency_ms = await ollaya_client.decide_systemone(ollaya_payload)
        if success:
            res_data["decision_meta"] = {
                "backend": "ollaya",
                "model_used": target_model,
                "is_calibrated": False,
                "confidence_type": "forward_pass_normalized",
                "calibration_note": "Model probabilities are normalized. Statistical calibration has not yet been established.",
                "runtime_device": "cpu (ARM64 onnxruntime fp32)",
                "latency_ms": round(latency_ms, 2)
            }
            return JSONResponse(status_code=status.HTTP_200_OK, content=res_data)

        if not settings.FALLBACK_ENABLED:
            logger.error("Ollaya primary failed and fallback is disabled: %s", res_data)
            return JSONResponse(
                status_code=res_data.get("status_code", status.HTTP_502_BAD_GATEWAY),
                content={"error": "Primary decision runtime unavailable", "upstream": res_data}
            )
        primary_failure_reason = res_data
    else:
        primary_failure_reason = {"notice": "Simulated primary outage (user forced fallback demo)"}

    # Fallback path to Ollama
    logger.warning("Engaging Ollama fallback (%s)...", settings.FALLBACK_MODEL)
    fb_success, fb_data, fb_latency_ms = await ollama_fallback.decide_all(
        state=state,
        questions=questions_dict,
        model_name=settings.FALLBACK_MODEL
    )

    if fb_success:
        fb_data["decision_meta"] = {
            "backend": "ollama_fallback",
            "model_used": settings.FALLBACK_MODEL,
            "is_calibrated": False,
            "confidence_type": "heuristic_uncalibrated",
            "calibration_note": "Uncalibrated heuristic estimates via autoregressive LLM fallback.",
            "runtime_device": "local ollama (port 11434)",
            "latency_ms": round(fb_latency_ms, 2),
            "primary_failure": primary_failure_reason
        }
        return JSONResponse(status_code=status.HTTP_200_OK, content=fb_data)

    logger.critical("Both Ollaya primary and Ollama fallback failed!")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": "Both primary decision runtime and fallback backend failed",
            "primary_error": primary_failure_reason,
            "fallback_error": fb_data
        }
    )

@app.post("/v1/systemone", response_model=SystemOneResponse)
async def systemone_endpoint(req: SystemOneRequest):
    questions_dict = {k: v.model_dump(exclude_none=True) for k, v in req.questions.items()}
    return await process_decision(req.state, questions_dict, req.model)

@app.post("/v1/decisions", response_model=SystemOneResponse)
async def decisions_endpoint(req: DecisionsRequest):
    input_text = req.input or req.state
    questions_dict = {k: v.model_dump(exclude_none=True) for k, v in req.questions.items()}
    return await process_decision(input_text, questions_dict, req.model)

@app.post("/api/v1/decide", response_model=SystemOneResponse)
async def api_decide_endpoint(req: SystemOneRequest):
    questions_dict = {k: v.model_dump(exclude_none=True) for k, v in req.questions.items()}
    return await process_decision(req.state, questions_dict, req.model)
