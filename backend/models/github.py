"""
GitHub Webhook Event Models

Pydantic models for GitHub webhook payloads. We only model the fields
we actually use to keep things focused and maintainable.

Reference: https://docs.github.com/en/webhooks/webhook-events-and-payloads
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class GitHubUser(BaseModel):
    """GitHub user (author of a PR, committer, etc.)."""
    id: int
    login: str
    avatar_url: Optional[str] = None


class GitHubRepository(BaseModel):
    """GitHub repository information from a webhook payload."""
    id: int
    full_name: str = Field(..., description="org/repo format")
    name: str
    private: bool = False
    default_branch: str = "main"
    owner: Optional[GitHubUser] = None


class GitHubBranch(BaseModel):
    """Branch reference in a PR (head or base)."""
    sha: str
    ref: str
    label: Optional[str] = None


class GitHubPullRequest(BaseModel):
    """Pull request data from a webhook payload."""
    id: int
    number: int
    title: str
    state: str = "open"
    head: GitHubBranch
    base: GitHubBranch
    user: GitHubUser
    body: Optional[str] = None
    draft: bool = False
    mergeable: Optional[bool] = None
    changed_files: Optional[int] = None
    additions: Optional[int] = None
    deletions: Optional[int] = None


class GitHubInstallation(BaseModel):
    """GitHub App installation information."""
    id: int
    account: Optional[GitHubUser] = None
    app_id: Optional[int] = None


class PullRequestEvent(BaseModel):
    """GitHub pull_request webhook event payload.

    This is the primary event that triggers cost estimation.
    We handle 'opened', 'synchronize', and 'reopened' actions.
    """
    action: str = Field(
        ...,
        description="Event action (opened, synchronize, reopened, closed, etc.)",
    )
    number: int = Field(..., description="PR number")
    pull_request: GitHubPullRequest
    repository: GitHubRepository
    installation: Optional[GitHubInstallation] = None
    sender: Optional[GitHubUser] = None

    @property
    def should_process(self) -> bool:
        """Check if this event should trigger cost analysis.

        We only process PRs that are opened, updated (synchronize),
        or reopened. We skip closed PRs and draft PRs.
        """
        processable_actions = {"opened", "synchronize", "reopened"}
        return (
            self.action in processable_actions
            and not self.pull_request.draft
        )

    @property
    def repo_full_name(self) -> str:
        """Get the full repository name (org/repo)."""
        return self.repository.full_name

    @property
    def installation_id(self) -> Optional[int]:
        """Get the GitHub App installation ID."""
        return self.installation.id if self.installation else None


class InstallationEvent(BaseModel):
    """GitHub installation webhook event payload.

    Fired when the GitHub App is installed or uninstalled from an org.
    """
    action: str = Field(
        ...,
        description="Event action (created, deleted, suspend, unsuspend)",
    )
    installation: GitHubInstallation
    repositories: Optional[list[GitHubRepository]] = None
    sender: Optional[GitHubUser] = None


class GitHubFileInfo(BaseModel):
    """Information about a file in a PR (from the GitHub files API)."""
    sha: str
    filename: str
    status: str  # added, modified, removed, renamed
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    patch: Optional[str] = None

    @property
    def is_terraform(self) -> bool:
        """Check if this file is a Terraform configuration file."""
        return (
            self.filename.endswith(".tf")
            or self.filename.endswith(".tf.json")
        )


class GitHubComment(BaseModel):
    """A PR comment (for creating or updating cost estimate comments)."""
    id: Optional[int] = None
    body: str
    user: Optional[GitHubUser] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class WebhookPayload(BaseModel):
    """Generic webhook payload wrapper.

    Used for initial parsing before we determine the specific event type.
    """
    action: Optional[str] = None
    installation: Optional[GitHubInstallation] = None
    repository: Optional[GitHubRepository] = None
    # The raw payload for specific event parsing
    raw: dict[str, Any] = Field(default_factory=dict)
