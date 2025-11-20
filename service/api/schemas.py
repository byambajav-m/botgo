from pydantic import BaseModel

class WebhookPayload(BaseModel):
    object_kind: str
    project: dict
    object_attributes: dict

class ReviewRequest(BaseModel):
    project_id: int
    mr_iid: int

class ReviewResponse(BaseModel):
    status: str
    task_id: str
    project_id: int
    mr_iid: int

class HealthResponse(BaseModel):
    api: str
    redis: str
    ollama: str