from django.db import migrations


def add_cluster_metrics(app, *args, **kwargs):
    """补充集群指标配置"""

    from metadata.models.storage import ClusterMetric

    metrics = [
        ClusterMetric(
            metric_name="influxdb.httpd.client_error",
            tags=["hostname", "bind", "bkm_cluster"],
        ),
        ClusterMetric(
            metric_name="influxdb.httpd.server_error",
            tags=["hostname", "bind", "bkm_cluster"],
        ),
        ClusterMetric(
            metric_name="influxdb.httpd.points_written_dropped",
            tags=["hostname", "bind", "bkm_cluster"],
        ),
        ClusterMetric(
            metric_name="influxdb.httpd.points_written_fail",
            tags=["hostname", "bind", "bkm_cluster"],
        ),
        ClusterMetric(
            metric_name="influxdb.httpd.points_written_ok",
            tags=["hostname", "bind", "bkm_cluster"],
        ),
        ClusterMetric(
            metric_name="influxdb.httpd.req",
            tags=["hostname", "bind", "bkm_cluster"],
        ),
        ClusterMetric(
            metric_name="influxdb.httpd.query_req",
            tags=["hostname", "bind", "bkm_cluster"],
        ),
        ClusterMetric(
            metric_name="influxdb.httpd.write_req",
            tags=["hostname", "bind", "bkm_cluster"],
        ),
        ClusterMetric(
            metric_name="influxdb.runtime.sys",
            tags=["hostname", "bkm_cluster"],
        ),
        ClusterMetric(
            metric_name="influxdb.runtime.alloc",
            tags=["hostname", "bkm_cluster"],
        ),
        ClusterMetric(
            metric_name="influxdb.shard.write_points_ok",
            tags=[
                "bkm_cluster",
                "database",
                "engine",
                "hostname",
                "id",
                "index_type",
                "path",
                "retention_policy",
                "wal_path",
            ],
        ),
        ClusterMetric(
            metric_name="influxdb.shard.write_points_err",
            tags=[
                "bkm_cluster",
                "database",
                "engine",
                "hostname",
                "id",
                "index_type",
                "path",
                "retention_policy",
                "wal_path",
            ],
        ),
        ClusterMetric(
            metric_name="influxdb.shard.disk_bytes",
            tags=[
                "bkm_cluster",
                "database",
                "engine",
                "hostname",
                "id",
                "index_type",
                "path",
                "retention_policy",
                "wal_path",
            ],
        ),
        ClusterMetric(
            metric_name="influxdb.database.num_series",
            tags=["bkm_cluster", "database", "hostname"],
        ),
        ClusterMetric(
            metric_name="influxdb_proxy.influxdb_proxy_backend_alive_status",
            tags=["bkm_cluster", "backend", "type"],
        ),
    ]
    ClusterMetric.objects.bulk_create(metrics)


class Migration(migrations.Migration):
    dependencies = [("metadata", "0176_clustermetric")]

    operations = [migrations.RunPython(add_cluster_metrics)]
