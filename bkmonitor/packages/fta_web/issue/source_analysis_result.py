"""源码分析成功结果的版本化协议校验。"""

import json

from jsonschema import Draft202012Validator

from constants.issue import SourceAnalysisFailureMessage, SourceAnalysisResultType


SOURCE_ANALYSIS_RESULT_SCHEMA_VERSION = "1.0.0"

# 与 TAPD《源码分析结果 JSON Schema v1.0.0、Mock 与页面字段映射》保持一致。
# 任务状态与技术失败不进入该 Schema，只校验 BKFara 已成功生成的业务结果。
SOURCE_ANALYSIS_RESULT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "urn:tencent:blueking:bkm:source-ai-analysis-result:1.0.0",
    "title": "BKMonitor Issue 源码 AI 分析结果",
    "description": "成功完成分析后的业务结果。任务失败状态不进入本协议。",
    "type": "object",
    "additionalProperties": False,
    "required": ["schema_version", "result_type", "result_card", "content_type", "content"],
    "properties": {
        "schema_version": {"const": SOURCE_ANALYSIS_RESULT_SCHEMA_VERSION},
        "result_type": {
            "type": "string",
            "enum": [
                SourceAnalysisResultType.HIGH_CONFIDENCE,
                SourceAnalysisResultType.INSUFFICIENT_EVIDENCE,
            ],
        },
        "result_card": {
            "type": "object",
            "additionalProperties": False,
            "required": ["description", "responsibility"],
            "properties": {
                "description": {"type": "string", "minLength": 1},
                "responsibility": {
                    "oneOf": [
                        {"$ref": "#/$defs/responsibility"},
                        {"type": "null"},
                    ]
                },
            },
        },
        "content_type": {"const": "text/markdown"},
        "content": {"type": "string", "minLength": 1},
    },
    "allOf": [
        {
            "if": {
                "properties": {"result_type": {"const": SourceAnalysisResultType.INSUFFICIENT_EVIDENCE}},
                "required": ["result_type"],
            },
            "then": {
                "properties": {
                    "result_card": {
                        "properties": {
                            "responsibility": {"type": "null"},
                        }
                    }
                }
            },
        }
    ],
    "$defs": {
        "responsibility": {
            "type": "object",
            "additionalProperties": False,
            "required": ["commit_id", "commit_message", "author_name", "bk_username"],
            "properties": {
                "commit_id": {"type": "string", "pattern": "^[0-9a-fA-F]{7,64}$"},
                "commit_message": {"type": "string", "minLength": 1},
                "author_name": {"type": "string", "minLength": 1},
                "bk_username": {
                    "oneOf": [
                        {"type": "string", "minLength": 1},
                        {"type": "null"},
                    ]
                },
            },
        }
    },
}

Draft202012Validator.check_schema(SOURCE_ANALYSIS_RESULT_SCHEMA)
SOURCE_ANALYSIS_RESULT_VALIDATOR = Draft202012Validator(SOURCE_ANALYSIS_RESULT_SCHEMA)


class SourceAnalysisResultValidationError(ValueError):
    """可安全写入执行记录的结果校验错误，不携带原始结果内容。"""

    MESSAGES = {
        "RESULT_NOT_JSON": SourceAnalysisFailureMessage.RESULT_NOT_JSON,
        "RESULT_SCHEMA_UNSUPPORTED": SourceAnalysisFailureMessage.RESULT_SCHEMA_UNSUPPORTED,
        "RESULT_SCHEMA_INVALID": SourceAnalysisFailureMessage.RESULT_SCHEMA_INVALID,
        "RESULT_SEMANTIC_INVALID": SourceAnalysisFailureMessage.RESULT_SEMANTIC_INVALID,
    }

    def __init__(self, code: str, path: str | None = None):
        self.code = code
        self.path = path
        self.safe_message = self.MESSAGES[code]
        super().__init__(self.safe_message)


class SourceAnalysisResultValidator:
    """把 BKFara 临时返回边界规范化为可持久化的 v1.0.0 envelope。"""

    # 沿用 BKM Web 请求体的 10 MiB 内存边界，防止异常上游结果无限占用 Worker 内存。
    MAX_PAYLOAD_BYTES = 10 * 1024 * 1024

    @classmethod
    def validate(cls, raw_result) -> dict:
        payload = cls._parse_json(raw_result)
        cls._validate_transport_boundary(payload)

        schema_version = payload.get("schema_version")
        if isinstance(schema_version, str) and schema_version != SOURCE_ANALYSIS_RESULT_SCHEMA_VERSION:
            raise SourceAnalysisResultValidationError("RESULT_SCHEMA_UNSUPPORTED", "$.schema_version")

        result_card = payload.get("result_card")
        if (
            payload.get("result_type") == SourceAnalysisResultType.INSUFFICIENT_EVIDENCE
            and isinstance(result_card, dict)
            and result_card.get("responsibility") is not None
        ):
            raise SourceAnalysisResultValidationError(
                "RESULT_SEMANTIC_INVALID",
                "$.result_card.responsibility",
            )

        validation_error = next(SOURCE_ANALYSIS_RESULT_VALIDATOR.iter_errors(payload), None)
        if validation_error is not None:
            path = "$" + "".join(f"[{item!r}]" for item in validation_error.absolute_path)
            raise SourceAnalysisResultValidationError("RESULT_SCHEMA_INVALID", path)
        return payload

    @classmethod
    def _parse_json(cls, raw_result) -> dict:
        if isinstance(raw_result, bytes):
            if len(raw_result) > cls.MAX_PAYLOAD_BYTES:
                raise SourceAnalysisResultValidationError("RESULT_SCHEMA_INVALID")
            try:
                raw_result = raw_result.decode("utf-8")
            except UnicodeDecodeError as error:
                raise SourceAnalysisResultValidationError("RESULT_NOT_JSON") from error

        if isinstance(raw_result, str):
            try:
                if len(raw_result.encode("utf-8")) > cls.MAX_PAYLOAD_BYTES:
                    raise SourceAnalysisResultValidationError("RESULT_SCHEMA_INVALID")
                raw_result = json.loads(raw_result)
            except (UnicodeEncodeError, json.JSONDecodeError) as error:
                raise SourceAnalysisResultValidationError("RESULT_NOT_JSON") from error

        if not isinstance(raw_result, dict):
            raise SourceAnalysisResultValidationError("RESULT_SCHEMA_INVALID")
        return raw_result

    @classmethod
    def _validate_transport_boundary(cls, payload: dict) -> None:
        try:
            encoded_payload = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        except (TypeError, UnicodeEncodeError) as error:
            raise SourceAnalysisResultValidationError("RESULT_SCHEMA_INVALID") from error
        if len(encoded_payload) > cls.MAX_PAYLOAD_BYTES:
            raise SourceAnalysisResultValidationError("RESULT_SCHEMA_INVALID")
