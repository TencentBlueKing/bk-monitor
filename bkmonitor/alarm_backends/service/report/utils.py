import asyncio
import logging
import os
from http.client import BadStatusLine

from pyppeteer import launch

from core.errors.common import CustomError

logger = logging.getLogger("alarm_backends")


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


async def get_browser():
    """
    获取浏览器
    """
    try_times = 0
    while try_times <= 3:
        # 获取浏览器路径
        chrome_path = os.popen("command -v chromium").readlines() or os.popen("command -v google-chrome").readlines()
        if len(chrome_path) > 0:
            chrome_path = chrome_path[0].strip()
        else:
            raise CustomError("[mail_report] Without Chrome, Could not start mail report.")

        try:
            # 启动浏览器
            return await launch(
                headless=True,
                executablePath=chrome_path,
                options={
                    "args": [
                        "--disable-dev-shm-usage",
                        "--disable-infobars",
                        "--disable-extensions",
                        "--disable-gpu",
                        "--mute-audio",
                        "--disable-bundled-ppapi-flash",
                        "--hide-scrollbars",
                    ]
                },
            )
        except BadStatusLine as e:
            logger.exception(f"[mail_report] chrome start fail, will try again, Number: {try_times}, error: {e}")
            try_times += 1

    raise CustomError("[mail_report] chrome start fail, try 3 times, still fail.")
