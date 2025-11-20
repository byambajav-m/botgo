from fastapi import APIRouter
from api.schemas import (
    WebhookPayload,
    ReviewRequest,
    ReviewResponse,
    HealthResponse
)
from tasks import review_merge_request
from config import settings
import requests
from redis import Redis

router = APIRouter()


@router.get("/")
def root():
    return {
        "service": settings.APP_NAME,
        "status": "running",
    }

@router.get("/health", response_model=HealthResponse)
def health_check():
    checks = HealthResponse(
        api="ok",
        redis="unknown",
        ollama="unknown"
    )

    try:
        r = Redis.from_url(settings.REDIS_URL)
        r.ping()
        checks.redis = "ok"
    except:
        checks.redis = "error"

    try:
        resp = requests.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=2)
        checks.ollama = "ok" if resp.status_code == 200 else "error"
    except:
        checks.ollama = "error"

    return checks

@router.post("/api/webhook")
async def gitlab_webhook(payload: WebhookPayload):
    if payload.object_kind != "merge_request":
        return {"status": "ignored", "reason": "not a merge request event"}

    mr_action = payload.object_attributes.get("action")
    if mr_action not in ["open", "update"]:
        return {"status": "ignored", "reason": f"action '{mr_action}' not reviewed"}

    project_id = payload.project["id"]
    mr_iid = payload.object_attributes["iid"]

    task = review_merge_request.delay(project_id, mr_iid)

    return ReviewResponse(
        status="queued",
        task_id=task.id,
        project_id=project_id,
        mr_iid=mr_iid
    )


@router.post("/api/review", response_model=ReviewResponse)
async def trigger_review(request: ReviewRequest):
    task = review_merge_request.delay(request.project_id, request.mr_iid)

    return ReviewResponse(
        status="queued",
        task_id=task.id,
        project_id=request.project_id,
        mr_iid=request.mr_iid
    )

@router.post("/api/test", response_model=ReviewResponse)
async def test_review(request: ReviewRequest):
    task = review_merge_request.delay(request.project_id, request.mr_iid)

    return ReviewResponse(
        status="queued",
        task_id=task.id,
        project_id=request.project_id,
        mr_iid=request.mr_iid
    )

@router.post("/api/knowledge", response_model=HealthResponse)
async def knowledges(request: ReviewRequest):
    task = review_merge_request.delay(request.project_id, request.mr_iid)
    
