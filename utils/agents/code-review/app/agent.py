import os
import logging
from typing import List, Optional
from github import Github, GithubException
import google.auth
import google.auth.transport.requests
from google.antigravity import Agent, LocalAgentConfig
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
    ):
        self.model_name = model_name

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

    async def review_pull_request(self, github_token: str, repo_full_name: str, pr_number: int) -> ReviewResult:
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

        system_instructions = (
            "You are an expert lead software engineer conducting a code review for a GitHub Pull Request.\n\n"
            "Focus your evaluation strictly on:\n"
            "1. Code Quality: Correctness, logic flaws, edge cases, error handling.\n"
            "2. Maintainability: Modularity, DRY principles, testability, clean architecture.\n"
            "3. Readability: Naming conventions, style guide adherence, clean structure.\n\n"
            "Keep the summary BRIEF AND CONCISE (2-4 sentences maximum)."
        )

        prompt = f"""
Conduct a code review for Pull Request #{pr_number} in {repo_full_name}.

PR Title: {pull.title}
PR Description: {pull.body or 'N/A'}

Modified Files & Diffs:
"""
        for p in patches:
            prompt += f"\n--- File: {p['filename']} ---\n{p['patch']}\n"

        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key:
            logger.info("Using GEMINI_API_KEY for authentication.")
            config = LocalAgentConfig(
                model=self.model_name,
                api_key=api_key,
                system_instructions=system_instructions,
                response_schema=ReviewResult,
            )
        else:
            logger.info("GEMINI_API_KEY not set. Using Vertex AI with Application Default Credentials (ADC).")
            try:
                _, adc_project = google.auth.default(
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
            except Exception as e:
                logger.warning(f"Failed to resolve ADC project: {e}")
                adc_project = None

            project_id = (
                adc_project
                or os.environ.get("GCP_PROJECT")
                or os.environ.get("GOOGLE_CLOUD_PROJECT")
            )
            location = os.environ.get("GCP_LOCATION", "us-central1")
            model = "gemini-2.5-flash" if "3.6" in self.model_name else self.model_name

            config = LocalAgentConfig(
                model=model,
                vertex=True,
                project=project_id,
                location=location,
                system_instructions=system_instructions,
                response_schema=ReviewResult,
            )

        async with Agent(config) as agent:
            response = await agent.chat(prompt)
            data = await response.structured_output()

        if isinstance(data, dict):
            review_data = ReviewResult.model_validate(data)
        elif isinstance(data, ReviewResult):
            review_data = data
        else:
            raise ValueError(f"Unexpected response type from structured_output: {type(data)}")

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
