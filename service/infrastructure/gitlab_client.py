import gitlab
from config import settings
from loguru import logger
from typing import Dict, Any
import sys

logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)


class GitLabClient:
    def __init__(self):
        try:
            self.gl = gitlab.Gitlab(
                settings.GITLAB_URL,
                private_token=settings.GITLAB_TOKEN,
            )
        except Exception:
            logger.exception("Failed to initialize GitLab client")
            raise

    def get_projects(self, membership=True, owned=False, search=None):
        try:
            return self.gl.projects.list(
                membership=membership,
                owned=owned,
                search=search,
                all=True,
                simple=True,
            )
        except Exception:
            logger.exception(
                "Failed to list projects",
                membership=membership,
                owned=owned,
                search=search,
            )
            raise

    def get_project(self, project_id: int):
        try:
            return self.gl.projects.get(project_id)
        except Exception:
            logger.exception(
                "Failed to get project",
                project_id=project_id,
            )
            raise

    def get_mrs_by_project(
        self,
        project_id: int,
        state: str = "merged",
        source_branch: str | None = None,
        target_branch: str | None = None,
    ):
        try:
            project = self.gl.projects.get(project_id)
            return project.mergerequests.list(
                state=state,
                source_branch=source_branch,
                target_branch=target_branch,
                all=True,
            )
        except Exception:
            logger.exception(
                "Failed to list merge requests",
                project_id=project_id,
                state=state,
                source_branch=source_branch,
                target_branch=target_branch,
            )
            raise

    def get_mr_data(
            self,
            project_id: int,
            mr_iid: int,
            max_files: int = 15,
            max_chars: int = 2000,
    ) -> Dict[str, Any]:
        try:
            project = self.gl.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)
            diff_versions = mr.diffs.list()
            if not diff_versions:
                logger.warning(
                    "No diff versions found",
                    project_id=project_id,
                    mr_iid=mr_iid,
                )
                return {
                    "project_name": project.name,
                    "author": mr.author["username"],
                    "source_branch": mr.source_branch,
                    "target_branch": mr.target_branch,
                    "summary_diff": "",
                    "full_diff": "",
                }

            latest = diff_versions[0]
            diff_version = mr.diffs.get(latest.id)

            summary_diff = ""
            full_diff = ""

            for idx, d in enumerate(diff_version.diffs):
                old_path = d["old_path"]
                new_path = d["new_path"]
                diff_body = d.get("diff", "")

                full_diff += f"diff --git a/{old_path} b/{new_path}\n"
                full_diff += diff_body
                full_diff += "\n"

                if idx < max_files:
                    summary_diff += f"\n--- {old_path} -> {new_path}\n"
                    summary_diff += diff_body[:max_chars]

            return {
                "project_name": project.name,
                "author": mr.author["name"],
                "source_branch": mr.source_branch,
                "target_branch": mr.target_branch,
                "summary_diff": summary_diff.strip(),
                "full_diff": full_diff.strip(),
                "mr_title": mr.title
            }

        except Exception:
            logger.exception(
                "Failed to fetch MR diff",
                project_id=project_id,
                mr_iid=mr_iid,
            )
            raise

    def get_mr_diff_summary(
        self,
        project_id: int,
        mr_iid: int,
        max_files: int = 5,
        max_chars: int = 2000,
    ) -> str:
        try:
            project = self.gl.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)

            diff_versions = mr.diffs.list()
            if not diff_versions:
                logger.warning(
                    "No diff versions found",
                    project_id=project_id,
                    mr_iid=mr_iid,
                )
                return "No diff versions found"

            latest = diff_versions[0]
            diff_version = mr.diffs.get(latest.id)

            diff_text = ""
            for d in diff_version.diffs[:max_files]:
                diff_text += f"\n--- {d['old_path']} -> {d['new_path']}\n"
                diff_text += d.get("diff", "")[:max_chars]

            return diff_text or "No changes found"

        except Exception:
            logger.exception(
                "Failed to fetch MR diff summary",
                project_id=project_id,
                mr_iid=mr_iid,
            )
            raise

    def get_mr_diff_full(
        self,
        project_id: int,
        mr_iid: int,
    ) -> str:
        try:
            project = self.gl.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)

            diff_versions = mr.diffs.list()
            if not diff_versions:
                logger.warning(
                    "No diff versions found",
                    project_id=project_id,
                    mr_iid=mr_iid,
                )
                return ""

            latest = diff_versions[0]
            diff_version = mr.diffs.get(latest.id)

            diff_text = ""
            for d in diff_version.diffs:
                diff_text += f"diff --git a/{d['old_path']} b/{d['new_path']}\n"
                diff_text += d.get("diff", "")
                diff_text += "\n"

            return diff_text

        except Exception:
            logger.exception(
                "Failed to fetch full MR diff",
                project_id=project_id,
                mr_iid=mr_iid,
            )
            raise

    def post_mr_note(
        self,
        project_id: int,
        mr_iid: int,
        note_body: str,
    ) -> None:
        try:
            project = self.gl.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)
            mr.notes.create({"body": note_body})
        except Exception:
            logger.exception(
                "Failed to post MR note",
                project_id=project_id,
                mr_iid=mr_iid,
                note_preview=note_body[:100],
            )
            raise

    def post_inline_comment(
        self,
        project_id: int,
        mr_iid: int,
        file_path: str,
        start_line: int,
        end_line: int,
        body: str,
    ) -> None:
        try:
            project = self.gl.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)

            diff_refs = mr.diff_refs
            if not diff_refs:
                logger.error(
                    "Missing diff_refs for MR",
                    project_id=project_id,
                    mr_iid=mr_iid,
                )
                return

            position = {
                "position_type": "text",
                "base_sha": diff_refs["base_sha"],
                "start_sha": diff_refs["start_sha"],
                "head_sha": diff_refs["head_sha"],
                "new_path": file_path,
                "line_range": {
                    "start": {"line": start_line, "type": "new"},
                    "end": {"line": end_line, "type": "new"},
                },
            }

            mr.discussions.create(
                {
                    "body": body,
                    "position": position,
                }
            )

        except Exception:
            logger.exception(
                "Failed to post inline comment",
                project_id=project_id,
                mr_iid=mr_iid,
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
            )
            raise

    def get_mr_info(self, project_id: int, mr_iid: int) -> dict:
        try:
            project = self.gl.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)
            return {
                "title": mr.title,
                "author": mr.author["username"],
                "state": mr.state,
                "iid": mr.iid,
                "source_branch": mr.source_branch,
                "target_branch": mr.target_branch,
            }
        except Exception:
            logger.exception(
                "Failed to fetch MR info",
                project_id=project_id,
                mr_iid=mr_iid,
            )
            raise


gitlab_client = GitLabClient()
