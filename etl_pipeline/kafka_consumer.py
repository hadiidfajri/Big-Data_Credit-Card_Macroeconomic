"""Prompt 3 — Kafka consumer: persist streamed messages to raw/ and datalake/.

Subscribes to ``credit-card-raw`` and ``fred-macro-raw``, accumulates the JSON
messages until the stream goes idle, then writes them **untouched** (no cleaning)
to both landing zones, realising the §5 fan-out:

* ``raw/``      — ETL path landing  (credit_card_stream.csv, fred_macro_stream.json)
* ``datalake/`` — ELT path landing  (same two files)

Run it in one terminal, then run the producer in another::

    python etl_pipeline/kafka_consumer.py --idle-ms 8000
    # (other terminal) python etl_pipeline/kafka_producer.py --limit 50
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from common.logging_utils import get_logger  # noqa: E402
from common.paths import DATALAKE_DIR, ETL_LOGS, RAW_DIR, ensure_dirs  # noqa: E402
from etl_pipeline.kafka_producer import TOPIC_CREDIT, TOPIC_FRED  # noqa: E402

logger = get_logger("etl.kafka.consumer", ETL_LOGS / "kafka.log")


def build_consumer(bootstrap: str, idle_ms: int):
    from kafka import KafkaConsumer

    return KafkaConsumer(
        TOPIC_CREDIT,
        TOPIC_FRED,
        bootstrap_servers=bootstrap,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id="bigdata-raw-consumer",
        consumer_timeout_ms=idle_ms,  # stop after this much idle time
    )


def _write_both(filename: str, writer) -> None:
    """Write the same payload to raw/ and datalake/ via ``writer(path)``."""
    ensure_dirs(RAW_DIR, DATALAKE_DIR)
    for base in (RAW_DIR, DATALAKE_DIR):
        writer(base / filename)


def main() -> int:
    parser = argparse.ArgumentParser(description="Persist Kafka messages to raw/ + datalake/.")
    parser.add_argument("--idle-ms", type=int, default=8000,
                        help="Stop after this many ms with no new messages.")
    parser.add_argument("--bootstrap", default=None)
    args = parser.parse_args()

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    bootstrap = args.bootstrap or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    logger.info("=== Kafka consumer <- %s (idle stop=%dms) ===", bootstrap, args.idle_ms)

    consumer = build_consumer(bootstrap, args.idle_ms)
    credit: list[dict] = []
    fred: list[dict] = []

    for msg in consumer:
        if msg.topic == TOPIC_CREDIT:
            credit.append(msg.value)
        elif msg.topic == TOPIC_FRED:
            fred.append(msg.value)
    consumer.close()
    logger.info("Consumed credit=%d, fred=%d messages.", len(credit), len(fred))

    if credit:
        df = pd.DataFrame(credit)
        _write_both("credit_card_stream.csv", lambda p: df.to_csv(p, index=False))
        logger.info("Wrote credit_card_stream.csv (%d rows) to raw/ + datalake/.", len(df))
    if fred:
        _write_both(
            "fred_macro_stream.json",
            lambda p: p.write_text(json.dumps(fred, indent=2), encoding="utf-8"),
        )
        logger.info("Wrote fred_macro_stream.json (%d obs) to raw/ + datalake/.", len(fred))

    logger.info("=== Consumer done ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
