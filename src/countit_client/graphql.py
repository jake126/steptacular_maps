from __future__ import annotations


def query_challenge_leaderboard(challenge_id: str) -> dict:
    return {
        "variables": {"challengeId": challenge_id, "leaderboardIds": None},
        "query": """
            query Query_ChallengeLeaderboard($challengeId: ID!, $leaderboardIds: [ID!]) {
                leaderboards(challengeId: $challengeId, leaderboardIds: $leaderboardIds) {
                    id
                    name
                    firstName
                    lastName
                    type
                }
            }
        """,
    }


def query_team_member_leaderboard(challenge_id: str, team_id: str, version: int = 2) -> dict:
    return {
        "variables": {"challengeId": challenge_id, "teamId": team_id, "version": version},
        "query": """
            query Query_TeamMemberLeaderboard(
                $challengeId: ID!
                $teamId: ID!
                $version: Int!
                $date: ISO8601Date
            ) {
                teamMemberLeaderboard(
                    challengeId: $challengeId
                    teamId: $teamId
                    date: $date
                    version: $version
                ) {
                    leaderboards {
                        entries { id }
                    }
                }
            }
        """,
    }


def query_dailylog(
    user_id: str,
    challenge_id: str,
    before: str | None = None,
    after: str | None = None,
    version: int = 3,
) -> dict:
    return {
        "variables": {
            "userId": str(user_id),
            "challengeId": str(challenge_id),
            "before": str(before) if before else None,
            "after": str(after) if after else None,
            "version": version,
        },
        "query": """
            query Query_DailyLog(
                $userId: ID
                $challengeId: ID!
                $version: Int
                $after: String
                $before: String
            ) {
                dailyLog(
                    challengeId: $challengeId,
                    userId: $userId,
                    version: $version,
                    after: $after,
                    before: $before
                ) {
                    pageInfo {
                        startCursor
                        endCursor
                        hasPreviousPage
                        hasNextPage
                        total
                    }
                    edges {
                        cursor
                        node {
                            id
                            type
                            activityEntry { score }
                        }
                    }
                }
            }
        """,
    }
