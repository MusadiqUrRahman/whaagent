"""Tests for whaagent package - GitHub PR reviewer module."""

import os
from unittest.mock import MagicMock, patch

from whaagent.agents.github_pr_reviewer import (
    GithubPrReviewerAgent,
    _check_token,
    _get_headers,
    _github_request,
    get_pr_comments,
    get_pr_diff,
    get_pr_metadata,
    post_general_comment,
    post_review_comment,
    reply_to_review_comment,
)


def test_github_check_token_missing():
    """Test _check_token returns error when token is missing."""
    with patch.dict(os.environ, {"GITHUB_TOKEN": ""}, clear=True):
        result = _check_token()
        assert result is not None
        assert "GITHUB_TOKEN environment variable is not set" in result


def test_github_check_token_present():
    """Test _check_token returns None when token is present."""
    with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"}):
        result = _check_token()
        assert result is None


def test_github_get_headers():
    """Test _get_headers builds correct headers."""
    with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"}):
        headers = _get_headers()

        assert headers["Authorization"] == "Bearer test_token"
        assert headers["Accept"] == "application/vnd.github+json"
        assert headers["X-GitHub-Api-Version"] == "2022-11-28"


def test_github_request_success():
    """Test _github_request returns response on success."""
    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("whaagent.agents.github_pr_reviewer.requests.get", return_value=mock_response):
        response = _github_request("get", "https://api.github.com/test")
        assert response.status_code == 200


def test_github_request_retry_429():
    """Test _github_request retries on 429 status."""
    mock_responses = [
        MagicMock(status_code=429),  # First attempt
        MagicMock(status_code=200),  # Second attempt (success)
    ]

    with (
        patch("whaagent.agents.github_pr_reviewer.requests.get", side_effect=mock_responses),
        patch("whaagent.agents.github_pr_reviewer.time.sleep"),
    ):
        response = _github_request("get", "https://api.github.com/test")
        assert response.status_code == 200


def test_github_request_retry_503():
    """Test _github_request retries on 503 status."""
    mock_responses = [
        MagicMock(status_code=503),
        MagicMock(status_code=503),
        MagicMock(status_code=200),
    ]

    with (
        patch("whaagent.agents.github_pr_reviewer.requests.get", side_effect=mock_responses),
        patch("whaagent.agents.github_pr_reviewer.time.sleep"),
    ):
        response = _github_request("get", "https://api.github.com/test")
        assert response.status_code == 200


def test_github_request_max_retries():
    """Test _github_request gives up after max retries."""
    mock_response = MagicMock(status_code=429)

    with (
        patch("whaagent.agents.github_pr_reviewer.requests.get", return_value=mock_response),
        patch("whaagent.agents.github_pr_reviewer.time.sleep"),
    ):
        response = _github_request("get", "https://api.github.com/test")
        assert response.status_code == 429


def test_github_get_pr_diff_success():
    """Test get_pr_diff with successful response."""
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {
            "filename": "test.py",
            "status": "modified",
            "additions": 10,
            "deletions": 5,
            "patch": "@@ -1,1 +1,2 @@\n-old\n+new\n",
        }
    ]
    mock_response.raise_for_status = MagicMock()

    with (
        patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"}),
        patch("whaagent.agents.github_pr_reviewer._github_request", return_value=mock_response),
    ):
        result = get_pr_diff("owner/repo", 123)
        assert "PR #123 diff for owner/repo" in result
        assert "test.py" in result
        assert "+10/-5" in result


def test_github_get_pr_diff_missing_token():
    """Test get_pr_diff with missing token."""
    with patch.dict(os.environ, {"GITHUB_TOKEN": ""}, clear=True):
        result = get_pr_diff("owner/repo", 123)
        assert "GITHUB_TOKEN environment variable is not set" in result


def test_github_get_pr_diff_error():
    """Test get_pr_diff with API error."""
    with (
        patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"}),
        patch("whaagent.agents.github_pr_reviewer._github_request") as mock_request,
    ):
        mock_request.side_effect = Exception("API error")
        result = get_pr_diff("owner/repo", 123)
        assert "Error fetching PR diff" in result


def test_github_get_pr_comments_success():
    """Test get_pr_comments with successful response."""
    review_response = MagicMock()
    review_response.json.return_value = [
        {"id": 1, "user": {"login": "user1"}, "path": "test.py", "line": 10, "body": "comment1"}
    ]
    review_response.raise_for_status = MagicMock()

    issue_response = MagicMock()
    issue_response.json.return_value = [{"id": 2, "user": {"login": "user2"}, "body": "comment2"}]
    issue_response.raise_for_status = MagicMock()

    with (
        patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"}),
        patch("whaagent.agents.github_pr_reviewer._github_request", side_effect=[review_response, issue_response]),
    ):
        result = get_pr_comments("owner/repo", 123)
        assert "Comments for PR #123 in owner/repo:" in result
        assert "Inline Review Comments" in result
        assert "General Comments" in result


def test_github_get_pr_comments_empty():
    """Test get_pr_comments with no comments."""
    review_response = MagicMock()
    review_response.json.return_value = []
    review_response.raise_for_status = MagicMock()

    issue_response = MagicMock()
    issue_response.json.return_value = []
    issue_response.raise_for_status = MagicMock()

    with (
        patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"}),
        patch("whaagent.agents.github_pr_reviewer._github_request", side_effect=[review_response, issue_response]),
    ):
        result = get_pr_comments("owner/repo", 123)
        assert "None" in result


def test_github_post_review_comment_success():
    """Test post_review_comment with successful response."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"html_url": "https://github.com/repo/pull/123#comment-1"}
    mock_response.raise_for_status = MagicMock()

    with (
        patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"}),
        patch("whaagent.agents.github_pr_reviewer._github_request", return_value=mock_response),
    ):
        result = post_review_comment("owner/repo", 123, "abc123", "test.py", 10, "test comment")
        assert "Posted inline review comment on test.py:10" in result
        assert "https://github.com/" in result


def test_github_post_review_comment_invalid_line():
    """Test post_review_comment with invalid line number."""
    with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"}):
        result = post_review_comment("owner/repo", 123, "abc123", "test.py", 0, "test comment")
        assert "line must be a positive integer" in result

        result2 = post_review_comment("owner/repo", 123, "abc123", "test.py", -5, "test comment")
        assert "line must be a positive integer" in result2


def test_github_post_review_comment_missing_token():
    """Test post_review_comment with missing token."""
    with patch.dict(os.environ, {"GITHUB_TOKEN": ""}, clear=True):
        result = post_review_comment("owner/repo", 123, "abc123", "test.py", 10, "test comment")
        assert "GITHUB_TOKEN environment variable is not set" in result


def test_github_post_general_comment_success():
    """Test post_general_comment with successful response."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"html_url": "https://github.com/repo/pull/123#comment-2"}
    mock_response.raise_for_status = MagicMock()

    with (
        patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"}),
        patch("whaagent.agents.github_pr_reviewer._github_request", return_value=mock_response),
    ):
        result = post_general_comment("owner/repo", 123, "general comment")
        assert "Posted general comment on PR #123" in result
        assert "https://github.com/" in result


def test_github_post_general_comment_missing_token():
    """Test post_general_comment with missing token."""
    with patch.dict(os.environ, {"GITHUB_TOKEN": ""}, clear=True):
        result = post_general_comment("owner/repo", 123, "general comment")
        assert "GITHUB_TOKEN environment variable is not set" in result


def test_github_reply_to_review_comment_success():
    """Test reply_to_review_comment with successful response."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"html_url": "https://github.com/repo/pull/123#comment-3"}
    mock_response.raise_for_status = MagicMock()

    with (
        patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"}),
        patch("whaagent.agents.github_pr_reviewer._github_request", return_value=mock_response),
    ):
        result = reply_to_review_comment("owner/repo", 123, 456, "reply text")
        assert "Replied to comment #456 on PR #123" in result
        assert "https://github.com/" in result


def test_github_reply_to_review_comment_missing_token():
    """Test reply_to_review_comment with missing token."""
    with patch.dict(os.environ, {"GITHUB_TOKEN": ""}, clear=True):
        result = reply_to_review_comment("owner/repo", 123, 456, "reply text")
        assert "GITHUB_TOKEN environment variable is not set" in result


def test_github_get_pr_metadata_success():
    """Test get_pr_metadata with successful response."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "title": "Test PR",
        "body": "PR description",
        "user": {"login": "testuser"},
        "state": "open",
        "base": {"ref": "main"},
        "head": {"ref": "feature", "sha": "abc123def456"},
        "changed_files": 10,
        "additions": 100,
        "deletions": 50,
    }
    mock_response.raise_for_status = MagicMock()

    with (
        patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"}),
        patch("whaagent.agents.github_pr_reviewer._github_request", return_value=mock_response),
    ):
        result = get_pr_metadata("owner/repo", 123)
        assert "PR #123: Test PR" in result
        assert "Author: testuser" in result
        assert "Head SHA: abc123def456" in result
        assert "+100/-50" in result


def test_github_get_pr_metadata_missing_token():
    """Test get_pr_metadata with missing token."""
    with patch.dict(os.environ, {"GITHUB_TOKEN": ""}, clear=True):
        result = get_pr_metadata("owner/repo", 123)
        assert "GITHUB_TOKEN environment variable is not set" in result


def test_github_get_pr_metadata_long_description():
    """Test get_pr_metadata truncates long description."""
    long_desc = "a" * 3000
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "title": "Test PR",
        "body": long_desc,
        "user": {"login": "testuser"},
        "state": "open",
        "base": {"ref": "main"},
        "head": {"ref": "feature", "sha": "abc123"},
        "changed_files": 1,
        "additions": 1,
        "deletions": 0,
    }
    mock_response.raise_for_status = MagicMock()

    with (
        patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"}),
        patch("whaagent.agents.github_pr_reviewer._github_request", return_value=mock_response),
    ):
        result = get_pr_metadata("owner/repo", 123)
        # Description should be truncated to 2000 characters
        assert len(result.split("Description:\n")[1]) <= 2000


def test_github_pr_reviewer_agent_initialization():
    """Test GithubPrReviewerAgent can be initialized."""
    agent = GithubPrReviewerAgent()
    assert agent is not None
    assert agent.system_prompt is not None


def test_github_pr_reviewer_agent_local_tools():
    """Test GithubPrReviewerAgent has correct local tools."""
    agent = GithubPrReviewerAgent()
    tools = agent.local_tools()

    assert len(tools) == 6
    tool_names = [t.name for t in tools]
    assert "get_pr_metadata" in tool_names
    assert "get_pr_diff" in tool_names
    assert "get_pr_comments" in tool_names
    assert "post_review_comment" in tool_names
    assert "post_general_comment" in tool_names
    assert "reply_to_review_comment" in tool_names


def test_github_pr_reviewer_agent_tool_descriptions():
    """Test GithubPrReviewerAgent tools have descriptions."""
    agent = GithubPrReviewerAgent()
    tools = agent.local_tools()

    for tool in tools:
        assert tool.description is not None
        assert len(tool.description) > 0
