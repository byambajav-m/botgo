from fastapi import APIRouter

from api.schemas import (
    WebhookPayload,
    ReviewRequest,
    ReviewResponse,
    HealthResponse
)
from infrastructure.gitlab_client import GitLabClient
from tasks import review_merge_request
from config import settings
import requests
from redis import Redis
from workflows import create_review_workflow, ReviewState

router = APIRouter()


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
    workflow = create_review_workflow()

    initial_state: ReviewState = {
        "project_id": request.project_id,
        "mr_iid": request.mr_iid,
    }

    result = await workflow.ainvoke(initial_state)

    if result.get("error"):
        return {"status": "error", "error": result["error"]}

    return ReviewResponse(
        status="completed",
        project_id=request.project_id,
        mr_iid=request.mr_iid,
        task_id="task_iod"
    )

@router.get("/api/projects")
async def get_projects():
    gitlab_client = GitLabClient()
    project_list = gitlab_client.get_projects()

    for p in project_list:
        print(p.id)
        print(p.path_with_namespace)
        print(p.name)

    return { "projects": "ok" }

@router.get("/api/merge-requests/{project_id}")
async def get_merge_requests(project_id):
    gitlab_client = GitLabClient()
    mr_list = gitlab_client.get_mrs_by_project(project_id)
    for mr in mr_list:
        print(mr.iid)
        print(mr.state)

    return { "merge_requests": "ok" }

@router.get("/api/merge-requests/{project_id}/{mr_iid}/diff")
async def get_diff(project_id, mr_iid):
    gitlab_client = GitLabClient()
    diffs = gitlab_client.get_mr_diff(project_id, mr_iid)
    print(diffs)
    return { "diffs": "ok" }
@router.post("/api/knowledge", response_model=HealthResponse)
async def knowledges(request: ReviewRequest):
    task = review_merge_request.delay(request.project_id, request.mr_iid)
    
