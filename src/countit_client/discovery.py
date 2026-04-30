from __future__ import annotations

import argparse
from pathlib import Path

from .client import CountItClient
from .config import load_config
from .transforms import build_people_and_teams


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export available Count.It teams and people so you can build a selection CSV."
    )
    parser.add_argument(
        "--output-dir",
        default="discovery_output",
        help="Directory to write catalog CSV files into.",
    )
    parser.add_argument(
        "--config-path",
        default="config/config.json",
        help="Path to the JSON config file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    client = CountItClient(api_url=config.api_url, headers=config.headers)
    leaderboards = client.fetch_leaderboards(config.challenge_id)
    teams_df, people_df = build_people_and_teams(leaderboards)
    teams_df.to_csv(output_dir / "available_teams.csv", index=False)
    people_df.to_csv(output_dir / "available_people.csv", index=False)
    print(f"Wrote {output_dir / 'available_teams.csv'}")
    print(f"Wrote {output_dir / 'available_people.csv'}")


if __name__ == "__main__":
    main()
