from __future__ import annotations

import logging
import shutil
from datetime import date
from pathlib import Path

import pandas as pd

from .client import CountItClient
from .config import AppConfig
from .git_upload import commit_and_push_daily_outputs
from .map_export import generate_map_from_export
from .selectors import load_selection_csv, split_selected_entities
from .transforms import (
    attach_team_membership,
    build_cumulative_points,
    build_people_and_teams,
    build_team_membership_df,
    build_wide_export,
    get_export_dates_with_data,
    parse_dailylog_edges,
)

logger = logging.getLogger(__name__)


def resolve_selected_people(
    people_df: pd.DataFrame,
    team_membership_df: pd.DataFrame,
    selected_teams_df: pd.DataFrame,
    selected_people_df: pd.DataFrame,
) -> pd.DataFrame:
    selected_person_ids = set(selected_people_df["entity_id"].tolist())
    if not selected_teams_df.empty and not team_membership_df.empty:
        team_person_ids = set(
            team_membership_df.loc[
                team_membership_df["team_id"].isin(selected_teams_df["entity_id"]), "id"
            ].tolist()
        )
        selected_person_ids.update(team_person_ids)
    if not selected_person_ids:
        raise ValueError(
            "No people were selected. Add at least one person or one team with members in the selection CSV."
        )
    selected_people = people_df[people_df["id"].isin(selected_person_ids)].copy()
    if selected_people.empty:
        raise ValueError("Selected people IDs were not found in leaderboard metadata.")
    return selected_people


def write_daily_outputs(
    config: AppConfig,
    selection_df: pd.DataFrame,
    step_counts_df: pd.DataFrame,
    memberships_df: pd.DataFrame,
    export_year: int,
    export_month: int,
) -> dict[date, Path]:
    export_dates = get_export_dates_with_data(step_counts_df, export_year, export_month)
    if not export_dates:
        logger.warning(
            "No data dates found for %04d-%02d; no daily maps generated.",
            export_year,
            export_month,
        )
        return {}

    daily_dirs: dict[date, Path] = {}
    for output_date in export_dates:
        daily_dir = config.output_dir / output_date.isoformat()
        daily_dir.mkdir(parents=True, exist_ok=True)
        export_df = build_wide_export(
            selection_df=selection_df,
            step_counts_df=step_counts_df,
            memberships_df=memberships_df,
            year=export_year,
            month=export_month,
            end_date=output_date,
        )
        export_path = daily_dir / "export.csv"
        export_df.to_csv(export_path, index=False)
        generate_map_from_export(export_df=export_df, output_dir=daily_dir)
        daily_dirs[output_date] = daily_dir
        logger.info("Wrote daily export and map for %s", output_date.isoformat())

    # copy the last date into "latest" folder
    shutil.copytree(
        daily_dirs[max(export_dates)], config.output_dir / "latest", dirs_exist_ok=True
    )

    return daily_dirs


def run_pipeline(
    config: AppConfig,
    selection_csv: str | Path,
    export_year: int,
    export_month: int,
    upload_to_git: bool = True,
) -> dict[str, pd.DataFrame]:
    selection_df = load_selection_csv(selection_csv)
    selected_teams_df, selected_people_df = split_selected_entities(selection_df)

    client = CountItClient(api_url=config.api_url, headers=config.headers)
    leaderboards = client.fetch_leaderboards(config.challenge_id)
    teams_df, people_df = build_people_and_teams(leaderboards)

    selected_team_ids = set(selected_teams_df["entity_id"].tolist())
    unknown_team_ids = selected_team_ids.difference(set(teams_df["id"].tolist()))
    if unknown_team_ids:
        raise ValueError(
            f"Unknown team IDs in selection CSV: {sorted(unknown_team_ids)}"
        )

    selected_person_ids = set(selected_people_df["entity_id"].tolist())
    unknown_person_ids = selected_person_ids.difference(set(people_df["id"].tolist()))
    if unknown_person_ids:
        raise ValueError(
            f"Unknown person IDs in selection CSV: {sorted(unknown_person_ids)}"
        )

    team_memberships: list[dict[str, str]] = []
    for team_id in sorted(selected_team_ids):
        logger.info("Fetching team membership for team_id=%s", team_id)
        for member_id in client.fetch_team_members(config.challenge_id, team_id):
            team_memberships.append({"id": member_id, "team_id": team_id})

    memberships_df = build_team_membership_df(team_memberships)
    selected_people_full_df = resolve_selected_people(
        people_df, memberships_df, selected_teams_df, selected_people_df
    )
    selected_people_full_df = attach_team_membership(
        selected_people_full_df, memberships_df
    )

    step_count_rows: list[dict] = []
    for user_id in selected_people_full_df["id"].drop_duplicates():
        logger.info("Fetching daily log for user_id=%s", user_id)
        has_next_page = True
        after = None
        while has_next_page:
            page = client.fetch_dailylog_page(
                config.challenge_id, user_id=user_id, after=after
            )
            step_count_rows.extend(parse_dailylog_edges(user_id, page.get("edges", [])))
            page_info = page.get("pageInfo", {})
            has_next_page = bool(page_info.get("hasNextPage", False))
            after = page_info.get("endCursor")

    config.output_dir.mkdir(parents=True, exist_ok=True)
    step_counts_df = pd.DataFrame(step_count_rows)
    if not step_counts_df.empty:
        step_counts_df = step_counts_df.sort_values(["user_id", "date"]).reset_index(
            drop=True
        )

    metrics_df = build_cumulative_points(step_counts_df)
    full_export_df = build_wide_export(
        selection_df, step_counts_df, memberships_df, export_year, export_month
    )
    result_teams_df = teams_df[teams_df["id"].isin(selected_team_ids)].copy()

    standard_outputs = {
        "selected_entities": selection_df.reset_index(drop=True),
        "teams": result_teams_df.reset_index(drop=True),
        "people": selected_people_full_df.reset_index(drop=True),
        "step_counts": step_counts_df.reset_index(drop=True),
        "metrics": metrics_df.reset_index(drop=True),
        "export": full_export_df.reset_index(drop=True),
    }
    for name, df in standard_outputs.items():
        df.to_csv(config.output_dir / f"{name}.csv", index=False)

    daily_dirs = write_daily_outputs(
        config, selection_df, step_counts_df, memberships_df, export_year, export_month
    )
    if upload_to_git:
        commit_and_push_daily_outputs(daily_dirs, config.git)

    return standard_outputs
