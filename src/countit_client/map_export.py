from __future__ import annotations

import base64
import json
import pickle
from datetime import datetime
from pathlib import Path
from typing import Dict

import folium
import numpy as np
import pandas as pd
from geopy import Point
from geopy.distance import geodesic

USE_PIC = True
SHOW_COMPANY_ICON = True
START_COORDS = (55.9533, -3.1883)
EDINBURGH = (55.9533, -3.1883)
DOVER = (51.1290, 1.3210)
CALAIS = (50.9513, 1.8587)
ISTANBUL = (41.0082, 28.9784)
KATHMANDU = (27.7103, 85.3222)
DODGE_THRESHOLD_KM = 5
DODGE_OFFSET_KM = 2
ED_TO_DOVER_KM = geodesic(EDINBURGH, DOVER).km
CALAIS_TO_ISTANBUL_KM = geodesic(CALAIS, ISTANBUL).km
ISTANBUL_TO_KATHMANDU_KM = geodesic(ISTANBUL, KATHMANDU).km
ENCODED_IMG_FILENAME = "src/img/encoded.json"


def load_encoded_imgs() -> Dict[str, str]:
    with open(ENCODED_IMG_FILENAME, "rb") as f:
        data = json.load(f)
    return data


def save_encoded_uri_to_file(path_to_png: str, encoded_uri: str) -> None:
    ENCODED_IMG_MAP[path_to_png] = encoded_uri
    with open(ENCODED_IMG_FILENAME, "wb") as f:
        pickle.dump(ENCODED_IMG_MAP, f)


ENCODED_IMG_MAP = load_encoded_imgs()


def encode_image_as_base64_uri(path_to_png: str | Path) -> str | None:
    if path_to_png in ENCODED_IMG_MAP:
        return ENCODED_IMG_MAP[path_to_png]
    try:
        with open(path_to_png, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
            suffix = Path(path_to_png).suffix.lower()
            mime = "image/png" if suffix == ".png" else "image/jpeg"
            encoded_uri = f"data:{mime};base64,{encoded}"
            save_encoded_uri_to_file(path_to_png, encoded_uri)
            return encoded_uri
    except Exception as exc:
        print(f"Could not load image for marker: {exc}")
        return None


def is_date_column(colname: str) -> bool:
    try:
        datetime.strptime(str(colname), "%d/%m/%Y")
        return True
    except Exception:
        return False


def unit_vector(
    p1: tuple[float, float], p2: tuple[float, float]
) -> tuple[float, float]:
    lat1, lon1 = p1
    lat2, lon2 = p2
    dx = lon2 - lon1
    dy = lat2 - lat1
    mag = np.hypot(dx, dy)
    return (dx / mag, dy / mag)


def perpendicular(v: tuple[float, float]) -> tuple[float, float]:
    dx, dy = v
    return (-dy, dx)


def get_segment_index(latlon: tuple[float, float]) -> int:
    if geodesic(EDINBURGH, latlon).km < 550:
        return 0
    return 1


def compute_distance(row: pd.Series, steps_col: str) -> float:
    multiplier = 0.413 if str(row["gender"]).lower() == "female" else 0.415
    step_length = (float(row["height"]) * multiplier) / 2
    return (step_length * float(row[steps_col])) / 1000


def interpolate_point(
    start: tuple[float, float], end: tuple[float, float], fraction: float
) -> tuple[float, float]:
    start_point = Point(start)
    end_point = Point(end)
    lat = start_point.latitude + (end_point.latitude - start_point.latitude) * fraction
    lon = (
        start_point.longitude + (end_point.longitude - start_point.longitude) * fraction
    )
    return (lat, lon)


def get_straightline_land_path_destination(dist_km: float) -> tuple[float, float]:
    if dist_km <= ED_TO_DOVER_KM:
        return interpolate_point(EDINBURGH, DOVER, dist_km / ED_TO_DOVER_KM)
    remaining = dist_km - ED_TO_DOVER_KM
    if remaining <= CALAIS_TO_ISTANBUL_KM:
        return interpolate_point(CALAIS, ISTANBUL, remaining / CALAIS_TO_ISTANBUL_KM)
    if remaining <= ISTANBUL_TO_KATHMANDU_KM:
        return interpolate_point(
            ISTANBUL, KATHMANDU, remaining / ISTANBUL_TO_KATHMANDU_KM
        )
    return KATHMANDU


def generate_map_from_export(
    export_df: pd.DataFrame,
    output_dir: str | Path,
    company_icon_path: str | Path = "img/blend.png",
    output_html_name: str = "steptacular.html",
) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    df = export_df.copy()

    # if "EntityType" in df.columns:
    #     df = df[df["EntityType"].astype(str).str.lower() == "person"].copy()

    if df.empty:
        raise ValueError("Map export requires at least one person row in export.csv.")

    date_colnames = [col for col in df.columns if is_date_column(col)]
    if len(date_colnames) < 1:
        raise ValueError("Map export requires at least one date column in export.csv.")
    sorted_dates = sorted(date_colnames, key=lambda x: datetime.strptime(x, "%d/%m/%Y"))
    latest_date_str = sorted_dates[-1]
    prev_date_str = sorted_dates[-2] if len(sorted_dates) > 1 else latest_date_str

    df = df.rename(
        columns={
            "EntityName": "person",
            "PNG": "path_to_png",
            "Gender": "gender",
            "Height": "height",
        }
    )
    input_data = pd.DataFrame(
        {
            "person": df["person"],
            "path_to_png": df["path_to_png"],
            "gender": df["gender"].astype(str).str.lower(),
            "height": df["height"],
            "prev_steps": df[prev_date_str],
            "no_steps": df[latest_date_str],
        }
    )
    input_data["no_steps"] = pd.to_numeric(input_data["no_steps"], errors="coerce")
    input_data["prev_steps"] = pd.to_numeric(
        input_data["prev_steps"], errors="coerce"
    ).fillna(input_data["no_steps"])
    input_data = input_data.dropna(subset=["no_steps", "height"]).reset_index(drop=True)

    dir_vectors = [
        unit_vector(EDINBURGH, DOVER),
        unit_vector(CALAIS, ISTANBUL),
        unit_vector(ISTANBUL, KATHMANDU),
    ]
    perp_vectors = [perpendicular(v) for v in dir_vectors]
    input_data["distance_km"] = input_data.apply(
        lambda row: compute_distance(row, "no_steps"), axis=1
    )
    input_data["prev_distance_km"] = input_data.apply(
        lambda row: compute_distance(row, "prev_steps"), axis=1
    )

    dest_coords = [
        get_straightline_land_path_destination(row["distance_km"])
        for _, row in input_data.iterrows()
    ]
    prev_dest_coords = [
        get_straightline_land_path_destination(row["prev_distance_km"])
        for _, row in input_data.iterrows()
    ]
    input_data["latlon"] = dest_coords
    input_data["prev_latlon"] = prev_dest_coords

    adjusted_coords: list[tuple[float, float] | None] = [None] * len(input_data)
    used_indices: set[int] = set()
    for i, latlon1 in enumerate(input_data["latlon"]):
        if i in used_indices:
            continue
        group = [i]
        for j in range(i + 1, len(input_data)):
            if j in used_indices:
                continue
            if geodesic(latlon1, input_data["latlon"][j]).km < DODGE_THRESHOLD_KM:
                group.append(j)
        segment_idx = get_segment_index(latlon1)
        perp_dx, perp_dy = perp_vectors[segment_idx]
        offsets = np.linspace(-DODGE_OFFSET_KM, DODGE_OFFSET_KM, len(group))
        for idx, offset in zip(group, offsets):
            lat, lon = input_data["latlon"][idx]
            lat_offset = perp_dy * (offset / 111)
            lon_offset = perp_dx * (offset / (111 * np.cos(np.radians(lat))))
            adjusted_coords[idx] = (lat + lat_offset, lon + lon_offset)
        used_indices.update(group)
    input_data["latlon_dodged"] = adjusted_coords

    all_coords = [START_COORDS] + dest_coords
    min_lat = min(lat for lat, lon in all_coords)
    max_lat = max(lat for lat, lon in all_coords)
    min_lon = min(lon for lat, lon in all_coords)
    max_lon = max(lon for lat, lon in all_coords)
    center_lat = (min_lat + max_lat) / 2
    center_lon = (min_lon + max_lon) / 2

    map_obj = folium.Map(location=[center_lat, center_lon], zoom_start=5)
    folium.Marker(
        location=START_COORDS,
        popup="Edinburgh (Start)",
        icon=folium.Icon(color="green"),
    ).add_to(map_obj)

    for _, row in input_data.iterrows():
        folium.PolyLine(
            locations=[row["prev_latlon"], row["latlon_dodged"]],
            color="blue",
            weight=2,
            opacity=0.6,
            tooltip=f"{row['person']} walked {row['distance_km'] - row['prev_distance_km']:.1f} km since last update",
        ).add_to(map_obj)
        popup_text = f"<b>{row['person']}</b><br>{int(row['no_steps']):,} steps<br>{row['distance_km']:.1f} km"
        if USE_PIC:
            uri = encode_image_as_base64_uri(f"img/{row['path_to_png']}")
            if uri:
                icon = folium.CustomIcon(
                    icon_image=uri, icon_size=(30, 40), icon_anchor=(15, 20)
                )
                folium.Marker(
                    location=row["latlon_dodged"],
                    popup=folium.Popup(popup_text, max_width=300),
                    icon=icon,
                ).add_to(map_obj)
            else:
                folium.Marker(
                    location=row["latlon_dodged"],
                    popup=folium.Popup(popup_text, max_width=300),
                ).add_to(map_obj)
        else:
            folium.Marker(
                location=row["latlon_dodged"],
                popup=folium.Popup(popup_text, max_width=300),
            ).add_to(map_obj)

    total_steps = input_data["no_steps"].sum()
    total_distance_km = input_data["distance_km"].sum()
    if SHOW_COMPANY_ICON:
        team_dest = get_straightline_land_path_destination(total_distance_km)
        uri = encode_image_as_base64_uri(company_icon_path)
        if uri:
            icon = folium.CustomIcon(
                icon_image=uri, icon_size=(60, 45), icon_anchor=(30, 22)
            )
            popup_text = f"<b>Team total</b><br>{int(total_steps):,} steps -- {total_distance_km:.1f} km"
            folium.Marker(
                location=team_dest,
                popup=folium.Popup(popup_text, max_width=250),
                icon=icon,
            ).add_to(map_obj)

    map_obj.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]])
    output_path = output_dir / output_html_name
    map_obj.save(output_path)
    return output_path
