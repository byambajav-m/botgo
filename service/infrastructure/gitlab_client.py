import gitlab
from config import settings

class GitLabClient:
    def __init__(self):
        self.gl = gitlab.Gitlab(
            settings.GITLAB_URL,
            private_token=settings.GITLAB_TOKEN
        )

    def get_mr_diff(self, project_id: int, mr_iid: int) -> str:
        project = self.gl.projects.get(project_id)
        mr = project.mergerequests.get(mr_iid)

        changes = mr.changes()
        diff_text = ""

        for change in changes.get("changes", [])[:5]:
            diff_text += f"\n--- {change['old_path']} -> {change['new_path']}\n"
            diff_text += change.get("diff", "")[:2000]

        return diff_text or "No changes found"

    def post_mr_note(self, project_id: int, mr_iid: int, note_body: str) -> None:
        project = self.gl.projects.get(project_id)
        mr = project.mergerequests.get(mr_iid)
        mr.notes.create({"body": note_body})

    def get_mr_info(self, project_id: int, mr_iid: int) -> dict:
        project = self.gl.projects.get(project_id)
        mr = project.mergerequests.get(mr_iid)
        return {
            "title": mr.title,
            "author": mr.author["username"],
            "state": mr.state,
            "source_branch": mr.source_branch,
            "target_branch": mr.target_branch
        }


gitlab_client = GitLabClient()