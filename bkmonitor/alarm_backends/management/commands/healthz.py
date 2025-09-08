# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import datetime
import logging
import re
import signal
import sys
import time
from io import StringIO

from django.conf import settings
from django.core.management.base import BaseCommand

from alarm_backends.management.commands.hash_ring import HashRing
from alarm_backends.management.story import sc
from core.drf_resource import api

logger = logging.getLogger("self_monitor")


class Command(BaseCommand):
    help = "运维小帮手"

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument(
            "-t",
            action="store_true",
            help="Try to resolve automatically",
        )
        parser.add_argument(
            "-d",
            action="store_true",
            help="Run with daemon, force take -t argument",
        )
        parser.add_argument(
            "-i", metavar="SECONDS", dest="interval", type=int, default=600, help="Run with the given interval"
        )
        parser.add_argument(
            "-es",
            action="store_true",
            help="Run elastic check",
        )
        parser.add_argument(
            "-transfer",
            action="store_true",
            help="Run transfer check, NOTE: this step will wait 1 min or more",
        )
        parser.add_argument(
            "-ts_backup",
            action="store_true",
            help="Run influxdb-proxy backup data check, NOTE: this step will wait 3 min",
        )
        parser.add_argument(
            "-wild",
            action="store_true",
            help="Run nodeman wild subscription check",
        )

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

    def handle(self, *args, **options):
        self.pre_handle()
        if options.get("d"):
            self.run_daemon(interval=options["interval"])
        else:
            self.run_once(options.get("t"))

        sys.exit(len(sc.problems))

    def pre_handle(self):
        pass

    def run_once(self, t=False):
        sc.run()
        if t:
            sc.resolve()

    def run_daemon(self, interval):
        loop = HealthzLoop(interval, self)
        loop.run()


class IntervalLoop(object):
    def __init__(self, interval):
        self.shutdown = False
        self.last_at = None
        self.interval = interval
        self.output = StringIO()

    def run(self):
        signal.signal(signal.SIGTERM, self._onsignal)
        signal.signal(signal.SIGINT, self._onsignal)

        self.on_create()
        while self.can_continue():
            try:
                if HashRing.is_leader():
                    start = time.time()
                    self.on_start()
                    self.on_stop()
                    logger.info("check done in {}, found {}problems".format(time.time() - start, len(sc.problems)))
                    sys.stdout.truncate(0)
                else:
                    logger.info("I'm not leader, do nothing.")
            except Exception as e:
                logger.exception("self monitor error: %s" % e)
                # 自监控未捕获异常，自动退出。由托管进程重新拉起
                break

        self.on_destroy()

    def on_create(self):
        sys.stdout = self.output

    def on_start(self):
        raise NotImplementedError

    def on_stop(self):
        raise NotImplementedError

    def _onsignal(self, signum, frame):
        self.shutdown = True
        print("receive signal: %s" % signum, file=sys.__stdout__)

    def on_destroy(self):
        print("bye!", file=sys.__stdout__)
        sys.stdout = sys.__stdout__

    def can_continue(self):
        if self.shutdown:
            return False

        if self.last_at:
            waited = time.time() - self.last_at
            if waited < self.interval:
                self.wait_until_break(self.interval - waited)
        self.last_at = time.time()
        return True and not self.shutdown

    def wait_until_break(self, wait_for):
        until = time.time() + wait_for
        while not self.shutdown:
            if time.time() < until:
                time.sleep(min([until - time.time(), 10]))
            else:
                break


class HealthzLoop(IntervalLoop):
    def __init__(self, interval, cmd):
        super().__init__(interval)
        self.cmd = cmd
        self.content = ""
        self.suffix = "({})".format(
            getattr(settings, "WXWORK_BOT_NAME", None) or getattr(settings, "BK_IAM_SYSTEM_NAME", "监控平台")
        )
        # 跑一天
        self.max_cycle = int(60 * 60 * 24 / interval)

    def on_start(self):
        self.cmd.run_once(t=True)

    def on_stop(self):
        print("Report at %s" % datetime.datetime.now())
        self.content = self.output.getvalue()
        print(self.content, file=sys.__stdout__)
        if sc.problems:
            self.send_alarm()

        # 循环次数用尽，自动退出
        self.max_cycle -= 1
        if self.max_cycle <= 0:
            self.shutdown = True

    def send_alarm(self):
        alarm_config = settings.HEALTHZ_ALARM_CONFIG
        if "alarm_type" not in alarm_config:
            logger.error(f"自监控发现 {len(sc.problems)}个问题，但未配置通知!")
            return

        for notice_way in alarm_config["alarm_type"]:
            send = getattr(self, "send_{}".format(notice_way), None)
            if not send:
                continue
            send(alarm_config["alarm_role"])

    def send_sms(self, notice_receivers):
        message = "| ".join(map(str, sc.problems))
        message += self.suffix
        logger.info("send.sms({}): \ncontent: {}".format(",".join(notice_receivers), message))
        try:
            api.cmsi.send_sms(
                receiver__username=",".join(notice_receivers),
                content=message,
                is_content_base64=True,
            )
        except Exception as e:
            logger.error("send.sms failed, {}".format(e))

    def send_wechat(self, notice_receivers):
        title = "{}发现{}个问题".format(self.suffix, len(sc.problems))
        message = "| ".join(map(str, sc.problems))
        logger.info("send.weixin({}): \ntitle: {}\ncontent: {}".format(",".join(notice_receivers), title, message))

        try:
            api.cmsi.send_weixin(
                receiver__username=",".join(notice_receivers),
                heading=title,
                message=title + message,
                is_message_base64=True,
            )
        except Exception as e:
            logger.error("send.weixin failed, {}".format(e))

    def send_mail(self, notice_receivers):
        title = "{}发现{}个问题".format(self.suffix, len(sc.problems))
        content = self.content.replace("\033", "")
        content = re.sub(r"\[\d{1,2}m", "", content)
        params = {
            "receiver__username": ",".join(notice_receivers),
            "title": title,
            "content": "<pre>%s</pre>" % content,
            "is_content_base64": True,
        }
        logger.info("send.mail({}): \ntitle: {}".format(",".join(notice_receivers), title))

        try:
            api.cmsi.send_mail(**params)
        except Exception as e:
            logger.error("send.mail failed, {}".format(e))

    def send_phone(self, notice_receivers):
        message = "自监控发现%s个异常" % len(sc.problems)
        logger.info("send.voice({}): \ncontent: {}".format(",".join(notice_receivers), message))
        try:
            api.cmsi.send_voice(
                receiver__username=",".join(notice_receivers),
                auto_read_message=message,
            )
        except Exception as e:
            logger.error("send.voice failed, {}".format(e))
