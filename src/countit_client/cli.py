from __future__ import annotations

import argparse
import logging

from .config import load_config
from .pipeline import run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pull selected Count.It data, generate daily maps, and optionally upload to GitHub."
    )
    parser.add_argument(
        "--selection-csv",
        default="src/selection.csv",
        help="CSV listing which teams and/or people to include.",
    )
    parser.add_argument(
        "--config-path",
        default="src/config/config.json",
        help="Path to the JSON config file.",
    )
    parser.add_argument(
        "--export-year", type=int, default=2025, help="Year for wide CSV date columns."
    )
    parser.add_argument(
        "--export-month", type=int, default=5, help="Month for wide CSV date columns."
    )
    parser.add_argument(
        "--skip-git-upload",
        action="store_true",
        help="Generate files but do not commit or push them to GitHub.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    config = load_config(args.config_path)
    run_pipeline(
        config,
        args.selection_csv,
        args.export_year,
        args.export_month,
        upload_to_git=not args.skip_git_upload,
    )
    print(f"Wrote outputs to {config.output_dir}")


if __name__ == "__main__":
    main()
