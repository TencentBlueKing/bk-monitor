"""
插件错误定义
"""


class MetricPluginNotFoundError(Exception):
    """
    插件不存在
    """


class MetricPluginVersionNotFoundError(Exception):
    """
    插件版本不存在
    """


class MetricPluginManagerNotFoundError(Exception):
    """
    插件管理器不存在
    """


class RegisterPluginFailedError(Exception):
    """
    注册插件失败
    """


class ExportPluginTimeoutError(Exception):
    """
    导出插件超时
    """


class ExportPluginFailedError(Exception):
    """
    导出插件失败
    """


class ParsePluginDebugContentError(Exception):
    """
    解析插件调试内容失败
    """


class MetricPluginDeploymentNotFoundError(Exception):
    """
    插件部署项不存在
    """


class MetricPluginDeploymentStatusError(Exception):
    """
    插件部署项状态错误
    """


class MetricPluginDeploymentOperationError(Exception):
    """
    插件部署项操作错误
    """


class ParseOsTypeError(Exception):
    """
    解析操作系统类型失败
    """


class DebugInstNotExistError(Exception):
    """
    调试实例不存在
    """


class PluginFileNotFoundError(Exception):
    """
    插件文件不存在
    """


class MetricPluginDeploymentExistsError(Exception):
    """
    插件部署项存在
    """


class DataIDNotFoundError(Exception):
    """
    数据ID不存在
    """


class HostInfoNotFoundError(Exception):
    """
    主机信息不存在
    """


class LogoSizeExceededError(Exception):
    """
    Logo 图片大小超过限制
    """


class PluginVersionReleasedError(Exception):
    """
    插件版本已发布，无法修改
    """


class PluginVersionLessThanReleasedError(Exception):
    """
    禁止创建小于已发布版本的版本号
    """


class MetricPluginRemoteCollectDisableError(Exception):
    """
    已开启远程采集的已发布插件不允许直接关闭远程采集
    """


class PluginIDInvalidError(Exception):
    """
    插件ID不合法
    """


class PluginIDExistsError(Exception):
    """
    插件ID已存在
    """


class PluginFileUploadError(Exception):
    """
    文件上传失败
    """


class PluginParseError(Exception):
    """
    插件解析失败
    """
