from pathlib import Path, PureWindowsPath


class PathStyle:
    AUTO: str = "auto"
    WINDOWS: str = "windows"
    POSIX: str = "posix"


class PathFormatter:
    """
    跨平台路径格式化工具，支持强制生成特定平台的路径字符串
    """

    @staticmethod
    def format_path(*parts: str, style: str = PathStyle.AUTO) -> str:
        """
        格式化路径为指定风格的字符串

        :param parts: 路径部分
        :param style: 路径风格，可选值：
                      - "auto": 自动使用当前系统风格（默认）
                      - "windows": 强制 Windows 风格（反斜线）
                      - "posix": 强制 POSIX 风格（正斜线）
        :return: 格式化后的路径字符串
        :raises ValueError: 当 style 参数无效时
        """
        if style not in ("auto", "windows", "posix"):
            raise ValueError(f"Invalid style: {style}. Must be 'auto', 'windows', or 'posix'")

        if style == PathStyle.WINDOWS:
            return str(PureWindowsPath(*parts))
        elif style == PathStyle.POSIX:
            return Path(*parts).as_posix()
        else:
            # auto: 使用当前系统
            return str(Path(*parts))


# 使用示例
# ==================

# 强制 Windows 格式
# windows_path = PathFormatter.format_path("logs", "base", "app.log", style=PathStyle.WINDOWS)
# 结果：logs\base\app.log

# 强制 POSIX/Linux 格式
# posix_path = PathFormatter.format_path("logs", "base", "app.log", style=PathStyle.POSIX)
# 结果：logs/base/app.log

# 自动使用当前系统（Windows 返回反斜线，Linux 返回正斜线）
# auto_path = PathFormatter.format_path("logs", "base", "app.log", style=PathStyle.AUTO)
