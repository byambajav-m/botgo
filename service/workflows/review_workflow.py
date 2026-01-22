from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Optional
from infrastructure import gitlab_client, LLMWorker

class ReviewState(TypedDict):
    project_id: int
    mr_iid: int

    summary_diff: str
    full_diff: str

    similar_contexts: List[str]

    inline_comments: List[dict]

    review_summary: str
    suggestion: str
    confidence: str
    reason: str

    error: Optional[str]


def fetch_mr_diffs(state: ReviewState):
    try:
        project_id = state["project_id"]
        mr_iid = state["mr_iid"]

        state["summary_diff"] = gitlab_client.get_mr_diff_summary(
            project_id,
            mr_iid,
        )

        state["full_diff"] = gitlab_client.get_mr_diff_full(
            project_id,
            mr_iid,
        )

        return state

    except Exception as e:
        state["error"] = f"Failed to fetch MR diffs: {str(e)}"
        return state


async def generate_summary_review(state: ReviewState):
    try:
        if state.get("error"):
            return state

        summary, suggestion = await LLMWorker.generate_review(
            diff=state["summary_diff"],
            contexts=state["similar_contexts"],
        )

        state["review_summary"] = summary
        state["suggestion"] = suggestion
        return state

    except Exception as e:
        state["error"] = f"Summary review error: {str(e)}"
        return state

def post_summary_review(state: ReviewState):
    try:
        if state.get("error"):
            return state

        summary = (state.get("review_summary") or "").strip()
        suggestion = (state.get("suggestion") or "").strip()

        is_lgtm = suggestion.upper() == "LGTM"

        summary_block = f"""
### (๑˃̵ᴗ˂̵)ﻭ Summary
{summary}
""".strip() if is_lgtm else f"""
### (￢_￢) Summary
{summary}
""".strip()

        if is_lgtm:
            suggestion_block = """
### ヽ(・∀・)ﾉ GOOD JOB
> **LGTM** — No blocking issues found.
""".strip()
        else:
            suggestion_block = f"""
### (╯°□°）╯ Suggested Improvement
- {suggestion}
""".strip()

        note_body = f"""
## 🐪 BotGo Review

{summary_block}

{suggestion_block}

---
<sub>Automated review • Focused on correctness, safety, and maintainability</sub>
""".strip()

        gitlab_client.post_mr_note(
            state["project_id"],
            state["mr_iid"],
            note_body,
        )

        return state

    except Exception as e:
        state["error"] = f"Failed to post summary review: {str(e)}"
        return state



def create_review_workflow():
    workflow = StateGraph(ReviewState)

    workflow.add_node("fetch_diffs", fetch_mr_diffs)
    workflow.add_node("summary_review", generate_summary_review)
    workflow.add_node("post_summary", post_summary_review)

    workflow.set_entry_point("fetch_diffs")

    workflow.add_edge("fetch_diffs", "summary_review")
    workflow.add_edge("summary_review", "post_summary")
    workflow.add_edge("post_summary", END)

    return workflow.compile()
