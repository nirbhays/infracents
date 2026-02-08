"""
GitHub Service

Handles all interactions with the GitHub API:
- Fetching PR file lists
- Fetching file contents
- Creating and updating PR comments
- Managing GitHub App authentication (JWT + installation tokens)

Uses PyGithub for convenience but could be replaced with raw HTTP for
fewer dependencies.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import httpx
import jwt

from config import get_settings
from models.github import GitHubComment, GitHubFileInfo

logger = logging.getLogger(__name__)
settings = get_settings()

# The marker we use to identify our own comments (for updating instead of duplicating)
COMMENT_MARKER = "<!-- infracents-cost-estimate -->"


class GitHubService:
    """Service for interacting with the GitHub API.

    Uses GitHub App authentication:
    1. Generate a JWT signed with the App's private key
    2. Exchange the JWT for an installation access token
    3. Use the installation token for API calls

    The installation token is scoped to the specific org that installed the app
    and has only the permissions granted during installation.
    """

    def __init__(self):
        """Initialize the GitHub service."""
        self.base_url = "https://api.github.com"
        self._installation_tokens: dict[int, tuple[str, float]] = {}

    async def get_pr_files(
        self,
        installation_id: int,
        repo_full_name: str,
        pr_number: int,
    ) -> list[GitHubFileInfo]:
        """Fetch the list of files changed in a pull request.

        Args:
            installation_id: GitHub App installation ID.
            repo_full_name: Repository full name (org/repo).
            pr_number: Pull request number.

        Returns:
            List of file information objects.
        """
        token = await self._get_installation_token(installation_id)
        url = f"{self.base_url}/repos/{repo_full_name}/pulls/{pr_number}/files"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=self._auth_headers(token),
                params={"per_page": 100},
            )
            response.raise_for_status()

        files = []
        for file_data in response.json():
            files.append(
                GitHubFileInfo(
                    sha=file_data.get("sha", ""),
                    filename=file_data["filename"],
                    status=file_data["status"],
                    additions=file_data.get("additions", 0),
                    deletions=file_data.get("deletions", 0),
                    changes=file_data.get("changes", 0),
                    patch=file_data.get("patch"),
                )
            )

        logger.info(
            "Fetched %d files from %s PR #%d", len(files), repo_full_name, pr_number
        )
        return files

    async def get_file_content(
        self,
        installation_id: int,
        repo_full_name: str,
        file_path: str,
        ref: str,
    ) -> Optional[str]:
        """Fetch the content of a file at a specific git ref.

        Args:
            installation_id: GitHub App installation ID.
            repo_full_name: Repository full name (org/repo).
            file_path: Path to the file in the repo.
            ref: Git ref (branch name, commit SHA, tag).

        Returns:
            The file content as a string, or None if not found.
        """
        token = await self._get_installation_token(installation_id)
        url = f"{self.base_url}/repos/{repo_full_name}/contents/{file_path}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={
                    **self._auth_headers(token),
                    "Accept": "application/vnd.github.raw+json",
                },
                params={"ref": ref},
            )

            if response.status_code == 404:
                return None
            response.raise_for_status()

        return response.text

    async def create_or_update_comment(
        self,
        installation_id: int,
        repo_full_name: str,
        pr_number: int,
        body: str,
    ) -> int:
        """Create or update the InfraCents cost estimate comment on a PR.

        We look for an existing comment with our marker. If found, we update it.
        If not found, we create a new one. This prevents duplicate comments
        when a PR is updated multiple times.

        Args:
            installation_id: GitHub App installation ID.
            repo_full_name: Repository full name.
            pr_number: Pull request number.
            body: The Markdown comment body (should include COMMENT_MARKER).

        Returns:
            The comment ID.
        """
        token = await self._get_installation_token(installation_id)

        # Ensure the body includes our marker
        if COMMENT_MARKER not in body:
            body = f"{COMMENT_MARKER}\n{body}"

        # Check for existing comment
        existing_comment_id = await self._find_existing_comment(
            token, repo_full_name, pr_number
        )

        if existing_comment_id:
            # Update existing comment
            return await self._update_comment(
                token, repo_full_name, existing_comment_id, body
            )
        else:
            # Create new comment
            return await self._create_comment(
                token, repo_full_name, pr_number, body
            )

    async def _find_existing_comment(
        self,
        token: str,
        repo_full_name: str,
        pr_number: int,
    ) -> Optional[int]:
        """Find an existing InfraCents comment on a PR.

        Searches through PR comments for one containing our marker.
        """
        url = f"{self.base_url}/repos/{repo_full_name}/issues/{pr_number}/comments"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=self._auth_headers(token),
                params={"per_page": 100},
            )
            response.raise_for_status()

        for comment in response.json():
            if COMMENT_MARKER in comment.get("body", ""):
                logger.debug("Found existing InfraCents comment: %d", comment["id"])
                return comment["id"]

        return None

    async def _create_comment(
        self,
        token: str,
        repo_full_name: str,
        pr_number: int,
        body: str,
    ) -> int:
        """Create a new comment on a PR."""
        url = f"{self.base_url}/repos/{repo_full_name}/issues/{pr_number}/comments"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=self._auth_headers(token),
                json={"body": body},
            )
            response.raise_for_status()

        comment_id = response.json()["id"]
        logger.info("Created comment %d on %s PR #%d", comment_id, repo_full_name, pr_number)
        return comment_id

    async def _update_comment(
        self,
        token: str,
        repo_full_name: str,
        comment_id: int,
        body: str,
    ) -> int:
        """Update an existing comment."""
        url = f"{self.base_url}/repos/{repo_full_name}/issues/comments/{comment_id}"

        async with httpx.AsyncClient() as client:
            response = await client.patch(
                url,
                headers=self._auth_headers(token),
                json={"body": body},
            )
            response.raise_for_status()

        logger.info("Updated comment %d on %s", comment_id, repo_full_name)
        return comment_id

    async def _get_installation_token(self, installation_id: int) -> str:
        """Get an installation access token for API calls.

        Tokens are cached for 50 minutes (they expire after 1 hour).
        This JWT → installation token exchange is the standard GitHub App
        authentication flow.
        """
        # Check cache
        if installation_id in self._installation_tokens:
            token, expires_at = self._installation_tokens[installation_id]
            if time.time() < expires_at:
                return token

        # Generate JWT
        app_jwt = self._generate_jwt()

        # Exchange for installation token
        url = f"{self.base_url}/app/installations/{installation_id}/access_tokens"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                },
            )
            response.raise_for_status()

        data = response.json()
        token = data["token"]

        # Cache for 50 minutes (tokens expire in 1 hour)
        self._installation_tokens[installation_id] = (token, time.time() + 3000)

        logger.debug("Obtained installation token for installation %d", installation_id)
        return token

    def _generate_jwt(self) -> str:
        """Generate a JWT for GitHub App authentication.

        The JWT is signed with the App's private key and is valid for 10 minutes.
        It's used to exchange for installation-scoped access tokens.
        """
        if not settings.github_app_id or not settings.github_private_key:
            raise ValueError(
                "GITHUB_APP_ID and GITHUB_PRIVATE_KEY must be configured"
            )

        now = int(time.time())
        payload = {
            "iat": now - 60,  # Issued at (60 seconds in the past for clock skew)
            "exp": now + 600,  # Expires in 10 minutes
            "iss": settings.github_app_id,
        }

        # The private key may have escaped newlines from env vars
        private_key = settings.github_private_key.replace("\\n", "\n")

        return jwt.encode(payload, private_key, algorithm="RS256")

    def _auth_headers(self, token: str) -> dict[str, str]:
        """Build authorization headers for GitHub API calls."""
        return {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }


def has_terraform_changes(files: list[GitHubFileInfo]) -> bool:
    """Check if any of the changed files are Terraform files.

    Args:
        files: List of files changed in a PR.

    Returns:
        True if at least one .tf file was changed.
    """
    return any(f.is_terraform for f in files)


def get_terraform_files(files: list[GitHubFileInfo]) -> list[GitHubFileInfo]:
    """Filter to only Terraform files from a list of changed files."""
    return [f for f in files if f.is_terraform]
