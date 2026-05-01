from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_API_URL = "https://api.count.it/graphql"
DEFAULT_CONFIG_PATH = Path("config/config.json")


@dataclass(frozen=True)
class GitConfig:
    enabled: bool = True
    repo_url: str = "https://github.com/jake126/steptacular_maps.git"
    branch: str = "main"


@dataclass(frozen=True)
class AppConfig:
    api_url: str
    authorization: str
    app_build: str | None = None
    device_id: str | None = None
    challenge_id: str = "680a51b4db908edfc4fc31a4"
    output_dir: Path = Path("output")
    config_path: Path = DEFAULT_CONFIG_PATH
    git: GitConfig = GitConfig()

    @property
    def headers(self) -> dict[str, str]:
        headers = {
            "accept": "*/*",
            "content-type": "application/json",
            "authorization": self.authorization,
        }
        if self.app_build:
            headers["app_build"] = str(self.app_build)
        if self.device_id:
            headers["device_id"] = str(self.device_id)
        return headers


def load_config(config_path: str | Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}. Create config/config.json first."
        )

    data = json.loads(path.read_text(encoding="utf-8"))
    authorization = str(data.get("authorization", "")).strip()
    if not authorization:
        raise ValueError(
            "config/config.json must include a non-empty 'authorization' value."
        )

    challenge_id = str(data.get("challenge_id", "")).strip()
    if not challenge_id:
        raise ValueError(
            "config/config.json must include a non-empty 'challenge_id' value."
        )

    git_data = data.get("git", {}) or {}
    output_dir = Path(data.get("output_dir", "YYYY"))
    git = GitConfig(
        enabled=bool(git_data.get("enabled", True)),
        repo_url=str(
            git_data.get("repo_url", "https://github.com/jake126/steptacular_maps.git")
        ),
        branch=str(git_data.get("branch", "main")),
    )

    return AppConfig(
        api_url=str(data.get("api_url", DEFAULT_API_URL)).strip() or DEFAULT_API_URL,
        authorization=authorization,
        app_build=(
            str(data["app_build"]).strip()
            if data.get("app_build") is not None
            else None
        ),
        device_id=(
            str(data["device_id"]).strip()
            if data.get("device_id") is not None
            else None
        ),
        challenge_id=challenge_id,
        output_dir=output_dir,
        config_path=path,
        git=git,
    )
