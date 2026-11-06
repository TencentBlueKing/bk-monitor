import logging
import traceback
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@contextmanager
def ignored(*exceptions, **kwargs):
    """
    忽略指定异常的上下文管理器
    """
    try:
        yield
    except exceptions:
        if kwargs.get("log_exception", True):
            logger.warning(traceback.format_exc())
