# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import asyncio
import os

from pyppeteer import launch


async def main():
    chrome_path = os.popen("command -v google-chrome").readlines()
    if len(chrome_path) > 0:
        chrome_path = chrome_path[0].strip()
    else:
        raise Exception("Without Chrome, Could not start mail report.")
    browser = await launch(
        handleSIGINT=False,
        handleSIGTERM=False,
        handleSIGHUP=False,
        verify=False,
        headless=True,
        executablePath=chrome_path,
        options={
            "args": [
                "--disable-dev-shm-usage",
                "start-maximized",
                "disable-infobars",
                "--disable-extensions",
                "--disable-gpu",
                "BK-APP-CODE='bk_monitor'",
                "BK-USERNAME='admin'",
            ]
        },
    )
    # 打开一个新页面
    page = await browser.newPage()
    # 访问百度
    await page.goto("https://www.baidu.com/")
    # 截图并存储
    await page.screenshot({"path": "baidu.png"})
    await browser.close()


asyncio.get_event_loop().run_until_complete(main())
