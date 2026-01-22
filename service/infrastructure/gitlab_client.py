import gitlab
from config import settings


class GitLabClient:
    def __init__(self):
        self.gl = gitlab.Gitlab(
            settings.GITLAB_URL,
            private_token=settings.GITLAB_TOKEN,
        )

    def get_projects(self, membership=True, owned=False, search=None):
        return self.gl.projects.list(
            membership=membership,
            owned=owned,
            search=search,
            all=True,
            simple=True,
        )

    def get_project(self, project_id: int):
        return self.gl.projects.get(project_id)

    def get_mrs_by_project(
        self,
        project_id: int,
        state: str = "merged",
        source_branch: str | None = None,
        target_branch: str | None = None,
    ):
        project = self.gl.projects.get(project_id)
        return project.mergerequests.list(
            state=state,
            source_branch=source_branch,
            target_branch=target_branch,
            all=True,
        )

    def get_mr_diff_summary(
        self,
        project_id: int,
        mr_iid: int,
        max_files: int = 5,
        max_chars: int = 2000,
    ) -> str:
        project = self.gl.projects.get(project_id)
        mr = project.mergerequests.get(mr_iid)

        diff_versions = mr.diffs.list()
        if not diff_versions:
            return "No diff versions found"

        latest = diff_versions[0]
        diff_version = mr.diffs.get(latest.id)

        diff_text = ""
        for d in diff_version.diffs[:max_files]:
            diff_text += f"\n--- {d['old_path']} -> {d['new_path']}\n"
            diff_text += d.get("diff", "")[:max_chars]

        return diff_text or "No changes found"

    def get_mr_diff_full(
        self,
        project_id: int,
        mr_iid: int,
    ) -> str:
        project = self.gl.projects.get(project_id)
        mr = project.mergerequests.get(mr_iid)

        diff_versions = mr.diffs.list()
        if not diff_versions:
            return ""

        latest = diff_versions[0]
        diff_version = mr.diffs.get(latest.id)

        diff_text = ""
        for d in diff_version.diffs:
            diff_text += f"diff --git a/{d['old_path']} b/{d['new_path']}\n"
            diff_text += d.get("diff", "")
            diff_text += "\n"

        return diff_text

    def post_mr_note(
        self,
        project_id: int,
        mr_iid: int,
        note_body: str,
    ) -> None:
        project = self.gl.projects.get(project_id)
        mr = project.mergerequests.get(mr_iid)
        mr.notes.create({"body": note_body})

    def post_inline_comment(
            self,
            project_id: int,
            mr_iid: int,
            file_path: str,
            start_line: int,
            end_line: int,
            body: str,
    ) -> None:
        project = self.gl.projects.get(project_id)
        mr = project.mergerequests.get(mr_iid)

        diff_refs = mr.diff_refs

        position = {
            "position_type": "text",
            "base_sha": diff_refs["base_sha"],
            "start_sha": diff_refs["start_sha"],
            "head_sha": diff_refs["head_sha"],
            "new_path": file_path,
            "line_range": {
                "start": {
                    "line": start_line,
                    "type": "new",
                },
                "end": {
                    "line": end_line,
                    "type": "new",
                },
            },
        }

        mr.discussions.create({
            "body": body,
            "position": position,
        })

    def get_mr_info(self, project_id: int, mr_iid: int) -> dict:
        project = self.gl.projects.get(project_id)
        mr = project.mergerequests.get(mr_iid)
        return {
            "title": mr.title,
            "author": mr.author["username"],
            "state": mr.state,
            "source_branch": mr.source_branch,
            "target_branch": mr.target_branch,
        }


gitlab_client = GitLabClient()
