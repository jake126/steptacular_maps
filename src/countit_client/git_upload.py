from __future__ import annotations

import subprocess
from datetime import date, datetime
from pathlib import Path

from .config import GitConfig


def run_git(cmd: list[str], cwd: Path) -> str:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result.stdout.strip()


def commit_and_push_daily_outputs(
    daily_output_dirs: dict[date, Path], git_config: GitConfig
) -> bool:
    if not git_config.enabled:
        print("Git upload disabled in config.")
        return False
    if not daily_output_dirs:
        print("No daily outputs to upload.")
        return False

    run_git(["git", "add", "."], cwd=Path.cwd())

    status = run_git(["git", "status", "--porcelain"], cwd=Path.cwd())
    if not status:
        print("No Git changes detected; nothing to commit.")
        return False

    first_date = min(daily_output_dirs).isoformat()
    last_date = max(daily_output_dirs).isoformat()
    commit_message = f"Update Steptacular maps {first_date} to {last_date} ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
    run_git(["git", "commit", "-m", commit_message], cwd=Path.cwd())
    run_git(["git", "push", "origin", git_config.branch], cwd=Path.cwd())
    print(
        f"Uploaded {len(daily_output_dirs)} dated map folder(s) to {git_config.repo_url} on {git_config.branch}."
    )
    return True
