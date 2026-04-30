# Count.It daily Steptacular export

This project pulls selected Count.It people/teams, creates one daily `export.csv` and `steptacular.html` for every day with data, and uploads those files to dated folders in GitHub.

## View maps on web

To view the html files, go to the following URL:

https://jake126.github.io/steptacular_maps/YYYY/YYYY-MM-DD/steptacular.html

For example:

https://jake126.github.io/steptacular_maps/2025/2025-05-31/steptacular.html

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Edit `config/config.json`:

```json
{
  "authorization": "Bearer <your token>",
  "challenge_id": "680a51b4db908edfc4fc31a4",
  "output_dir": "2025",
  "git": {
    "enabled": true,
    "repo_url": "https://github.com/jake126/steptacular_maps.git",
    "branch": "main"
  }
}
```

## Discover IDs

```bash
python -m src.countit_client.discovery
```

Use `<output dir>/available_people.csv` and `<output dir>/available_teams.csv` to fill `selection.csv`.

## Run the full pipeline

```bash
python -m src.countit_client.cli
```

By default this uses May 2025 data columns.

## What is generated locally

Standard summary files are written to `output/`:

- `selected_entities.csv`
- `teams.csv`
- `people.csv`
- `step_counts.csv`
- `metrics.csv`
- `export.csv`

Daily files are written to dated folders:

```text
output/daily/2025-05-16/export.csv
output/daily/2025-05-16/steptacular.html
output/daily/2025-05-19/export.csv
output/daily/2025-05-19/steptacular.html
```

Each daily `export.csv` includes columns from the first day of the month through that date only, so the map's latest date is the specific folder date.

## What is uploaded to GitHub

The pipeline clones/pulls `main`, copies daily files into the configured base folder, commits only if there are changes, and pushes:

```text
steptacular_maps/
└── 2026/
    ├── 2025-05-16/
    │   ├── export.csv
    │   └── steptacular.html
    ├── 2025-05-19/
    │   ├── export.csv
    │   └── steptacular.html
```

## Skip Git upload

```bash
python -m src.countit_client.cli \
  --selection-csv src/selection.csv \
  --skip-git-upload
```

## GitHub authentication

The script uses your local `git` command. Set up SSH or HTTPS token authentication before running.
