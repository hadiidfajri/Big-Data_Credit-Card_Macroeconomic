"""Prompt 3 — Kafka producer: stream the raw sources onto Kafka topics.

Reads the raw landing produced by :mod:`etl_pipeline.extract` (UCI credit rows +
FRED observations) and publishes them as JSON messages to two topics:

* ``credit-card-raw`` — one message per credit client row.
* ``fred-macro-raw``  — one message per FRED observation (tagged with series_id).

The matching :mod:`etl_pipeline.kafka_consumer` persists what it receives to
``raw/`` (ETL path) and ``datalake/`` (ELT path), realising the §5 data flow.

Run (broker comes from .env KAFKA_BOOTSTRAP_SERVERS; host=localhost:9092,
in-container=kafka:19092)::

    python etl_pipeline/kafka_producer.py --limit 50   # small end-to-end test first
    python etl_pipeline/kafka_producer.py              # full stream
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import zipfile
from pathlib import Path

# --- make the repo root importable when run as a script ---
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import requests  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from common.logging_utils import get_logger  # noqa: E402
from common.paths import ETL_LOGS, RAW_DIR  # noqa: E402
from etl_pipeline.extract import (  # noqa: E402
    FRED_SERIES,
    UCI_ZIP_URL,
    HTTP_TIMEOUT,
)

TOPIC_CREDIT = "credit-card-raw"
TOPIC_FRED = "fred-macro-raw"

logger = get_logger("etl.kafka.producer", ETL_LOGS / "kafka.log")


# --------------------------------------------------------------------------- #
# Source loading (prefer the already-extracted raw files; else fetch in-memory)
# --------------------------------------------------------------------------- #
def load_credit_records(limit: int | None) -> list[dict]:
    """Load credit rows from raw/ (xls/csv) or download the UCI zip in memory."""
    xls = RAW_DIR / "uci_credit_card.xls"
    csv = RAW_DIR / "uci_credit_card.csv"
    if xls.exists():
        df = pd.read_excel(xls, header=1)
    elif csv.exists():
        df = pd.read_csv(csv)
    else:
        logger.info("No raw credit file found — downloading UCI source in memory.")
        resp = requests.get(UCI_ZIP_URL, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            name = next(n for n in zf.namelist() if n.lower().endswith((".xls", ".xlsx")))
            df = pd.read_excel(io.BytesIO(zf.read(name)), header=1)
    if limit:
        df = df.head(limit)
    return df.to_dict(orient="records")


def load_fred_records() -> list[dict]:
    """Load FRED observations from the raw/ JSON files (one record per obs)."""
    records: list[dict] = []
    for series_id in FRED_SERIES:
        path = RAW_DIR / f"fred_{series_id}_2005.json"
        if not path.exists():
            logger.warning("Missing %s — run extract first (or it will be skipped).", path.name)
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for obs in payload.get("observations", []):
            records.append({"series_id": series_id, **obs})
    return records


# --------------------------------------------------------------------------- #
# Publishing
# --------------------------------------------------------------------------- #
def build_producer(bootstrap: str):
    from kafka import KafkaProducer

    return KafkaProducer(
        bootstrap_servers=bootstrap,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: str(k).encode("utf-8") if k is not None else None,
        acks="all",
        retries=3,
        linger_ms=20,
    )


def publish(producer, topic: str, records: list[dict], key_field: str | None) -> int:
    for rec in records:
        key = rec.get(key_field) if key_field else None
        producer.send(topic, key=key, value=rec)
    producer.flush()
    logger.info("Published %d messages to topic '%s'.", len(records), topic)
    return len(records)


def main() -> int:
    parser = argparse.ArgumentParser(description="Stream raw sources to Kafka.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max credit rows to publish (use a small N for a smoke test).")
    parser.add_argument("--bootstrap", default=None,
                        help="Override KAFKA_BOOTSTRAP_SERVERS.")
    args = parser.parse_args()

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    bootstrap = args.bootstrap or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    logger.info("=== Kafka producer -> %s (limit=%s) ===", bootstrap, args.limit)

    producer = build_producer(bootstrap)
    total = 0
    total += publish(producer, TOPIC_CREDIT, load_credit_records(args.limit), key_field="ID")
    total += publish(producer, TOPIC_FRED, load_fred_records(), key_field="series_id")
    producer.close()

    logger.info("=== Producer done: %d total messages ===", total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
