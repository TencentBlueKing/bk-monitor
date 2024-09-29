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
import yaml

from bkmonitor.utils.rsa.signature import Verification
from core.errors.plugin import (
    PluginVersionNotExist,
    SignatureNotSupported,
    SignatureProtocolNotExist,
)
from monitor_web.plugin.constant import PluginType
from utils import count_md5

__all__ = ["load_plugin_signature_manager", "Signature"]


class PluginSignatureManager(object):
    def __init__(self, plugin_version):
        if not plugin_version.version:
            raise PluginVersionNotExist

        self.version = plugin_version

    def signature(self, protocols=None):
        if protocols is None:
            protocols = ["default"]
        if isinstance(protocols, str):
            protocols = [protocols]

        signature_dict = dict()
        for protocol in protocols:
            signature_info = dict()
            for os_type in self.version.os_type_list:
                signature_info[os_type] = self.gen_signature_with_os(os_type, protocol)

            signature_dict[protocol] = signature_info

        return Signature(signature_dict)

    def gen_signature_with_os(self, os_type, protocol):
        result = ""
        for result in self.default(os_type, protocol):
            pass

        return result

    def default(self, os_type, protocol):
        message_maker = getattr(self, "message_by_%s" % protocol, None)
        if message_maker is None:
            raise SignatureProtocolNotExist(plugin=self.version, protocol=protocol)

        message = message_maker(os_type)
        yield message
        yield Verification(protocol).gen_signature(message)


class SignatureObj(object):
    def __init__(self, signature):
        """
        :param signature: loaded from meta.yaml (dict)
        """
        self.protocol = signature.get("protocol", "default")
        self.signature_info = signature["signature"]

    def yaml_format(self):
        return yaml.safe_dump(self.__dict__, default_flow_style=False, allow_unicode=True, encoding="utf-8")

    def verificate(self, plugin_version):
        psm = load_plugin_signature_manager(plugin_version)
        for os_type in plugin_version.os_type_list:
            if os_type not in self.signature_info:
                return False

            message = next(psm.default(os_type, self.protocol))
            if not Verification(self.protocol).verify(message, self.signature_info[os_type]):
                return False

        return True

    def __str__(self):
        return self.yaml_format()


def load_plugin_signature_manager(plugin_version):
    plugin_type = plugin_version.plugin.plugin_type
    if plugin_version.plugin.plugin_type not in SignatureManagerFactory:
        raise SignatureNotSupported(plugin_type=plugin_type)

    return SignatureManagerFactory[plugin_type](plugin_version)


class SignatureObjCollections(object):
    """manage signature with multiple protocol"""

    signature_type_info = {
        "safety": {"default"},
        "official": {"strict"},
    }

    def __init__(self, signature_dict=None):
        self.supported_protocol = set().union(*list(self.signature_type_info.values()))
        self._signature_dict = dict()
        if signature_dict:
            self.load_from_python(signature_dict)

    def load_from_file(self, signature_file_or_path):
        if hasattr(signature_file_or_path, "read"):
            signature_file = signature_file_or_path
        else:
            try:
                signature_file = open(signature_file_or_path, "r")
            except IOError:
                return self

        yaml_content = signature_file.read()
        self.load_from_yaml(yaml_content)
        return self

    def load_from_yaml(self, yaml_content):
        signature_dict = yaml.load(yaml_content, Loader=yaml.FullLoader)
        self.load_from_python(signature_dict)
        return self

    def load_from_python(self, signature_dict):
        for protocol in signature_dict:
            if protocol not in self.supported_protocol:
                continue
            self._signature_dict[protocol] = SignatureObj({"protocol": protocol, "signature": signature_dict[protocol]})
        return self

    def dumps2yaml(self):
        return yaml.safe_dump(self.dumps2python(), default_flow_style=False, allow_unicode=True, encoding="utf-8")

    def dumps2python(self):
        return {sig.protocol: sig.signature_info for sig in list(self._signature_dict.values())}

    def verificate(self, signature_type, plugin_version):
        if signature_type not in self.signature_type_info:
            return False

        protocols = self.signature_type_info[signature_type] & set(self._signature_dict.keys())
        if not protocols:
            return False

        for protocol in protocols:
            signature_obj = self._signature_dict[protocol]
            if not signature_obj.verificate(plugin_version):
                return False

        return True

    def iter_verificate(self, plugin_version):
        for protocol in self._signature_dict:
            yield protocol, self._signature_dict[protocol].verificate(plugin_version)


class BasePluginSignatureProtocolMixin(object):
    def message_by_default(self, os_type, plugin_debugged=True):
        md5_list = [
            self.version.config.config_json,
            self.version.config.is_support_remote,
        ]
        if plugin_debugged:
            md5_list.append(self.version.config.debug_flag)
        return "".join(map(count_md5, md5_list))

    def message_by_strict(self, os_type):
        # 防篡改
        info_md5 = count_md5(self.version.info.info2dict())
        config_md5 = self.message_by_default(os_type, plugin_debugged=False)
        meta = self.version.plugin
        meta_fields = ["plugin_id", "plugin_type", "tag"]
        content = "".join([getattr(meta, field) for field in meta_fields])
        return count_md5(
            "".join([info_md5, config_md5, content, self.version.version_log, self.version.config.diff_fields])
        )


class ExporterPluginSignatureManager(PluginSignatureManager, BasePluginSignatureProtocolMixin):
    def message_by_default(self, os_type, plugin_debugged=True):
        # 安全认证签名
        default_message = super(ExporterPluginSignatureManager, self).message_by_default(os_type, plugin_debugged)
        return default_message + count_md5(self.version.config.file_config[os_type]["md5"])

    def message_by_strict(self, os_type):
        # 防篡改
        return super(ExporterPluginSignatureManager, self).message_by_strict(os_type)


class DataDogPluginSignatureManager(PluginSignatureManager, BasePluginSignatureProtocolMixin):
    def message_by_default(self, os_type, plugin_debugged=True):
        # 安全认证签名
        default_message = super(DataDogPluginSignatureManager, self).message_by_default(os_type, plugin_debugged)
        return default_message

    def message_by_strict(self, os_type):
        # 防篡改
        return super(DataDogPluginSignatureManager, self).message_by_strict(os_type)


class ScriptPluginSignatureManager(PluginSignatureManager, BasePluginSignatureProtocolMixin):
    def message_by_default(self, os_type, plugin_debugged=True):
        # 安全认证签名
        default_message = super(ScriptPluginSignatureManager, self).message_by_default(os_type, plugin_debugged)
        return default_message + count_md5(self.version.config.file_config[os_type])

    def message_by_strict(self, os_type):
        # 防篡改
        return super(ScriptPluginSignatureManager, self).message_by_strict(os_type)


class JMXPluginSignatureManager(PluginSignatureManager, BasePluginSignatureProtocolMixin):
    def message_by_default(self, os_type, plugin_debugged=True):
        # 安全认证签名
        default_message = super(JMXPluginSignatureManager, self).message_by_default(os_type, plugin_debugged)
        return default_message + count_md5({"config_yaml": self.version.config.collector_json["config_yaml"]})

    def message_by_strict(self, os_type):
        # 防篡改
        return super(JMXPluginSignatureManager, self).message_by_strict(os_type)


class PushgatewayPluginSignatureManager(PluginSignatureManager, BasePluginSignatureProtocolMixin):
    def message_by_default(self, os_type, plugin_debugged=True):
        # 安全认证签名
        default_message = super(PushgatewayPluginSignatureManager, self).message_by_default(os_type, plugin_debugged)
        return default_message

    def message_by_strict(self, os_type):
        # 防篡改
        return super(PushgatewayPluginSignatureManager, self).message_by_strict(os_type)


class BuiltInPluginSignatureManager(PluginSignatureManager, BasePluginSignatureProtocolMixin):
    def message_by_default(self, os_type, plugin_debugged=True):
        # 安全认证签名
        default_message = super(BuiltInPluginSignatureManager, self).message_by_default(os_type, plugin_debugged)
        return default_message

    def message_by_strict(self, os_type):
        # 防篡改
        return super(BuiltInPluginSignatureManager, self).message_by_strict(os_type)


class LogPluginSignatureManager(PluginSignatureManager, BasePluginSignatureProtocolMixin):
    def message_by_default(self, os_type, plugin_debugged=True):
        # 安全认证签名
        return super(LogPluginSignatureManager, self).message_by_default(os_type, plugin_debugged)

    def message_by_strict(self, os_type):
        # 防篡改
        return super(LogPluginSignatureManager, self).message_by_strict(os_type)


class ProcessPluginSignatureManager(BuiltInPluginSignatureManager):
    pass


class SNMPTrapPluginSignatureManager(PluginSignatureManager, BasePluginSignatureProtocolMixin):
    def message_by_default(self, os_type, plugin_debugged=True):
        # 安全认证签名
        return super(SNMPTrapPluginSignatureManager, self).message_by_default(os_type, plugin_debugged)

    def message_by_strict(self, os_type):
        # 防篡改
        return super(SNMPTrapPluginSignatureManager, self).message_by_strict(os_type)


class SNMPPluginSignatureManager(PluginSignatureManager, BasePluginSignatureProtocolMixin):
    def message_by_default(self, os_type, plugin_debugged=True):
        # 安全认证签名
        default_message = super(SNMPPluginSignatureManager, self).message_by_default(os_type, plugin_debugged)
        return default_message + count_md5(self.version.config.collector_json)

    def message_by_strict(self, os_type):
        # 防篡改
        return super(SNMPPluginSignatureManager, self).message_by_strict(os_type)


class K8sPluginSignatureManager(PluginSignatureManager, BasePluginSignatureProtocolMixin):
    def message_by_default(self, os_type, plugin_debugged=True):
        # 安全认证签名
        default_message = super(K8sPluginSignatureManager, self).message_by_default(os_type, plugin_debugged)
        return default_message + count_md5(self.version.config.collector_json)

    def message_by_strict(self, os_type):
        # 防篡改
        return super(K8sPluginSignatureManager, self).message_by_strict(os_type)


SignatureManagerFactory = {
    PluginType.EXPORTER: ExporterPluginSignatureManager,
    PluginType.DATADOG: DataDogPluginSignatureManager,
    PluginType.SCRIPT: ScriptPluginSignatureManager,
    PluginType.JMX: JMXPluginSignatureManager,
    PluginType.PUSHGATEWAY: PushgatewayPluginSignatureManager,
    PluginType.BUILT_IN: BuiltInPluginSignatureManager,
    PluginType.LOG: LogPluginSignatureManager,
    PluginType.PROCESS: ProcessPluginSignatureManager,
    PluginType.SNMP_TRAP: SNMPTrapPluginSignatureManager,
    PluginType.SNMP: SNMPPluginSignatureManager,
    PluginType.K8S: K8sPluginSignatureManager,
}

Signature = SignatureObjCollections
