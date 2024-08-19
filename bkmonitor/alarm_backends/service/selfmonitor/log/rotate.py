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

import logging
import os
import re
import time

from six.moves import range

logger = logging.getLogger("self_monitor")


class TimeAndSizeRotateFile(object):
    """
    Handler for rotate file, rotating the log file at midnight
    or reached a certain size.
    """

    DATE_FORMAT = "%Y-%m-%d"
    ONE_DAY_INTERVAL = 24 * 60 * 60  # one day

    def __init__(self, filename, max_bytes, backup_count, gzip=True):
        """
        :param filename:  log filename
        :param max_bytes:
        :param backup_count:
        """
        self.base_filename = os.path.abspath(filename)
        self.max_bytes = max_bytes
        self.backup_count = backup_count

        if os.path.exists(filename):
            t = os.path.getmtime(filename)
        else:
            t = int(time.time())
        self.rollover_next_time = self.compute_next_day(t)

        self.suffix = ""
        self.ext_reg = r"^(\d{4}-\d{2}-\d{2}).(\d+)$"
        self.gzip = gzip
        if self.gzip:
            self.suffix = ".gz"
            self.ext_reg = r"^(\d{4}-\d{2}-\d{2}).(\d+)\.gz$"
        self.ext_reg = re.compile(self.ext_reg)

    def compute_next_day(self, cur_time):
        t = time.localtime(cur_time)
        h, m, s = t[3], t[4], t[5]
        r = self.ONE_DAY_INTERVAL - ((h * 60 + m) * 60 + s)
        return cur_time + r

    def _reach_next_day(self):
        """
        comparing times,
        """
        now = int(time.time())
        return now >= self.rollover_next_time

    def _reach_max_size(self):
        """
        If max_bytes <= zero, rollover never occurs.
        """
        if self.max_bytes <= 0:
            return False

        return os.path.getsize(self.base_filename) > self.max_bytes

    def should_rollover(self):
        """
        Determine if rollover should occur.
        """
        return self._reach_next_day() or self._reach_max_size()

    def do_rollover(self):
        """
        Do a rollover; in this case, a date or number is appended to the filename
        when the rollover happens.

        For example
        app.log -> app.log.Y-m-d.1 -> app.log.Y-m-d.2 -> ...
        """
        if self.backup_count <= 0:
            return

        t = time.localtime(self.rollover_next_time - self.ONE_DAY_INTERVAL)
        date_str = time.strftime(self.DATE_FORMAT, t)
        for i in range(self.backup_count - 1, 0, -1):
            src_file = "%s.%s.%d%s" % (self.base_filename, date_str, i, self.suffix)
            dst_file = "%s.%s.%d%s" % (self.base_filename, date_str, i + 1, self.suffix)
            if os.path.exists(src_file):
                if os.path.exists(dst_file):
                    os.remove(dst_file)
                os.rename(src_file, dst_file)

        dst_file = "%s.%s.%d" % (self.base_filename, date_str, 1)
        if os.path.exists(dst_file):
            os.remove(dst_file)
        os.rename(self.base_filename, dst_file)

        if self.gzip:
            import gzip

            with gzip.open(dst_file + ".gz", "wb") as gfp:
                with open(dst_file, "rb") as fp:
                    gfp.writelines(fp)
            os.remove(dst_file)

        self.rollover_next_time = self.compute_next_day(int(time.time()))

    def get_files_to_delete(self):
        """
        Determine the files to delete when rolling over.
        """
        dir_name, basename = os.path.split(self.base_filename)
        file_names = os.listdir(dir_name)

        def sort_key(file):
            match = self.ext_reg.match(file)
            if match:
                return match.group(1), -int(match.group(2))
            else:
                return "9999-99-99", 0

        suffix_list = []
        suffix_file_map = {}
        prefix = basename + "."
        plen = len(prefix)
        for file_name in file_names:
            if file_name[:plen] == prefix:
                suffix = file_name[plen:]
                if self.ext_reg.match(suffix):
                    suffix_list.append(suffix)
                    suffix_file_map[suffix] = os.path.join(dir_name, file_name)

        suffix_list.sort(key=sort_key)
        file_path_list = [suffix_file_map[suffix] for suffix in suffix_list]
        if len(file_path_list) < self.backup_count:
            result = []
        else:
            result = file_path_list[: len(file_path_list) - self.backup_count]
        return result

    def handle(self):
        try:
            if self.should_rollover():
                self.do_rollover()

            if self.backup_count > 0:
                for f in self.get_files_to_delete():
                    os.remove(f)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:  # noqa
            pass
