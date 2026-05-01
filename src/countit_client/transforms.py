from __future__ import annotations

import calendar
import re
from datetime import date, datetime
from typing import Any

import pandas as pd


def build_people_and_teams(
    leaderboards: list[dict[str, Any]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_df = pd.DataFrame.from_records(leaderboards)
    if all_df.empty:
        return pd.DataFrame(columns=["id", "name"]), pd.DataFrame(
            columns=["id", "first_name", "last_name"]
        )

    teams_df = (
        all_df[all_df["type"] == "team"][["id", "name"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    people_df = (
        all_df[all_df["type"] == "people"][["id", "firstName", "lastName"]]
        .rename(columns={"firstName": "first_name", "lastName": "last_name"})
        .drop_duplicates()
        .reset_index(drop=True)
    )
    return teams_df, people_df


def parse_dailylog_edges(
    user_id: str, edges: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    current_date = None
    for edge in edges:
        node = edge.get("node", {})
        node_type = node.get("type")
        if node_type == "day_entry":
            raw_id = str(node.get("id", "")).replace("day:", "")
            try:
                current_date = datetime.strptime(raw_id, "%Y-%m-%d").date()
            except ValueError:
                current_date = None
        elif node_type == "activity_entry" and current_date is not None:
            score = node.get("activityEntry", {}).get("score")
            score_digits = re.sub(r"[^0-9]", "", str(score))
            if not score_digits:
                continue
            step_count = int(score_digits)
            points = step_count if step_count < 10000 else step_count + 2500
            records.append(
                {
                    "user_id": user_id,
                    "date": current_date,
                    "step_count": step_count,
                    "points": points,
                }
            )
    return records


def build_team_membership_df(team_memberships: list[dict[str, str]]) -> pd.DataFrame:
    if not team_memberships:
        return pd.DataFrame(columns=["id", "team_id"])
    return pd.DataFrame(team_memberships).drop_duplicates().reset_index(drop=True)


def attach_team_membership(
    people_df: pd.DataFrame, memberships_df: pd.DataFrame
) -> pd.DataFrame:
    if memberships_df.empty:
        out = people_df.copy()
        out["team_id"] = pd.NA
        return out
    return people_df.merge(memberships_df, how="left", on="id")


def build_cumulative_points(step_counts_df: pd.DataFrame) -> pd.DataFrame:
    if step_counts_df.empty:
        return step_counts_df.copy()
    cumulative = (
        step_counts_df.sort_values(["user_id", "date"])
        .set_index(["date", "user_id"])
        .groupby(["user_id"])[["step_count", "points"]]
        .cumsum()
        .reset_index()
        .rename(
            columns={
                "step_count": "step_count_cumulative",
                "points": "points_cumulative",
            }
        )
    )
    ranked = step_counts_df.merge(cumulative, on=["date", "user_id"], how="left")
    ranked["rank"] = ranked.groupby("date")["points_cumulative"].rank(
        method="dense", ascending=False
    )
    return ranked


def build_date_columns(
    year: int, month: int, end_date: date | None = None
) -> list[date]:
    _, days_in_month = calendar.monthrange(year, month)
    dates = [date(year, month, day) for day in range(1, days_in_month + 1)]
    if end_date is not None:
        dates = [d for d in dates if d <= end_date]
    return dates


def format_export_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def build_wide_export(
    selection_df: pd.DataFrame,
    step_counts_df: pd.DataFrame,
    memberships_df: pd.DataFrame,
    year: int,
    month: int,
    end_date: date | None = None,
) -> pd.DataFrame:
    export_dates = build_date_columns(year, month, end_date=end_date)
    date_columns = [format_export_date(day) for day in export_dates]
    base_columns = ["EntityType", "EntityName", "PNG", "Gender", "Height", "Team"]

    if selection_df.empty:
        return pd.DataFrame(columns=base_columns + date_columns)

    selected_rows = selection_df[
        selection_df["entity_type"].isin(["person", "team"])
    ].copy()
    selected_rows = selected_rows.drop_duplicates(
        subset=["entity_type", "entity_id"]
    ).reset_index(drop=True)

    def zero_export(rows: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(
            {
                "EntityType": rows["entity_type"],
                "EntityName": rows["entity_name"],
                "PNG": rows["png"],
                "Gender": rows["gender"],
                "Height": rows["height"],
                "Team": rows["team"],
            }
        )
        for column in date_columns:
            out[column] = 0
        return out[base_columns + date_columns]

    if step_counts_df.empty or not export_dates:
        return zero_export(selected_rows)

    selected_people = selected_rows[selected_rows["entity_type"] == "person"][
        ["entity_id", "entity_name", "png", "gender", "height", "team"]
    ].copy()
    selected_teams = selected_rows[selected_rows["entity_type"] == "team"][
        ["entity_id", "entity_name", "png", "gender", "height", "team"]
    ].copy()

    person_ids = set(selected_people["entity_id"].astype(str).tolist())
    if not memberships_df.empty:
        person_ids.update(memberships_df["id"].dropna().astype(str).tolist())
    person_ids = sorted(person_ids)

    filtered_steps = step_counts_df.copy()
    filtered_steps["user_id"] = filtered_steps["user_id"].astype(str)
    filtered_steps["date"] = pd.to_datetime(filtered_steps["date"]).dt.date
    filtered_steps = filtered_steps[filtered_steps["user_id"].isin(person_ids)]

    person_frames: list[pd.DataFrame] = []
    for user_id in person_ids:
        entity_dates = pd.DataFrame({"date": export_dates})
        daily = (
            filtered_steps[filtered_steps["user_id"] == str(user_id)]
            .groupby("date", as_index=False)["points"]
            .sum()
            .sort_values("date")
        )
        completed = entity_dates.merge(daily, on="date", how="left").sort_values("date")
        completed["points"] = completed["points"].fillna(0)
        completed["value"] = completed["points"].cumsum().astype(int)
        completed["user_id"] = str(user_id)
        person_frames.append(completed[["user_id", "date", "value"]])
    person_panel = (
        pd.concat(person_frames, ignore_index=True)
        if person_frames
        else pd.DataFrame(columns=["user_id", "date", "value"])
    )

    rows: list[dict[str, object]] = []
    for _, row in selected_people.iterrows():
        values = person_panel[person_panel["user_id"] == str(row["entity_id"])]
        export_row = {
            "EntityType": "person",
            "EntityName": row["entity_name"],
            "PNG": row["png"],
            "Gender": row["gender"],
            "Height": row["height"],
            "Team": row["team"],
        }
        value_map = {format_export_date(d): 0 for d in export_dates}
        for _, value_row in values.iterrows():
            value_map[format_export_date(value_row["date"])] = int(value_row["value"])
        export_row.update(value_map)
        rows.append(export_row)

    for _, row in selected_teams.iterrows():
        member_ids: list[str] = []
        if not memberships_df.empty:
            member_ids = (
                memberships_df[
                    memberships_df["team_id"].astype(str) == str(row["entity_id"])
                ]["id"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )
        team_values = {format_export_date(d): 0 for d in export_dates}
        if member_ids:
            team_panel = person_panel[person_panel["user_id"].isin(member_ids)].copy()
            if not team_panel.empty:
                summed = team_panel.groupby("date", as_index=False)["value"].sum()
                for _, value_row in summed.iterrows():
                    team_values[format_export_date(value_row["date"])] = int(
                        value_row["value"]
                    )
        export_row = {
            "EntityType": "team",
            "EntityName": row["entity_name"],
            "PNG": row["png"],
            "Gender": row["gender"],
            "Height": row["height"],
            "Team": row["team"],
        }
        export_row.update(team_values)
        rows.append(export_row)

    out = pd.DataFrame(rows)
    if out.empty:
        return zero_export(selected_rows)
    for column in date_columns:
        if column not in out.columns:
            out[column] = 0
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0).astype(int)
    return out[base_columns + date_columns]


def get_export_dates_with_data(
    step_counts_df: pd.DataFrame, year: int, month: int
) -> list[date]:
    if step_counts_df.empty:
        return []
    dates = pd.to_datetime(step_counts_df["date"]).dt.date
    return sorted({d for d in dates if d.year == year and d.month == month})
