from django.core.management.base import BaseCommand

from metadata.models.space import Space, constants
from metadata.models.space.utils import create_bcs_spaces, get_valid_bcs_projects


class Command(BaseCommand):
    help = "sync bcs project for space"
    type_id = constants.SpaceTypes.BKCI.value

    def add_arguments(self, parser):
        parser.add_argument("--bk_tenant_id", default="system", type=str, help="租户ID")

    def handle(self, *args, **options):
        """同步 bcs 空间

        NOTE: 需要关联资源: 类型=>资源: bkcc=>[bk_biz_id], bcs=>[project_id, cluster_id, namespace]
        0. 拉取项目，过滤到 `k8s` 的项目(此时项目之关联到了业务)
        1. 拉取所有集群(因为有集群，则保证项目为开启容器服务的项目)
        2. 拉取共享集群的命名空间(需要通过接口取拉取共享的集群)
        3. 创建空间
        4. 添加空间和数据源的关系
        5. 关联资源
        """
        print("start sync bcs space")
        bk_tenant_id = options["bk_tenant_id"]

        if Space.objects.filter(bk_tenant_id=bk_tenant_id, space_type_id=self.type_id).exists():
            print("bcs space type already exists")
            return

        # 查询所有集群(集群中含有项目ID)及共享集群
        # 格式: [{"project_id": "test", "name": "test", "project_code": "test", "bk_biz_id": "100148", "bk_tenant_id": "system"}]
        try:
            projects = get_valid_bcs_projects(bk_tenant_id=bk_tenant_id)
        except Exception as e:
            print("get bcs project error, %s", e)
            return

        # 创建空间、关联资源、关联数据源 ID
        create_bcs_spaces(projects)

        print("sync bcs project for space successfully")
