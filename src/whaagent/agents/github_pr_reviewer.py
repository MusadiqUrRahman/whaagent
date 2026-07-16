"""GitHub PR Review Agent for automated code review using the GitHub API."""

import os
import time
from typing import Any, Sequence

import requests

from whaagent.agent import AgentBase
from whaagent.interfaces.base import Tool
from whaagent.prompts import load_prompt
from whaagent.registry import AgentRegistry

_GITHUB_API_BASE = "https://api.github.com"
_RETRYABLE_STATUS_CODES = frozenset({429, 503, 504})
_MAX_RETRIES = 3


def _github_request(method: str, url: str, **kwargs: Any) -> requests.Response:
    """Make a GitHub API request with exponential backoff for transient errors.

    Retries up to _MAX_RETRIES times on 429 (rate limited), 503, and 504 responses,
    with delays of 1s, 2s between attempts (2**attempt seconds).

    Args:
        method: HTTP method — "get" or "post".
        url: Full request URL.
        **kwargs: Additional arguments forwarded to the underlying requests call.

    Returns:
        requests.Response from the last attempt.
    """
    for attempt in range(_MAX_RETRIES):
        if method == "get":
            response = requests.get(url, **kwargs)
        else:
            response = requests.post(url, **kwargs)
        if response.status_code not in _RETRYABLE_STATUS_CODES:
            return response
        if attempt < _MAX_RETRIES - 1:
            time.sleep(2**attempt)
    return response


def _get_headers() -> dict[str, str]:
    """Build GitHub API request headers from the GITHUB_TOKEN environment variable."""
    token = os.environ.get("GITHUB_TOKEN", "")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _check_token() -> str | None:
    """Return an error string if GITHUB_TOKEN is missing, else None.

    Returns:
        Error message string if token is absent, otherwise None.
    """
    if not os.environ.get("GITHUB_TOKEN"):
        return (
            "Error: GITHUB_TOKEN environment variable is not set. Please export GITHUB_TOKEN before running this agent."
        )
    return None


def get_pr_diff(repo: str, pr_number: int) -> str:
    """Fetch the file diffs for a GitHub pull request.

    Args:
        repo: Repository in 'owner/repo' format.
        pr_number: Pull request number.

    Returns:
        Formatted diff string with filename, status, additions, deletions, and patch.
        Returns an error string on failure.
    """
    err = _check_token()
    if err:
        return err
    try:
        url = f"{_GITHUB_API_BASE}/repos/{repo}/pulls/{pr_number}/files"
        response = _github_request("get", url, headers=_get_headers(), timeout=30)
        response.raise_for_status()
        files: list[dict[str, Any]] = response.json()
        lines = [f"PR #{pr_number} diff for {repo} ({len(files)} file(s) changed):"]
        for f in files:
            filename = f.get("filename", "")
            status = f.get("status", "")
            additions = f.get("additions", 0)
            deletions = f.get("deletions", 0)
            patch = f.get("patch", "")
            lines.append(f"\n--- {filename} [{status}] +{additions}/-{deletions} ---")
            if patch:
                lines.append(str(patch))
        return "\n".join(lines)
    except Exception as exc:
        return f"Error fetching PR diff for {repo}#{pr_number}: {exc}"


def get_pr_comments(repo: str, pr_number: int) -> str:
    """Fetch review and general comments for a pull request.

    Args:
        repo: Repository in 'owner/repo' format.
        pr_number: Pull request number.

    Returns:
        Structured list of comments with author, body, file, and line info.
        Returns an error string on failure.
    """
    err = _check_token()
    if err:
        return err
    try:
        headers = _get_headers()
        review_url = f"{_GITHUB_API_BASE}/repos/{repo}/pulls/{pr_number}/comments"
        issue_url = f"{_GITHUB_API_BASE}/repos/{repo}/issues/{pr_number}/comments"

        review_resp = _github_request("get", review_url, headers=headers, timeout=30)
        review_resp.raise_for_status()
        review_comments: list[dict[str, Any]] = review_resp.json()

        issue_resp = _github_request("get", issue_url, headers=headers, timeout=30)
        issue_resp.raise_for_status()
        issue_comments: list[dict[str, Any]] = issue_resp.json()

        lines: list[str] = [f"Comments for PR #{pr_number} in {repo}:"]

        if review_comments:
            lines.append("\n[Inline Review Comments]")
            for c in review_comments:
                user = str(c.get("user", {}).get("login", "unknown"))
                cid = str(c.get("id", ""))
                path = str(c.get("path", ""))
                line = str(c.get("line") or c.get("original_line", ""))
                body = str(c.get("body", ""))
                lines.append(f"  id={cid} author={user} file={path} line={line}\n  {body}")
        else:
            lines.append("\n[Inline Review Comments] None")

        if issue_comments:
            lines.append("\n[General Comments]")
            for c in issue_comments:
                user = str(c.get("user", {}).get("login", "unknown"))
                cid = str(c.get("id", ""))
                body = str(c.get("body", ""))
                lines.append(f"  id={cid} author={user}\n  {body}")
        else:
            lines.append("\n[General Comments] None")

        return "\n".join(lines)
    except Exception as exc:
        return f"Error fetching PR comments for {repo}#{pr_number}: {exc}"


def post_review_comment(repo: str, pr_number: int, commit_sha: str, path: str, line: int, body: str) -> str:
    """Post an inline code review comment on a specific file and line.

    Args:
        repo: Repository in 'owner/repo' format.
        pr_number: Pull request number.
        commit_sha: The SHA of the commit to comment on (use head SHA from get_pr_metadata).
        path: File path relative to repository root.
        line: Line number in the diff to comment on (must be a positive integer).
        body: Markdown content of the review comment.

    Returns:
        Success message with comment URL, or an error string on failure.
    """
    err = _check_token()
    if err:
        return err
    if line < 1:
        return (
            f"Error: line must be a positive integer, got {line}. "
            "Use get_pr_diff to find the correct line number within the diff."
        )
    try:
        url = f"{_GITHUB_API_BASE}/repos/{repo}/pulls/{pr_number}/comments"
        payload = {
            "body": body,
            "commit_id": commit_sha,
            "path": path,
            "line": line,
        }
        response = _github_request("post", url, headers=_get_headers(), json=payload, timeout=30)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        html_url = str(data.get("html_url", ""))
        return f"Posted inline review comment on {path}:{line}. URL: {html_url}"
    except Exception as exc:
        return f"Error posting review comment on {repo}#{pr_number} {path}:{line}: {exc}"


def post_general_comment(repo: str, pr_number: int, body: str) -> str:
    """Post a top-level comment on a pull request.

    Args:
        repo: Repository in 'owner/repo' format.
        pr_number: Pull request number.
        body: Markdown content of the comment.

    Returns:
        Success message with comment URL, or an error string on failure.
    """
    err = _check_token()
    if err:
        return err
    try:
        url = f"{_GITHUB_API_BASE}/repos/{repo}/issues/{pr_number}/comments"
        payload = {"body": body}
        response = _github_request("post", url, headers=_get_headers(), json=payload, timeout=30)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        html_url = str(data.get("html_url", ""))
        return f"Posted general comment on PR #{pr_number}. URL: {html_url}"
    except Exception as exc:
        return f"Error posting general comment on {repo}#{pr_number}: {exc}"


def reply_to_review_comment(repo: str, pr_number: int, comment_id: int, body: str) -> str:
    """Reply to an existing inline review comment thread.

    Args:
        repo: Repository in 'owner/repo' format.
        pr_number: Pull request number.
        comment_id: The ID of comment to reply to.
        body: Markdown content of the reply.

    Returns:
        Success message with reply URL, or an error string on failure.
    """
    err = _check_token()
    if err:
        return err
    try:
        url = f"{_GITHUB_API_BASE}/repos/{repo}/pulls/{pr_number}/comments/{comment_id}/replies"
        payload = {"body": body}
        response = _github_request("post", url, headers=_get_headers(), json=payload, timeout=30)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        html_url = str(data.get("html_url", ""))
        return f"Replied to comment #{comment_id} on PR #{pr_number}. URL: {html_url}"
    except Exception as exc:
        return f"Error replying to comment #{comment_id} on {repo}#{pr_number}: {exc}"


def get_pr_metadata(repo: str, pr_number: int) -> str:
    """Fetch metadata for a pull request including title, description, author, and head SHA.

    Args:
        repo: Repository in 'owner/repo' format.
        pr_number: Pull request number.

    Returns:
        Formatted metadata string including head SHA needed for inline comments.
        Returns an error string on failure.
    """
    err = _check_token()
    if err:
        return err
    try:
        url = f"{_GITHUB_API_BASE}/repos/{repo}/pulls/{pr_number}"
        response = _github_request("get", url, headers=_get_headers(), timeout=30)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        title = str(data.get("title", ""))
        description = str(data.get("body") or "")
        author = str(data.get("user", {}).get("login", "unknown"))
        state = str(data.get("state", ""))
        base_branch = str(data.get("base", {}).get("ref", ""))
        head_branch = str(data.get("head", {}).get("ref", ""))
        head_sha = str(data.get("head", {}).get("sha", ""))
        changed_files = int(data.get("changed_files", 0))
        additions = int(data.get("additions", 0))
        deletions = int(data.get("deletions", 0))
        # Truncate description to 2000 chars to keep's response manageable for the agent.
        truncated_description = description[:2000]
        return (
            f"PR #{pr_number}: {title}\n"
            f"Author: {author}\n"
            f"State: {state}\n"
            f"Base: {base_branch} <- Head: {head_branch}\n"
            f"Head SHA: {head_sha}\n"
            f"Changes: +{additions}/-{deletions} across {changed_files} file(s)\n"
            f"Description:\n{truncated_description}"
        )
    except Exception as exc:
        return f"Error fetching PR metadata for {repo}#{pr_number}: {exc}"


@AgentRegistry.register("github-pr-reviewer")
class GithubPrReviewerAgent(AgentBase):
    """GitHub PR Review Agent that reads diffs and posts inline and summary review comments.

    Requires GITHUB_TOKEN environment variable to be set with a GitHub personal
    access token (or fine-grained token) that has 'pull_requests: write' permission.

    Usage::

        bin/agent.sh github-pr-reviewer -i "Review PR #42 in owner/repo"
        bin/agent.sh github-pr-reviewer -i "Review PR #42 in owner/repo and reply to open questions"
        bin/agent.sh github-pr-reviewer -i "Read comments on PR #42 in owner/repo and reply to unanswered questions"
    """

    @property
    def system_prompt(self) -> str:
        return load_prompt("github_pr_reviewer")

    def local_tools(self) -> Sequence[Any]:
        """Return six GitHub API tools available to this agent."""
        return [
            Tool.from_function(
                func=get_pr_metadata,
                name="get_pr_metadata",
                description=(
                    "Fetch pull request metadata: title, description, author, base branch, "
                    "head SHA, and change statistics. Always call this first to get head SHA "
                    "before posting inline comments."
                ),
            ),
            Tool.from_function(
                func=get_pr_diff,
                name="get_pr_diff",
                description=(
                    "Fetch file diffs for a GitHub pull request. Returns filename, status, "
                    "additions/deletions, and patch content for each changed file."
                ),
            ),
            Tool.from_function(
                func=get_pr_comments,
                name="get_pr_comments",
                description=(
                    "Fetch both inline review comments and top-level general comments for a pull "
                    "request. Returns comment id, author, body, file, and line number."
                ),
            ),
            Tool.from_function(
                func=post_review_comment,
                name="post_review_comment",
                description=(
                    "Post an inline code review comment on a specific file and line number. "
                    "Requires commit_sha — use get_pr_metadata to retrieve head SHA first."
                ),
            ),
            Tool.from_function(
                func=post_general_comment,
                name="post_general_comment",
                description=(
                    "Post a top-level (general) comment on a pull request. Use for overall "
                    "summaries or replies to general comment threads."
                ),
            ),
            Tool.from_function(
                func=reply_to_review_comment,
                name="reply_to_review_comment",
                description=("Reply to an existing inline review comment thread. Use comment id from get_pr_comments."),
            ),
        ]
