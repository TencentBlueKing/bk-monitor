#!/usr/bin/env python3

import sys
from pathlib import Path


PACKAGES_DIR = Path(__file__).resolve().parents[1] / "bkmonitor" / "packages"
sys.path.insert(0, str(PACKAGES_DIR))

from common import log  # noqa: E402


class LogCapture:
    def __init__(self):
        self.messages = {"info": [], "warning": [], "exception": []}

    def info(self, message):
        self.messages["info"].append(message)

    def warning(self, message):
        self.messages["warning"].append(message)

    def exception(self, message):
        self.messages["exception"].append(message)


def main():
    capture = LogCapture()
    original_logger_detail = log.logger_detail
    log.logger_detail = capture

    try:
        log.logger.info("a=%s", 1)
        log.logger.warning("%s %s %s", 1, 2, 3)
        log.logger.info("单参数")
        log.logger.info("格式不匹配: %s %s", 1)

        try:
            raise RuntimeError("original error")
        except RuntimeError as error:
            exception_before_logging = sys.exc_info()
            log.logger.exception("x=%s", 1)
            exception_after_logging = sys.exc_info()

            assert exception_after_logging[0] is RuntimeError
            assert exception_after_logging[1] is error
            assert exception_after_logging[1] is exception_before_logging[1]
            assert exception_after_logging[2] is exception_before_logging[2]

        assert capture.messages == {
            "info": ["a=1", "单参数", "格式不匹配: %s %s (1,)"],
            "warning": ["1 2 3"],
            "exception": ["x=1"],
        }
    finally:
        log.logger_detail = original_logger_detail

    print("common logger format args self-check passed")


if __name__ == "__main__":
    main()
