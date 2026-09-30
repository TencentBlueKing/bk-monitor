from django.core.management.base import BaseCommand

from bk_monitor_base.metadata.models.space.constants import SPACE_REDIS_KEY, SpaceTypes
from bk_monitor_base.metadata.task.sync_space import push_and_publish_space_router
from bk_monitor_base.metadata.utils.redis_tools import RedisTools


class Command(BaseCommand):
    help = "init space data to redis"
    space_redis_key = SPACE_REDIS_KEY
    bkcc_type_id = SpaceTypes.BKCC.value
    bcs_type_id = SpaceTypes.BCS.value

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", default=False, help="force push redis data")

    def handle(self, *args, **options):
        """
        NOTE: 因为后续 redis 的 hmset 会被废弃，因此，这里直接使用 hset 直接推送数据
        """
        self.stdout.write("start to push space to redis")

        force_push = options.get("force")
        # 判断redis中是否存在数据，如果存在，则直接返回
        if not force_push and RedisTools.is_member_exist(self.space_redis_key):
            print("space data has pushed to redis")
            return

        # 推送数据
        push_and_publish_space_router()

        self.stdout.write("push space to redis successfully")
