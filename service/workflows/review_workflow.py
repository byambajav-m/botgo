from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Optional

from db.models import Review, ReviewVersion
from infrastructure import gitlab_client, LLMWorker
from beanie import PydanticObjectId


class ReviewState(TypedDict):
    project_id: int
    mr_iid: int

    mr_title: str
    project_name: str
    author: str
    source_branch: str
    target_branch: str

    summary_diff: str
    full_diff: str

    similar_contexts: List[str]

    review_summary: str
    suggestion: str
    confidence: str
    reason: str

    _review_id: Optional[PydanticObjectId]

    error: Optional[str]

def fetch_mr_diffs(state: ReviewState) -> ReviewState:
    try:
        mr = gitlab_client.get_mr_data(
            state["project_id"],
            state["mr_iid"],
        )

        state.update({
            "summary_diff": mr["summary_diff"],
            "full_diff": mr["full_diff"],
            "author": mr["author"],
            "source_branch": mr["source_branch"],
            "target_branch": mr["target_branch"],
            "project_name": mr["project_name"],
            "mr_title": mr["mr_title"],
        })

        return state

    except Exception as e:
        state["error"] = f"Failed to fetch MR diffs: {e}"
        return state


async def load_or_create_review(state: ReviewState) -> ReviewState:
    if state.get("error"):
        return state

    try:
        existing = await Review.find_one({
            "project_id": state["project_id"],
            "mr_iid": state["mr_iid"],
        })

        if existing:
            state["_review_id"] = existing.id
            return state

        review = Review(
            project_id=state["project_id"],
            project_name=state["project_name"],
            mr_iid=state["mr_iid"],
            author=state["author"],
            diff=state["full_diff"],
            source_branch=state["source_branch"],
            target_branch=state["target_branch"],
            mr_title=state["mr_title"],
            versions=[]
        )

        await review.insert()
        state["_review_id"] = review.id
        return state

    except Exception as e:
        state["error"] = f"Mongo init error: {e}"
        return state


async def generate_summary_review(state: ReviewState) -> ReviewState:
    if state.get("error"):
        return state

    try:
        summary, suggestion = await LLMWorker.generate_review(
            diff=state["full_diff"],
            contexts=state.get("similar_contexts", []),
        )

        state["review_summary"] = summary
        state["suggestion"] = suggestion
        return state

    except Exception as e:
        state["error"] = f"LLM review error: {e}"
        return state


async def persist_review_version(state: ReviewState) -> ReviewState:
    if state.get("error"):
        return state

    try:
        review = await Review.get(state["_review_id"])

        review.diff = state["full_diff"]

        review.versions.append(
            ReviewVersion(
                summary=state["review_summary"],
                suggestions=state["suggestion"],
            )
        )

        await review.replace()
        return state

    except Exception as e:
        state["error"] = f"Mongo persist error: {e}"
        return state


def post_summary_review(state: ReviewState) -> ReviewState:
    if state.get("error"):
        return state

    try:
        summary = state["review_summary"].strip()
        suggestion = state["suggestion"].strip()
        is_lgtm = suggestion.upper() == "LGTM"

        summary_block = (
            f"### (๑˃̵ᴗ˂̵)ﻭ Summary\n{summary}"
            if is_lgtm
            else f"### (￢_￢) Summary\n{summary}"
        )

        suggestion_block = (
            "### ヽ(・∀・)ﾉ GOOD JOB\n> **LGTM** — No blocking issues found."
            if is_lgtm
            else f"### (╯°□°）╯ Suggested Improvement\n- {suggestion}"
        )

        body = f"""
## 🐪 BotGo Review

{summary_block}

{suggestion_block}

---
<sub>Automated review • Correctness, safety, maintainability</sub>
""".strip()

        gitlab_client.post_mr_note(
            state["project_id"],
            state["mr_iid"],
            body,
        )

        return state

    except Exception as e:
        state["error"] = f"GitLab post error: {e}"
        return state

def create_review_workflow():
    graph = StateGraph(ReviewState)

    graph.add_node("fetch_diffs", fetch_mr_diffs)
    graph.add_node("init_review", load_or_create_review)
    graph.add_node("llm_review", generate_summary_review)
    graph.add_node("persist_version", persist_review_version)
    graph.add_node("post_summary", post_summary_review)

    graph.set_entry_point("fetch_diffs")

    graph.add_edge("fetch_diffs", "init_review")
    graph.add_edge("init_review", "llm_review")
    graph.add_edge("llm_review", "persist_version")
    graph.add_edge("persist_version", "post_summary")
    graph.add_edge("post_summary", END)

    return graph.compile()
