"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import hashlib
import json

import yaml
from bkcrypto.contrib.django.fields import SymmetricTextField
from bkcrypto.symmetric.configs import KeyConfig
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from bkmonitor.utils.common_utils import DatetimeEncoder
from bkmonitor.utils.local import local
from bkmonitor.utils.text import camel_to_underscore


def get_key_config(chiper_type: str):
    if settings.BK_CRYPTO_KEY:
        return settings.BK_CRYPTO_KEY

    if settings.SPECIFY_AES_KEY != "":
        x_key = settings.SPECIFY_AES_KEY

    else:
        # 否则使用默认的配置信息进行
        x_key = getattr(local, "AES_X_KEY", getattr(settings, settings.AES_X_KEY_FIELD))

    config = KeyConfig(key=hashlib.sha256(x_key.encode("utf-8")).digest())
    return config


class ConfigDataField(models.TextField):
    """配置字段"""

    description = "Stores data with json"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_db_prep_value(self, value, connection, prepared=False):
        data = json.dumps({"_data": value})
        return data

    def from_db_value(self, value, expression, connection):
        return json.loads(value)["_data"]


class JsonField(models.TextField):
    """基于TextField实现的自动序列化和反序列化的JsonField"""

    default_error_messages = {
        "invalid": "'%(value)s' is not a valid JsonFormat.",
    }
    description = "Stores data with json"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        """
        Converts the input value into the expected Python data type, raising
        django.core.exceptions.ValidationError if the data can't be converted.
        Returns the converted value. Subclasses should override this.
        """
        if isinstance(value, str):
            try:
                return json.loads(value)
            except ValueError:
                raise ValidationError(
                    self.error_messages["invalid"],
                    code="invalid",
                    params={"value": value},
                )
        return value

    def get_db_prep_value(self, value, connection, prepared=False):
        return json.dumps(value, cls=DatetimeEncoder)

    def from_db_value(self, value, expression, connection):
        return json.loads(value or "null")


class EventStatusField(models.IntegerField):
    description = "Modify status value"
    insert_status_map = {
        "ABNORMAL_ACK": 1000,
        "ABNORMAL": 30,
        "RECOVERED": 20,
        "CLOSED": 10,
    }  # 库中不存在，但是有时会带过来查询

    query_status_map = {30: "ABNORMAL", 20: "RECOVERED", 10: "CLOSED"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_prep_value(self, value):
        return self.insert_status_map[value]

    def from_db_value(self, value, expression, connection):
        return self.query_status_map[value]


class YamlField(models.TextField):
    description = "Stores data with yaml"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_db_prep_value(self, value, connection, prepared=False):
        return yaml.safe_dump(value)

    def from_db_value(self, value, expression, connection):
        return yaml.load(value or "", Loader=yaml.FullLoader)


class SymmetricJsonField(SymmetricTextField):
    """基于SymmetricTextField实现的自动序列化和反序列化的加密Field"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_db_prep_value(self, value, connection, prepared=False):
        value = json.dumps(value)
        return super().get_db_prep_value(value, connection, prepared)

    def from_db_value(self, value, expression, connection, context=None):
        value = super().from_db_value(value, expression, connection, context)
        return json.loads(value or "null")


class ReadWithUnderscoreField(models.CharField):
    """读取数据时，将驼峰命名的字符串转换为下划线形式"""

    description = "convert string to underscore from camel when get data"

    def from_db_value(self, value, expression, connection):
        return camel_to_underscore(value)
