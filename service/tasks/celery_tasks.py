from celery import Celery
from config import settings
from workflows import create_review_workflow, ReviewState

celery_app = Celery(
    "mr_reviewer",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)


@celery_app.task(name="review_merge_request")
def review_merge_request(project_id: int, mr_iid: int):
    workflow = create_review_workflow()

    initial_state: ReviewState = {
        "project_id": project_id,
        "mr_iid": mr_iid,
        "diff": "",
        "similar_contexts": [],
        "review_summary": "",
        "suggestion": "",
        "error": None
    }

    result = workflow.invoke(initial_state)

    if result.get("error"):
        return {"status": "error", "error": result["error"]}

    return {
        "status": "success",
        "summary": result["review_summary"],
        "suggestion": result["suggestion"]
    }