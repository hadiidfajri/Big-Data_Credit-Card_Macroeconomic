"""Shared utilities for the Big Data ETL/ELT pipelines.

Modules:
* :mod:`common.paths`          — canonical project directories.
* :mod:`common.logging_utils`  — structured console+file logging.
* :mod:`common.metrics`        — per-stage runtime/resource instrumentation (Prompt 9).
* :mod:`common.spark_session`  — Hive-enabled SparkSession factory.
"""
