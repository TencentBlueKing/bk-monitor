"""文件解析失败按路径返回错误，所有 AsCode 配置类型使用相同协议。"""

import pytest

from bkmonitor.as_code import parse


@pytest.mark.parametrize(
    "directory", ["rule", "rule/snippets", "duty", "notice", "action", "assign_group", "grafana", "recording_rule"]
)
@pytest.mark.parametrize(
    "filename,data",
    [("bad.yaml", "config: ["), ("bad.yml", "config: ["), ("bad.json", '{"config":'), ("bad.txt", "{}")],
)
def test_invalid_file_returns_path_before_processing_any_configuration(mocker, directory, filename, data):
    prepare_recording_rules = mocker.patch.object(parse.recording_rule, "prepare_import")
    convert_duty_rules = mocker.patch.object(parse, "convert_duty_rules")
    path = f"{directory}/{filename}"
    errors = parse.import_code_config(
        2,
        "test-app",
        {"recording_rule/valid.yaml": "groups: []", path: data},
        incremental=False,
    )
    assert list(errors) == [path]
    assert isinstance(errors[path], str) and errors[path]
    prepare_recording_rules.assert_not_called()
    convert_duty_rules.assert_not_called()
