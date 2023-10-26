# -*- coding: utf-8 -*-
import json

from rest_framework.parsers import BaseParser


class XNDJSONParser(BaseParser):
    media_type = "application/x-ndjson"

    def parse(self, stream, media_type=None, parser_context=None):
        parser_context = parser_context or {}
        encoding = parser_context.get("encoding", "utf-8")

        # 解析换行分隔的 JSON
        data = []
        for line in stream:
            decoded_line = line.decode(encoding)
            json_line = json.loads(decoded_line)
            data.append(json_line)

        return data
