"""Record real API responses for the dashboard tests.

Usage (needs the full database, see ``python -m f1lab.ingest``)::

    python tests/fixtures/export_web_fixtures.py

The API runs in-process against the real database; responses are written to
``web/src/test/fixtures``. ``tests/test_web_fixtures.py`` validates every file
against the API response models, so the web tests only rely on real fields.
"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from f1lab.api.main import create_app

WEB_FIXTURES_DIR = Path(__file__).resolve().parents[2] / "web" / "src" / "test" / "fixtures"
SHOWCASE = "/api/races/202504"  # Bahrain 2025: dry, out of sample
STRATEGIES = "driver=piastri&strategy=M-25-H&strategy=S3-20-H"

FIXTURES = {
    "races.json": "/api/races",
    "race-202504.json": SHOWCASE,
    "race-202501.json": "/api/races/202501",  # Australia 2025: wet, not simulated
    "simulation-202504.json": f"{SHOWCASE}/simulation",
    "strategies-202504.json": f"{SHOWCASE}/strategies?{STRATEGIES}",
    "sc-sensitivity-202504.json": f"{SHOWCASE}/sc-sensitivity?{STRATEGIES}",
    "report-202504.json": f"{SHOWCASE}/report",
    "report-202501.json": "/api/races/202501/report",
    "circuits.json": "/api/circuits",
    "tyres-bahrain.json": "/api/circuits/bahrain/tyres",
}


def main() -> None:
    """Request every fixture and write it as pretty-printed UTF-8 JSON."""
    WEB_FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    with TestClient(create_app()) as client:
        for name, url in FIXTURES.items():
            response = client.get(url)
            response.raise_for_status()
            text = json.dumps(response.json(), ensure_ascii=False, indent=2) + "\n"
            (WEB_FIXTURES_DIR / name).write_text(text, encoding="utf-8", newline="\n")
            print(f"{name}: {len(text) // 1024} KiB")


if __name__ == "__main__":
    main()
