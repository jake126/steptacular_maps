from __future__ import annotations

import logging
from typing import Any

import requests

from .graphql import query_challenge_leaderboard, query_dailylog, query_team_member_leaderboard

logger = logging.getLogger(__name__)


class CountItClient:
    def __init__(self, api_url: str, headers: dict[str, str], timeout: int = 30) -> None:
        self.api_url = api_url
        self.headers = headers
        self.timeout = timeout
        self.session = requests.Session()

    def post(self, body: dict[str, Any]) -> dict[str, Any]:
        response = self.session.post(self.api_url, headers=self.headers, json=body, timeout=self.timeout)
        logger.info("POST %s -> %s", self.api_url, response.status_code)
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise RuntimeError(f"API request failed: {response.text}") from exc
        payload = response.json()
        if "errors" in payload:
            raise RuntimeError(f"GraphQL returned errors: {payload['errors']}")
        return payload

    def fetch_leaderboards(self, challenge_id: str) -> list[dict[str, Any]]:
        payload = self.post(query_challenge_leaderboard(challenge_id))
        return payload.get("data", {}).get("leaderboards", [])

    def fetch_team_members(self, challenge_id: str, team_id: str) -> list[str]:
        payload = self.post(query_team_member_leaderboard(challenge_id, team_id))
        leaderboards = payload.get("data", {}).get("teamMemberLeaderboard", {}).get("leaderboards", [])
        member_ids: list[str] = []
        for leaderboard in leaderboards:
            for entry in leaderboard.get("entries", []):
                member_id = entry.get("id")
                if member_id:
                    member_ids.append(member_id)
        return sorted(set(member_ids))

    def fetch_dailylog_page(
        self,
        challenge_id: str,
        user_id: str,
        before: str | None = None,
        after: str | None = None,
    ) -> dict[str, Any]:
        payload = self.post(query_dailylog(user_id, challenge_id, before=before, after=after))
        return payload.get("data", {}).get("dailyLog", {})
