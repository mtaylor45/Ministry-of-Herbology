#!/usr/bin/env python3
"""Load the fixture data into the dev database.

Workstream B owns this script; the data it loads is Workstream L's. It is
idempotent: run it as often as you like. It refuses to run against anything
that does not look like a development database, because it truncates.

    python scripts/load_fixtures.py
    python scripts/load_fixtures.py --database-url postgresql://...
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "fixtures"

#: Truncated in this order, so foreign keys never block the reload.
WIPE_ORDER = [
    "task_event",
    "task",
    "frost_alert",
    "care_rule",
    "water_balance",
    "log_entry",
    "photo",
    "field_note",
    "plate",
    "specimen",
    "care_value",
    "species",
    "source",
    "reading",
    "sensor_source",
    "weather_forecast",
    "weather_obs",
    "weather_alert",
    "location",
    "map_layer",
    "site",
    "calendar_feed",
    "member",
]

DEV_MARKERS = ("localhost", "127.0.0.1", "@db:", "herbology-dev")


def load(relative: str):
    with (FIXTURES / relative).open() as fh:
        return json.load(fh)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.environ.get(
            "MOH_DATABASE_URL",
            "postgresql://herbology:herbology@localhost:5432/herbology",
        ),
    )
    parser.add_argument(
        "--force", action="store_true", help="Skip the dev-database check"
    )
    args = parser.parse_args()

    url = args.database_url.replace("postgresql+asyncpg://", "postgresql://")
    if not args.force and not any(marker in url for marker in DEV_MARKERS):
        print(
            f"{url!r} does not look like a development database. Refusing to truncate."
        )
        print("Pass --force if you are certain.")
        return 1

    try:
        import psycopg
    except ImportError:
        print("psycopg is not installed. Run: pip install 'psycopg[binary]'")
        return 1

    site = load("site.json")
    locations = load("locations/locations.json")
    sources = load("species/sources.json")
    species = load("species/species.json")
    specimens = load("specimens/specimens.json")

    with psycopg.connect(url, autocommit=False) as conn, conn.cursor() as cur:
        cur.execute(f"TRUNCATE {', '.join(WIPE_ORDER)} CASCADE")

        cur.execute(
            "INSERT INTO site (id, name, latitude, longitude, elevation_m, timezone, nws_zone)"
            " VALUES (%(id)s, %(name)s, %(latitude)s, %(longitude)s, %(elevation_m)s,"
            " %(timezone)s, %(nws_zone)s)",
            site,
        )

        for row in locations:
            cur.execute(
                "INSERT INTO location (id, site_id, parent_id, name, kind, is_outdoor,"
                " is_covered, sun_exposure) VALUES (%(id)s, %(site_id)s, %(parent_id)s,"
                " %(name)s, %(kind)s, %(is_outdoor)s, %(is_covered)s, %(sun_exposure)s)",
                row,
            )

        for row in sources:
            cur.execute(
                "INSERT INTO source (id, kind, title, url, license, retrieved_at)"
                " VALUES (%(id)s, %(kind)s, %(title)s, %(url)s, %(license)s, %(retrieved_at)s)",
                row,
            )

        columns = [
            "id",
            "accepted_name",
            "family",
            "genus",
            "common_names",
            "native_range",
            "summary",
            "light_label",
            "water_k_c",
            "water_interval_days",
            "soil_ph_min",
            "soil_ph_max",
            "soil_type",
            "fertilizer_note",
            "humidity_min_pct",
            "min_temp_c",
            "max_temp_c",
            "usda_zone_min",
            "usda_zone_max",
            "dormancy_months",
            "toxic_to_pets",
            "toxic_to_children",
            "toxicity_note",
            "enrichment_state",
        ]
        for row in species:
            cur.execute(
                f"INSERT INTO species ({', '.join(columns)}) VALUES"
                f" ({', '.join(f'%({c})s' for c in columns)})",
                {c: row.get(c) for c in columns},
            )
            for index, value in enumerate(row["care_values"]):
                cur.execute(
                    "INSERT INTO care_value (id, species_id, field, value, unit, source_id,"
                    " confidence) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (
                        f"018900ff-0000-7000-8000-{abs(hash((row['id'], index))) % 10**12:012d}",
                        row["id"],
                        value["field"],
                        json.dumps(value["value"]),
                        value.get("unit"),
                        value.get("source_id"),
                        value["confidence"],
                    ),
                )

        specimen_columns = [
            "id",
            "species_id",
            "nickname",
            "cultivar",
            "is_group",
            "count",
            "location_id",
            "is_outdoor",
            "in_container",
            "container_litres",
            "acquired_on",
            "provenance",
            "status",
        ]
        for row in specimens:
            cur.execute(
                f"INSERT INTO specimen ({', '.join(specimen_columns)}) VALUES"
                f" ({', '.join(f'%({c})s' for c in specimen_columns)})",
                {c: row.get(c) for c in specimen_columns},
            )

        conn.commit()

    print(
        f"Loaded 1 site, {len(locations)} locations, {len(sources)} sources, "
        f"{len(species)} species and {len(specimens)} specimens."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
