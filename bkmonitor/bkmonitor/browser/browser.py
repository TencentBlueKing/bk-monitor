import asyncio
import logging
import os
import time
from functools import lru_cache
from threading import Lock
from typing import Optional

from celery import platforms
from celery.signals import worker_process_init, worker_process_shutdown
from pyppeteer import launch
from pyppeteer.browser import Browser

logger = logging.getLogger("bkmonitor")

_browser: Optional[Browser] = None
_browser_lock = Lock()
_browser_connected = False
_browser_start_time = 0


@lru_cache(maxsize=1)
def get_browser_path():
    """
    获取浏览器路径
    """
    chrome_path = os.popen("command -v chromium").readlines() or os.popen("command -v google-chrome").readlines()
    if len(chrome_path) > 0:
        chrome_path = chrome_path[0].strip()
    else:
        raise RuntimeError("Without Chrome or Chrome not installed.")
    return chrome_path


def _on_browser_disconnected(*args, **kwargs):
    """
    监听浏览器断开事件
    """
    global _browser_connected
    _browser_connected = False


async def get_browser():
    """
    获取浏览器
    """
    global _browser
    global _browser_connected
    global _browser_start_time

    with _browser_lock:
        # 如果浏览器断开，尝试关闭浏览器
        if _browser and not _browser_connected:
            try:
                await _browser.close()
            except Exception as e:
                logger.exception(f"close browser failed, error: {e}")
            _browser = None
            _browser_start_time = 0

        # 如果浏览器启动时间超过30分钟，则重新启动浏览器，避免内存泄漏
        if _browser and _browser_start_time and time.time() - _browser_start_time > 30 * 60:
            try:
                await _browser.close()
            except Exception as e:
                logger.exception(f"close browser failed, error: {e}")

            _browser = None
            _browser_connected = False
            _browser_start_time = 0

        # 如果浏览器已连接，直接返回
        if _browser and _browser_connected:
            return _browser

        # 获取浏览器路径
        chrome_path = get_browser_path()

        # 启动浏览器
        _browser = await launch(
            headless=True,
            executablePath=chrome_path,
            options={
                "args": [
                    "--disable-dev-shm-usage",
                    "--disable-infobars",
                    "--disable-extensions",
                    "--disable-gpu",
                    "--disable-software-rasterizer",
                    "--renderer-process-limit=2",
                    "--mute-audio",
                    "--disable-bundled-ppapi-flash",
                    "--hide-scrollbars",
                ],
                "timeout": 5000,
            },
        )

        # 监听浏览器连接断开事件
        _browser_connected = True
        _browser.on("disconnected", _on_browser_disconnected)
        _browser_start_time = time.time()
        return _browser


def get_or_create_eventloop() -> asyncio.AbstractEventLoop:
    """
    获取或创建事件循环

    Returns:
        asyncio.AbstractEventLoop: 返回可用的事件循环实例

    Raises:
        RuntimeError: 如果无法创建或获取事件循环时抛出
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("Event loop is closed")
        return loop
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


def _cleanup_browser():
    """
    进程退出时清理浏览器资源
    """
    global _browser
    if _browser:
        loop = get_or_create_eventloop()
        try:
            loop.run_until_complete(_browser.close())
        except Exception as e:
            logger.exception(f"close browser failed, error: {e}")
        finally:
            _browser = None


@worker_process_shutdown.connect
def pool_process_shutdown_handler(signal=None, sender=None, **kwargs):
    logger.info("Worker is shutting downing")
    _cleanup_browser()


@worker_process_init.connect
def install_pool_process_sighandlers(signal=None, sender=None, **kwargs):
    logger.info("Worker is starting")
    platforms.signals["TERM"] = _cleanup_browser
    platforms.signals["INT"] = _cleanup_browser
