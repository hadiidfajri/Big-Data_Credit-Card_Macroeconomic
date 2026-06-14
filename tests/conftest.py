"""Shared pytest fixtures & import setup.

Adds the repo root (and the script folders ``docs/``, ``report/``, ``dashboard/``)
to ``sys.path`` so their modules import by name, and provides a lightweight,
**Hive-free** local SparkSession for the PySpark transform tests.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for p in (REPO_ROOT, REPO_ROOT / "docs", REPO_ROOT / "report", REPO_ROOT / "dashboard"):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

# --- Spark launch fix (Windows) --------------------------------------------- #
# A stale external SPARK_HOME (e.g. C:\Spark) makes pyspark look for a launcher
# that may not exist -> CreateProcess WinError 2. Force SPARK_HOME to pyspark's
# own bundled distribution, and pin the worker Python to this interpreter.
import pyspark  # noqa: E402

os.environ["SPARK_HOME"] = str(Path(pyspark.__file__).resolve().parent)
os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)


@pytest.fixture(scope="session")
def spark():
    """A minimal local SparkSession — NOT the project's Hive-wired get_spark().

    Plain `local[1]`, no Hive metastore, UI off, warehouse dir in a temp folder so
    nothing is written into the repo. In-memory ops only (no Parquet writes) so it
    runs on Windows without Hadoop native libs (winutils).
    """
    from pyspark.sql import SparkSession

    warehouse = tempfile.mkdtemp(prefix="spark-test-wh-")
    spark = (
        SparkSession.builder
        .master("local[1]")
        .appName("bigdata-tubes-tests")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .config("spark.sql.warehouse.dir", warehouse)
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    yield spark
    spark.stop()


@pytest.fixture(scope="session")
def _spark_worker_ok(spark):
    """True only if Spark can actually execute a Python-worker job here.

    PySpark local mode on Windows frequently crashes the Python worker
    (WinError 10038 socket bug) — JVM metadata ops work, but jobs (count/collect/
    agg) fail. This probes once so job-dependent tests can skip cleanly on such
    hosts while still running green on Linux / the Docker spark image.
    """
    try:
        spark.createDataFrame([(1,)], ["a"]).count()
        return True
    except Exception:  # noqa: BLE001
        return False


@pytest.fixture(autouse=True)
def _skip_when_no_spark_worker(request):
    """Skip `spark`-marked tests when the local Spark worker can't run jobs."""
    if request.node.get_closest_marker("spark"):
        if not request.getfixturevalue("_spark_worker_ok"):
            pytest.skip("Spark Python worker cannot execute jobs on this host "
                        "(PySpark 3.5 local mode on Windows, WinError 10038). "
                        "Run these in the Docker spark image / Linux for full green.")
