"""Download the real API responses used as offline test fixtures.

Run from the repository root (needs network, takes about a minute):

    python tests/fixtures/fetch_fixtures.py

Files are written exactly as the HTTP cache stores them, so tests read them
through the same client with networking disabled. Laps and stints are trimmed
to a few drivers to keep the files small; all other payloads are complete.
"""

import json
import shutil
from pathlib import Path

from f1lab.config import JOLPICA_CACHE_DIR_NAME, OPENF1_CACHE_DIR_NAME
from f1lab.ingest.http import JsonObject, cache_file_name
from f1lab.ingest.jolpica import create_jolpica_client
from f1lab.ingest.openf1 import create_openf1_client

FIXTURES_DIR = Path(__file__).resolve().parent
SEASON = 2024
RACES = {
    1: 9472,  # Bahrain: dry, no Safety Car
    21: 9636,  # São Paulo: wet, red flag, Safety Car, DNS and DSQ in the results
}
EXTRA_PIT_STOPS = (12,)  # British GP: a pit stop recorded without a duration
BASE_DRIVERS = (1, 27)  # Verstappen (winner of both) and Hülkenberg (lap-1 stop in Bahrain)
MAX_EXTRA_DRIVERS = 2


def _extra_drivers(stints: list[JsonObject], laps: list[JsonObject]) -> list[int]:
    """Pick drivers whose rows have missing fields, to cover the nullable paths."""
    with_gaps = [s["driver_number"] for s in stints if s["lap_start"] is None]
    with_gaps += [lap["driver_number"] for lap in laps if lap["lap_duration"] is None]
    unique = [n for n in dict.fromkeys(with_gaps) if n not in BASE_DRIVERS]
    return unique[:MAX_EXTRA_DRIVERS]


def _trim(file: Path, keep: set[int]) -> None:
    """Keep only rows of the given driver numbers in a cached OpenF1 response."""
    rows = json.loads(file.read_text(encoding="utf-8"))
    kept = [row for row in rows if row["driver_number"] in keep]
    file.write_text(json.dumps(kept, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    """Refetch all fixtures from scratch."""
    for name in (JOLPICA_CACHE_DIR_NAME, OPENF1_CACHE_DIR_NAME):
        shutil.rmtree(FIXTURES_DIR / name, ignore_errors=True)
    jolpica = create_jolpica_client(FIXTURES_DIR)
    openf1 = create_openf1_client(FIXTURES_DIR)

    jolpica.schedule(SEASON)
    openf1.race_sessions(SEASON)
    for round_number in EXTRA_PIT_STOPS:
        jolpica.pit_stops(SEASON, round_number)
    for round_number, session_key in RACES.items():
        jolpica.results(SEASON, round_number)
        jolpica.pit_stops(SEASON, round_number)
        openf1.weather(session_key)
        openf1.race_control(session_key)
        stints = openf1.stints(session_key)
        laps = openf1.laps(session_key)

        keep = {*BASE_DRIVERS, *_extra_drivers(stints, laps)}
        for path in ("laps", "stints"):
            _trim(
                FIXTURES_DIR
                / OPENF1_CACHE_DIR_NAME
                / cache_file_name(path, {"session_key": session_key}),
                keep,
            )
        print(f"{SEASON} R{round_number} (session {session_key}): drivers {sorted(keep)}")


if __name__ == "__main__":
    main()
