"""
django_redis 类型存根文件

此文件为 django_redis 库提供类型注解，因为该库本身不包含完整的类型信息。
当 django_redis 库更新时，可能需要更新此存根文件。

参考: https://github.com/jazzband/django-redis
"""

from redis.client import Redis

# get_redis_connection 函数返回一个 Redis 客户端实例
# alias 参数用于指定 Redis 连接的别名，默认为 "default"
def get_redis_connection(alias: str = "default") -> Redis: ...
