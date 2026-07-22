import os
import logging
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from app.agent import CodeReviewAgent, ReviewResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("code-review-service")

app = FastAPI(
    title="Antigravity Code Review Agent Service",
    description="Agent Runtime service that performs code reviews on GitHub Pull Requests using Antigravity SDK",
    version="0.1.0",
)

agent = CodeReviewAgent()


class ReviewRequest(BaseModel):
    repo_full_name: str
    pr_number: int
    github_token: str


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "code-review-agent"}


@app.post("/review", response_model=ReviewResult)
async def trigger_code_review(req: ReviewRequest):
    try:
        result = await agent.review_pull_request(
            github_token=req.github_token,
            repo_full_name=req.repo_full_name,
            pr_number=req.pr_number,
        )
        return result
    except Exception as e:
        logger.error(f"Error executing code review: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
