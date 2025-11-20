from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Optional

from lmnr import observe

from infrastructure import weaviate_client, gitlab_client, ollama_client


class ReviewState(TypedDict):
    project_id: int
    mr_iid: int
    diff: str
    similar_contexts: List[str]
    review_summary: str
    suggestion: str
    error: Optional[str]

@observe(name="fetch_mr_diff_step")
def fetch_mr_diff(state: ReviewState) -> ReviewState:
    try:
        diff = gitlab_client.get_mr_diff(state["project_id"], state["mr_iid"])
        state["diff"] = diff
        return state
    except Exception as e:
        state["error"] = f"Failed to fetch MR: {str(e)}"
        return state

@observe(name="retrieve_context_step")
def retrieve_context(state: ReviewState) -> ReviewState:
    try:
        if state.get("error"):
            return state

        weaviate_client.store_diff(
            state["project_id"],
            state["mr_iid"],
            state["diff"]
        )

        similar = weaviate_client.query_similar(state["diff"], n_results=3)
        state["similar_contexts"] = similar

        return state
    except Exception as e:
        state["error"] = f"Weaviate error: {str(e)}"
        return state

@observe(name="generate_review_step")
def generate_review(state: ReviewState) -> ReviewState:
    try:
        if state.get("error"):
            return state

        summary, suggestion = ollama_client.generate_review(
            state["diff"],
            state["similar_contexts"]
        )

        state["review_summary"] = summary
        state["suggestion"] = suggestion
        return state

    except Exception as e:
        state["error"] = f"LLM error: {str(e)}"
        return state

@observe(name="post_review_step")
def post_review(state: ReviewState) -> ReviewState:
    try:
        if state.get("error"):
            return state

        note_body = f"""## 🤖 BotGo Review

                    **Summary:**
                    {state["review_summary"]}
                    
                    **Suggestion:**
                    {state["suggestion"]}
        
                    """

        gitlab_client.post_mr_note(
            state["project_id"],
            state["mr_iid"],
            note_body
        )

        return state

    except Exception as e:
        state["error"] = f"Failed to post review: {str(e)}"
        return state


@observe(name="create_review_workflow")
def create_review_workflow():
    workflow = StateGraph(ReviewState)

    workflow.add_node("fetch_diff", fetch_mr_diff)
    workflow.add_node("retrieve_context", retrieve_context)
    workflow.add_node("generate_review", generate_review)
    workflow.add_node("post_review", post_review)

    workflow.set_entry_point("fetch_diff")
    workflow.add_edge("fetch_diff", "retrieve_context")
    workflow.add_edge("retrieve_context", "generate_review")
    workflow.add_edge("generate_review", "post_review")
    workflow.add_edge("post_review", END)

    return workflow.compile()