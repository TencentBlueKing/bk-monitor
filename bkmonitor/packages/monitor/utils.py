import json
from urllib import parse


def get_query_params(url):
    params_dict = dict(parse.parse_qsl(parse.urlparse(url).query))
    query_params = []
    for key, value in params_dict.items():
        query_params.append({"key": key, "value": value, "desc": "", "is_builtin": False, "is_enabled": True})
    return query_params


def translate_body(request):
    if not request:
        return {"data_type": "default", "params": [], "content": "", "content_type": ""}
    else:
        body = {"data_type": "raw", "params": [], "content": "", "content_type": ""}
        try:
            if json.loads(request):
                body["content_type"] = "json"
        except Exception:
            body["content_type"] = "text"
        body["content"] = request
    return body


def update_task_config(config):
    # 仅对拨测v1旧结构进行升级, v3版支持多url结构开始，不做url查询参数解析
    if config and not config.get("authorize"):
        config["headers"] = [
            {"key": item["name"], "value": item["value"], "desc": "", "is_builtin": False, "is_enabled": True}
            for item in config.get("headers", [])
        ]
        config["query_params"] = []
        config["body"] = translate_body(config.pop("request", ""))
        config["authorize"] = {
            "auth_type": "none",
            "auth_config": {},
            "insecure_skip_verify": config.pop("insecure_skip_verify", False),
        }
    return config
