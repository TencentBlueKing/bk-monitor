import logging
import os

from django.db import migrations

from bk_monitor_base.metadata.migration_util import models

logger = logging.getLogger("metadata")


def get_environ(name, is_list=False):
    """
    获取环境变量的值，可能返回一个单独的值或一个数组（多个值）
    :param name: 变量名
    :param is_list: 是否遍历多个值返回数组
    :return: string | list
    """
    # 如果是需要单个值，直接返回
    if not is_list:
        return os.environ.get(name)
    # 如果需要多个值，则从0开始进行遍历
    index = 0
    result = []
    while True:
        current_name = f"{name}{index}"
        current_value = os.environ.get(current_name)
        # 如果当前的这个遍历已经获取不到值了，则直接退出
        if current_value is None:
            break
        result.append(current_value)
        index += 1
    return result


def init_influxdb_backend_info():
    """追加influxdb backend的初始化数据"""
    # 获取用户名和密码
    username = get_environ("BK_MONITOR_INFLUXDB_USER")
    password = get_environ("BK_MONITOR_INFLUXDB_PASS")
    # 获取所有主机的信息
    port = get_environ("BK_MONITOR_INFLUXDB_PORT")
    host_list = get_environ("BK_MONITOR_INFLUXDB_IP", is_list=True)

    for index, ip in enumerate(host_list):
        host_name = f"INFLUXDB_HOST{index}"

        # 创建集群信息
        models["InfluxDBClusterInfo"].objects.create(host_name=host_name, cluster_name="default")
        # 创建具体的机器信息
        models["InfluxDBHostInfo"].objects.create(
            host_name=host_name,
            domain_name=ip,
            port=port,
            username=username if username is not None else "",
            password=password if password is not None else "",
            description="influxdb host for default cluster.",
        )
        cluster = models["ClusterInfo"].objects.get(cluster_type="influxdb", is_default_cluster=True)
        cluster.domain_name = os.environ.get("BK_INFLUXDB_PROXY_HOST", "")
        cluster.port = int(os.environ.get("BK_INFLUXDB_PROXY_PORT", 0))
        cluster.save()



def init_es_storage_backend_info():
    """增加ES存储集群的初始化数据"""
    es_host = os.environ.get("BK_MONITOR_ES7_HOST", "")
    es_port = int(os.environ.get("BK_MONITOR_ES7_REST_PORT", 0))
    es_username = os.environ.get("BK_MONITOR_ES7_USER", "")
    es_password = os.environ.get("BK_MONITOR_ES7_PASSWORD", "")

    # 创建集群信息
    models["ClusterInfo"].objects.update_or_create(
        cluster_name="es_cluster1",
        cluster_type="elasticsearch",
        is_default_cluster=True,
        defaults={
            "domain_name": es_host,
            "port": es_port,
            "description": "init es cluster",
            "username": es_username,
            "password": es_password,
            "version": "7.2",
        },
    )


def init_backend_info(apps, *args, **kwargs):
    """初始化存储后端信息"""
    # 获取APP models
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("old_metadata", model_name)
    init_influxdb_backend_info()
    init_es_storage_backend_info()


class Migration(migrations.Migration):
    dependencies = [
        ("old_metadata", "0002_initial_data"),
    ]

    operations = [migrations.RunPython(init_backend_info)]
