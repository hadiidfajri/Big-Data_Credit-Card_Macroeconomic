"""Hive-enabled :class:`SparkSession` factory shared by the Spark stages.

Connection targets come from the environment so the same code runs locally
(``localhost``) or inside the Spark containers (``hive-metastore`` service name):

* ``HIVE_METASTORE_URI``  (default ``thrift://hive-metastore:9083``)
* ``SPARK_MASTER_URL``    (default ``local[*]``)
"""

from __future__ import annotations

import os

from common.paths import HIVE_WAREHOUSE


def get_spark(app_name: str, with_hive: bool = True):
    """Build (or get) a SparkSession.

    Parameters
    ----------
    app_name:
        Spark application name (shown in the UI / logs).
    with_hive:
        Enable Hive metastore support (needed for Load and the ELT warehouse).
    """
    from pyspark.sql import SparkSession

    metastore_uri = os.getenv("HIVE_METASTORE_URI", "thrift://hive-metastore:9083")
    # local[*] keeps the CLAUDE.md default. Use APP_SPARK_MASTER (not SPARK_MASTER_URL,
    # which bitnami reserves for the worker->master link) to target the cluster
    # (spark://spark-master:7077).
    master = os.getenv("APP_SPARK_MASTER", "local[*]")

    builder = (
        SparkSession.builder.appName(app_name)
        .master(master)
        .config("spark.sql.warehouse.dir", HIVE_WAREHOUSE)
        .config("spark.sql.session.timeZone", "UTC")
        # bitnami uid 1001 has no /etc/passwd entry -> JVM user.home='?' -> ivy
        # 'basedir must be absolute'. Pin ivy to an absolute path (HOME=/tmp also set).
        .config("spark.jars.ivy", "/tmp/.ivy2")
        # Shared warehouse volume is touched by both Hive (uid 1000) and Spark; make
        # Spark-created dirs world-writable so the two uids don't collide on Mkdirs.
        .config("spark.hadoop.fs.permissions.umask-mode", "000")
        # Make CTAS create Spark-native parquet tables (Spark writer, no Hive
        # .hive-staging dir) so writes don't trip on metastore-owned table dirs.
        .config("spark.sql.legacy.createHiveTableByDefault", "false")
        # Spark 3.5 ships the Hive 2.3.9 metastore client; talk to the external
        # Hive 4.0 metastore over thrift (see README caveats).
        .config("spark.sql.hive.metastore.version", "2.3.9")
        .config("spark.sql.hive.metastore.jars", "builtin")
    )

    if with_hive:
        builder = builder.config("hive.metastore.uris", metastore_uri).enableHiveSupport()

    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark
