from beanie import Document, PydanticObjectId, before_event, Insert, Replace
from pydantic import Field, BaseModel
from typing import List
from datetime import datetime

class ReviewVersion(BaseModel):
    summary: str
    suggestions: str

class Review(Document):
    id: PydanticObjectId = Field(default_factory=PydanticObjectId)

    mr_title: str
    project_id: int
    project_name: str
    mr_iid: int
    author: str
    diff: str
    source_branch: str
    target_branch: str
    versions: List[ReviewVersion]

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @before_event(Insert)
    def set_created_at(self):
        self.created_at = datetime.now()

    @before_event(Replace)
    def set_updated_at(self):
        self.updated_at = datetime.now()

    class Settings:
        name = "reviews"
