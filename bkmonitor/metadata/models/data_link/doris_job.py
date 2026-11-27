from django.db import models


class DorisJobConfig(models.Model):
    """由 metadata 管理、在 Doris FE 执行的周期 INSERT。"""

    data_link = models.ForeignKey("metadata.DataLink", on_delete=models.PROTECT, related_name="doris_jobs")
    cluster_id = models.IntegerField()
    database = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    interval_minutes = models.PositiveIntegerField()
    insert_sql = models.TextField()
    template_key = models.CharField(max_length=64, blank=True)
    template_inputs = models.JSONField(default=dict)
    remote_id = models.BigIntegerField(null=True)
    reconcile_status = models.CharField(max_length=16, default="draft", db_index=True)
    pending_action = models.CharField(max_length=16, blank=True)
    status_reason = models.TextField(blank=True)
    create_time = models.DateTimeField(auto_now_add=True)
    last_modify_time = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("cluster_id", "name"),)


class MetricDorisPipeline(models.Model):
    """每个逻辑 RT 的期望输出与尚待执行的步骤。历史输出由 StorageClusterRecord 保存。"""

    result_table = models.OneToOneField("metadata.ResultTable", primary_key=True, on_delete=models.CASCADE)
    data_link = models.OneToOneField("metadata.DataLink", on_delete=models.PROTECT)
    source = models.ForeignKey(
        "metadata.ResultTable", null=True, related_name="metric_aggregates", on_delete=models.PROTECT
    )
    output = models.ForeignKey("metadata.ResultTableConfig", null=True, on_delete=models.PROTECT)
    layout = models.JSONField(default=dict)
    phase = models.CharField(max_length=16, default="apply", db_index=True)
    status_reason = models.TextField(blank=True)


class DorisJobTableRelation(models.Model):
    job = models.ForeignKey(DorisJobConfig, on_delete=models.CASCADE, related_name="table_relations")
    direction = models.CharField(max_length=8, choices=[("source", "source"), ("target", "target")])
    component_kind = models.CharField(max_length=16, blank=True)
    # 保留关系行，使待执行动作能够发现组件已被删除。
    result_table = models.ForeignKey("metadata.ResultTableConfig", null=True, on_delete=models.SET_NULL)
    doris_binding = models.ForeignKey("metadata.DorisStorageBindingConfig", null=True, on_delete=models.SET_NULL)
    database = models.CharField(max_length=255, blank=True)
    table = models.CharField(max_length=255, blank=True)
