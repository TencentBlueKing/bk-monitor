# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
from abc import ABC, abstractmethod

from apps.api import CmsiApi
from apps.constants import NotifyType as NotifyTypeChoice
from apps.log_search.models import EmailTemplate


class NotifyBase(ABC):
    @abstractmethod
    def title(self, *args, **kwargs):
        pass

    @abstractmethod
    def content(self, *args, **kwargs):
        pass

    @abstractmethod
    def send(self, *args, **kwargs):
        pass


class EmailNotify(NotifyBase):
    def title(self, file_template, **kwargs):
        return file_template.format(**kwargs)

    def content(self, name, language, **kwargs):
        return EmailTemplate.get_content(name=name, language=language, **kwargs)

    def send(self, receivers, title, content, is_external: bool = False):
        """
        发送邮件, is_external 为 True 时，表示发送给外部用户, receivers 为邮箱地址
        """
        if is_external:
            CmsiApi.send_mail({"receiver": receivers, "title": title, "content": content})
        else:
            CmsiApi.send_mail({"receiver__username": receivers, "title": title, "content": content})


class NotifyType(object):
    """

    1. 根据采集场景加载具体实现的类
    2.
    """

    @classmethod
    def get_instance(cls, notify_type=None):
        mapping = {NotifyTypeChoice.EMAIL.value: EmailNotify}
        return mapping.get(notify_type, EmailNotify)
