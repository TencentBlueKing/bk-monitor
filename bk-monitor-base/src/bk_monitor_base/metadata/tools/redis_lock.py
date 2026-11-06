import logging

from redis.exceptions import LockError

from bk_monitor_base.metadata.config import settings

logger = logging.getLogger("metadata")


class DistributedLock:
    """
    Redis 分布式锁
    """

    def __init__(self, redis_client, lock_name, timeout=settings.metadata.bkbase_redis_watch_lock_expire_seconds):
        """
        初始化分布式锁实例。

        :param redis_client: Redis 客户端实例，用于与 Redis 进行交互
        :param lock_name: 锁的名称，用于标识该锁
        :param timeout: 锁的过期时间（秒），防止死锁
        """
        self.redis = redis_client
        self.lock_name = lock_name
        self.timeout = timeout  # 锁的过期时间（秒）
        self.lock = None

    def acquire(self):
        """非阻塞获取锁"""
        # 尝试获取锁，并设置过期时间
        self.lock = self.redis.lock(self.lock_name, timeout=self.timeout)
        acquired = self.lock.acquire(blocking=False)  # 非阻塞获取锁

        if acquired:
            # 锁获取成功，记录日志
            logger.info(f"DistributedLock: Lock {self.lock_name} acquired.")
        else:
            # 锁获取失败，记录日志
            logger.warning(
                f"DistributedLock: Failed to acquire lock {self.lock_name}. Another process may be holding it."
            )

        return acquired

    def release(self):
        """释放锁并清理资源"""
        logger.info(f"Releasing lock {self.lock_name}.")
        try:
            if self.lock and self.lock.locked():  # 检查锁是否仍然被持有
                self.lock.release()  # 释放锁
                logger.info(f"DistributedLock: Lock {self.lock_name} released successfully.")
            else:
                logger.warning(f"DistributedLock: Lock {self.lock_name} was not acquired or has already been released.")
        except LockError as e:
            # 锁释放失败时记录错误日志
            logger.error(f"DistributedLock: Failed to release lock {self.lock_name}: {e}")

    def renew(self):
        """手动续约锁"""
        try:
            # 通过 Redis 重新设置锁的过期时间
            self.redis.set(self.lock_name, "locked", px=self.timeout * 1000)  # 设置过期时间（毫秒）
            logger.info(f"DistributedLock: Lock {self.lock_name} renewed successfully.")
        except Exception as e:  # pylint: disable=broad-except
            # 如果续约失败，记录错误日志
            logger.error(f"DistributedLock: Failed to renew lock {self.lock_name}: {e}")
