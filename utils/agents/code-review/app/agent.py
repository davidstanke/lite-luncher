import os
import logging
from typing import List, Optional
from github import Github, GithubException
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("code-review-agent")


class InlineComment(BaseModel):
    path: str = Field(description="Relative file path for the inline comment")
    position: int = Field(description="Line position within the diff patch to comment on")
    body: str = Field(description="Actionable code review suggestion or comment")


class ReviewResult(BaseModel):
    event: str = Field(
        description="GitHub PR review action: 'APPROVE', 'REQUEST_CHANGES', or 'COMMENT'"
    )
    summary: str = Field(description="High-level code review summary focusing on quality, maintainability, and readability")
    comments: List[InlineComment] = Field(default_factory=list, description="Inline code diff comments")


class CodeReviewAgent:
    def __init__(
        self,
        model_name: str = "gemini-3.6-flash",
        project: Optional[str] = None,
        location: str = "global"
    ):
        self.model_name = model_name
        project = (
            project
            or os.environ.get("GCP_PROJECT")
            or os.environ.get("GOOGLE_CLOUD_PROJECT")
        )
        location = (
            location
        )
        self.client = genai.Client(
            vertexai=True,
            project=project,
            location=location,
        )

    def fetch_pr_patches(self, github_token: str, repo_full_name: str, pr_number: int):
        gh = Github(github_token)
        repo = gh.get_repo(repo_full_name)
        pull = repo.get_pull(pr_number)

        patches = []
        for file in pull.get_files():
            if file.status in ("added", "modified", "renamed", "changed") and file.patch:
                patches.append({
                    "filename": file.filename,
                    "patch": file.patch,
                    "additions": file.additions,
                    "deletions": file.deletions,
                })
        return repo, pull, patches

    def review_pull_request(self, github_token: str, repo_full_name: str, pr_number: int) -> ReviewResult:
        logger.info(f"Starting code review for {repo_full_name} PR #{pr_number}")
        repo, pull, patches = self.fetch_pr_patches(github_token, repo_full_name, pr_number)

        if not patches:
            logger.info("No patchable files found in PR.")
            result = ReviewResult(
                event="COMMENT",
                summary="No reviewable code changes found in modified files.",
                comments=[],
            )
            self._submit_github_review(pull, result)
            return result

        prompt = f"""
You are an expert lead software engineer conducting a code review for Pull Request #{pr_number} in {repo_full_name}.

Focus your evaluation strictly on:
1. **Code Quality**: Correctness, logic flaws, edge cases, error handling.
2. **Maintainability**: Modularity, DRY principles, testability, clean architecture.
3. **Readability**: Naming conventions, PEP 8/style guide adherence, clean structure.

**Instructions**:
- Keep the summary **BRIEF AND CONCISE** (2-4 sentences maximum).
- Even if there are no inline suggestions or issues found, ALWAYS provide a brief summary (e.g. "LGTM! Changes are clean, well-structured, and ready to merge.").

PR Title: {pull.title}
PR Description: {pull.body or 'N/A'}

Modified Files & Diffs:
"""
        for p in patches:
            prompt += f"\n--- File: {p['filename']} ---\n{p['patch']}\n"

        prompt += """
Provide a structured output containing:
- 'event': 'APPROVE' if changes are well-written and maintainable, 'REQUEST_CHANGES' if there are critical bugs/security issues/major maintainability flaws, or 'COMMENT' for minor suggestions.
- 'summary': Brief review summary (2-4 sentences max).
- 'comments': List of inline diff comments specifying 'path', 'position' (the 1-indexed relative line count in the patch diff, NOT absolute file line), and 'body'. Return [] if no inline comments are required.
"""

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ReviewResult,
                temperature=0.2,
            ),
        )

        review_data = ReviewResult.model_validate_json(response.text)

        self._submit_github_review(pull, review_data)
        return review_data

    def _submit_github_review(self, pull, review_data: ReviewResult):
        inline_payload = []
        for c in review_data.comments:
            inline_payload.append({
                "path": c.path,
                "position": c.position,
                "body": c.body,
            })

        body_text = f"## 🤖 Antigravity Code Review\n\n{review_data.summary}"
        event = review_data.event
        logger.info(f"Submitting review to GitHub PR #{pull.number} with event={event}")

        # Attempt 1: Full review with original event and inline comments
        try:
            pull.create_review(
                body=body_text,
                event=event,
                comments=inline_payload if inline_payload else None,
            )
            logger.info("Successfully posted pull request review.")
            return
        except Exception as e:
            logger.warning(f"Attempt 1 (full review) failed: {e}")

        # Attempt 2: Fallback to event='COMMENT' with inline comments (handles self-review restriction)
        try:
            pull.create_review(
                body=body_text,
                event="COMMENT",
                comments=inline_payload if inline_payload else None,
            )
            logger.info("Successfully posted fallback COMMENT review with inline comments.")
            return
        except Exception as e:
            logger.warning(f"Attempt 2 (COMMENT review with inline comments) failed: {e}")

        # Attempt 3: Fallback to event='COMMENT' without inline comments (handles invalid position offsets)
        try:
            pull.create_review(
                body=body_text,
                event="COMMENT",
            )
            logger.info("Successfully posted fallback COMMENT review (summary only).")
            return
        except Exception as e:
            logger.warning(f"Attempt 3 (COMMENT review summary only) failed: {e}")

        # Attempt 4: Ultimate fallback to posting a standard PR issue comment
        try:
            pull.create_issue_comment(body_text)
            logger.info("Successfully posted fallback PR issue comment.")
            return
        except Exception as e:
            logger.error(f"All review posting attempts failed. Final error: {e}")
            raise RuntimeError(f"GitHub review and comment posting failed: {e}") from e
