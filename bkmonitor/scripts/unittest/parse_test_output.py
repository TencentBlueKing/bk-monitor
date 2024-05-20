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
import re
import sys
import typing

logger = logging.getLogger(__name__)


def format_test_result(test_result: typing.Dict[str, int]):
    print(f"{test_result.get('passed', 0)}, {test_result.get('failed', 0)}, {test_result.get('errors', 0)}")


def format_coverage_result(coverage_result: typing.Dict[str, typing.Union[str, int]]):
    print(f"{coverage_result['coverage']} ({coverage_result['hit']} / {coverage_result['total']})")


def handle_pytest(output: str) -> typing.Dict[str, int]:
    pattern = re.compile(r"={3,}\s*(?:\d+\s*(?:failed|passed|errors),?\s*)+?in\s*[\d\.s]+\s*\(\d+:\d+:\d+\)\s*={3,}")
    matched_line: str = pattern.findall(output)[-1]

    test_result: typing.Dict[str, int] = {}
    for num_str, category in re.findall(r"(\d+)\s*(failed|passed|errors)", matched_line):
        test_result[category] = int(num_str)
    format_test_result(test_result)
    return test_result


def handle_testcase(output: str) -> typing.Dict[str, int]:
    pattern = re.compile(r"Ran\s(\d+)\stests\sin\s[\d\.s]+\s+(OK|FAILED\s\((?:(?:failures|errors)=\d+,?\s?)+\))")
    total_str, matched_line = pattern.findall(output)[-1]

    category_mapping: typing.Dict[str, str] = {"failures": "failed"}
    test_result: typing.Dict[str, int] = {}
    for category, num_str in re.findall(r"(failures|errors)=(\d+)", matched_line):
        test_result[category_mapping.get(category, category)] = int(num_str)

    test_result["passed"] = int(total_str) - category_mapping.get("failed", 0) - category_mapping.get("errors", 0)

    format_test_result(test_result)
    return test_result


def handle_coverage(output: str) -> typing.Dict[str, typing.Union[str, int]]:
    pattern = re.compile(r"TOTAL\s+(\d+)\s+(\d+)\s+(\d+%)")
    coverage_result_tuple: typing.Tuple[str, str, str] = pattern.findall(output)[0]
    coverage_result: typing.Dict[str, typing.Union[str, int]] = {
        "total": int(coverage_result_tuple[0]),
        "hit": int(coverage_result_tuple[1]),
        "coverage": coverage_result_tuple[2],
    }
    format_coverage_result(coverage_result)
    return coverage_result


def parse_test_output(file_name):
    try:
        with open(file_name, "r") as file:
            content = file.read()
    except Exception as e:  # pylint: disable=broad-except
        logger.exception(f"Error reading file {file_name}: {e}")
        return

    try:
        if "pytest" in file_name:
            handle_pytest(content)
        elif "testcase" in file_name:
            handle_testcase(content)
        elif "coverage" in file_name:
            handle_coverage(content)
    except Exception as e:  # pylint: disable=broad-except
        logger.exception(f"Error parsing {file_name}: {e}")


if __name__ == "__main__":
    parse_test_output(sys.argv[1])
