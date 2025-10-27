from django.core.management.base import BaseCommand, CommandError

from core.drf_resource import api
from metadata import models
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis


class Command(BaseCommand):
    help = "创建快捷数据链路，将计算平台的结果表数据快速接入到监控平台"

    def add_arguments(self, parser):
        parser.add_argument("--space-id", type=int, required=True, help="空间ID（BKCC业务ID）")
        parser.add_argument("--bk-tenant-id", type=str, default="system", help="租户ID，默认为system")
        parser.add_argument("--table-ids", type=str, required=True, help="计算平台结果表ID列表，用逗号分隔")

    def handle(self, *args, **options):
        space_id = options["space_id"]
        bk_tenant_id = options["bk_tenant_id"]
        table_ids_str = options["table_ids"]

        # 验证space_id
        if space_id <= 0:
            raise CommandError("space_id必须大于0")

        # 固定参数
        etl_config = "bk_standard_v2_time_series"
        operator = "system"
        source_label = "custom"
        type_label = "time_series"
        space_type = "bkcc"

        # 解析结果表ID列表
        bk_data_result_table_ids = [table_id.strip() for table_id in table_ids_str.split(",") if table_id.strip()]

        if not bk_data_result_table_ids:
            raise CommandError("至少需要提供一个结果表ID")

        self.stdout.write(f"开始处理空间ID: {space_id}")
        self.stdout.write(f"结果表ID列表: {bk_data_result_table_ids}")

        result_table_ids = []

        for bk_data_result_table_id in bk_data_result_table_ids:
            bk_data_result_table_id = bk_data_result_table_id.strip()
            if not bk_data_result_table_id:
                continue

            self.stdout.write(f"正在处理结果表: {bk_data_result_table_id}")

            # 检查业务ID
            if not bk_data_result_table_id.startswith(f"{space_id}_"):
                raise CommandError(f"结果表ID格式错误: {bk_data_result_table_id}，应该以{space_id}_开头")

            try:
                # 获取VMRT信息
                vmrt_info = api.bkdata.get_result_table(
                    bk_tenant_id=bk_tenant_id, result_table_id=bk_data_result_table_id
                )
                vm_cluster_name = vmrt_info["storages"]["vm"]["storage_cluster"]["cluster_name"]

                # 获取VM集群信息
                cluster = models.ClusterInfo.objects.get(
                    cluster_name=vm_cluster_name, cluster_type=models.ClusterInfo.TYPE_VM
                )

                # 生成数据源名称，先去除业务ID，然后再去除bkm_前缀
                data_name = bk_data_result_table_id
                table_id = f"{bk_data_result_table_id}.__default__"

                # 1. 创建数据源（先检查是否存在）
                try:
                    ds = models.DataSource.objects.get(data_name=data_name, bk_tenant_id=bk_tenant_id)
                    self.stdout.write(f"数据源已存在: {data_name}")
                except models.DataSource.DoesNotExist:
                    ds = models.DataSource.create_data_source(
                        bk_tenant_id=bk_tenant_id,
                        data_name=data_name,
                        etl_config=etl_config,
                        operator=operator,
                        source_label=source_label,
                        type_label=type_label,
                        space_type_id=space_type,
                        space_id=space_id,
                    )
                    self.stdout.write(f"创建数据源: {data_name}")

                # 2. 创建RT（虚拟RT，并无实际作用）
                rt, created = models.ResultTable.objects.get_or_create(
                    bk_tenant_id=bk_tenant_id,
                    table_id=table_id,
                    defaults={
                        "table_name_zh": data_name,
                        "is_custom_table": False,
                        "schema_type": "fixed",
                        "default_storage": "victoria_metrics",
                        "creator": "system",
                        "last_modify_user": "system",
                        "bk_biz_id": space_id,
                    },
                )
                if created:
                    self.stdout.write(f"创建结果表: {table_id}")
                else:
                    self.stdout.write(f"结果表已存在: {table_id}")

                # 3. 创建接入VM记录，绑定真实的流转后的VMRT
                vm_record, created = models.AccessVMRecord.objects.get_or_create(
                    bk_tenant_id=bk_tenant_id,
                    result_table_id=table_id,
                    defaults={
                        "vm_cluster_id": cluster.cluster_id,
                        "bk_base_data_id": ds.bk_data_id,
                        "vm_result_table_id": bk_data_result_table_id,
                    },
                )
                if created:
                    self.stdout.write(f"创建VM接入记录: {table_id}")
                else:
                    self.stdout.write(f"VM接入记录已存在: {table_id}")

                # 4. 创建空间-数据源关联关系授权表，这里的data_id取自第一步创建的数据源
                space_ds, created = models.SpaceDataSource.objects.get_or_create(
                    bk_tenant_id=bk_tenant_id, bk_data_id=ds.bk_data_id, space_type_id=space_type, space_id=space_id
                )
                if created:
                    self.stdout.write(f"创建空间数据源关联: {ds.bk_data_id}")
                else:
                    self.stdout.write(f"空间数据源关联已存在: {ds.bk_data_id}")

                # 5. 创建数据源-结果表关联关系
                ds_rt, created = models.DataSourceResultTable.objects.get_or_create(
                    bk_tenant_id=bk_tenant_id, bk_data_id=ds.bk_data_id, table_id=table_id
                )
                if created:
                    self.stdout.write(f"创建数据源结果表关联: {ds.bk_data_id} -> {table_id}")
                else:
                    self.stdout.write(f"数据源结果表关联已存在: {ds.bk_data_id} -> {table_id}")

                # 6. 创建时序分组记录，这里的data_id取自第一步创建的数据源
                ts, created = models.TimeSeriesGroup.objects.get_or_create(
                    bk_tenant_id=bk_tenant_id,
                    bk_data_id=ds.bk_data_id,
                    defaults={
                        "time_series_group_name": data_name,
                        "bk_biz_id": space_id,
                        "table_id": table_id,
                    },
                )
                if created:
                    self.stdout.write(f"创建时序分组: {data_name}")
                else:
                    self.stdout.write(f"时序分组已存在: {data_name}")

                # 7. 指标发现
                metrics_info = ts.get_metrics_from_redis()
                ts.update_metrics(metrics_info)

                # 8. ResultTableOption
                rt_option, created = models.ResultTableOption.objects.get_or_create(
                    table_id=table_id,
                    name="is_split_measurement",
                    defaults={
                        "value": "true",
                        "value_type": "bool",
                        "creator": "system",
                        "bk_tenant_id": bk_tenant_id,
                    },
                )
                if created:
                    self.stdout.write(f"创建结果表选项: {table_id}")
                else:
                    self.stdout.write(f"结果表选项已存在: {table_id}")

                result_table_ids.append(table_id)
                self.stdout.write(self.style.SUCCESS(f"成功创建快捷数据链路: {table_id}"))

            except Exception as e:
                raise CommandError(f"处理结果表 {bk_data_result_table_id} 时出错: {str(e)}")

        # 9. 推送路由
        self.stdout.write("正在推送路由...")
        SpaceTableIDRedis().push_table_id_detail(
            table_id_list=result_table_ids, is_publish=True, bk_tenant_id=bk_tenant_id
        )
        SpaceTableIDRedis().push_space_table_ids(space_type=space_type, space_id=str(space_id), is_publish=True)

        self.stdout.write(self.style.SUCCESS(f"完成！共创建了 {len(result_table_ids)} 个快捷数据链路"))
