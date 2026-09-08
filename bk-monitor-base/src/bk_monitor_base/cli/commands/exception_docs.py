import importlib.util
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer


def scan_exception_docs(
    output_dir: Annotated[str, typer.Option("--output", "-o", help="输出目录")] = "./docs/exceptions",
    scan_path: Annotated[str, typer.Option("--scan", "-s", help="扫描路径")] = "./src",
    include_external: Annotated[bool, typer.Option("--external", help="包含外部系统异常")] = False,
) -> None:
    """
    扫描并生成异常文档

    扫描项目中的异常定义，生成美观的 HTML 和 Markdown 文档
    """
    scanner = ExceptionScanner(scan_path, include_external)
    modules_data = scanner.scan()

    # 确保输出目录存在
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    markdown_generator = MarkdownGenerator()
    markdown_content = markdown_generator.generate(modules_data)
    with open(output_path / "exceptions.md", "w", encoding="utf-8") as f:
        f.write(markdown_content)
    typer.echo(f"✅ Markdown 文档已生成: {output_path / 'exceptions.md'}")


class ExceptionClassInfo:
    """异常类信息"""

    def __init__(self, name: str, docstring: str = "", system_code: str = "", module_code: str = "", message: str = ""):
        self.name: str = name
        self.docstring: str = docstring
        self.system_code: str = system_code
        self.module_code: str = module_code
        self.message: str = message
        self.error_instances: list[tuple[str, Exception]] = []  # (错误码名称, 异常实例)


class ModuleInfo:
    """模块信息类"""

    def __init__(self, name: str, path: str):
        self.name: str = name
        self.path: str = path
        self.exception_classes: dict[str, ExceptionClassInfo] = {}  # 按异常类名组织


class ExceptionScanner:
    """异常扫描器"""

    def __init__(self, scan_path: str, include_external: bool = False):
        self.scan_path: Path = Path(scan_path)
        self.include_external: bool = include_external
        self.modules: list[ModuleInfo] = []

    def scan(self) -> list[ModuleInfo]:
        """扫描异常定义"""
        # 添加当前路径到 Python 路径
        sys.path.insert(0, str(self.scan_path.parent))

        try:
            # 扫描 domains 目录
            domains_path = self.scan_path / "bk_monitor_base" / "domains"
            if domains_path.exists():
                self._scan_domains(domains_path)

            # 如果包含外部系统，扫描其他可能的路径
            if self.include_external:
                self._scan_external_systems()

        except Exception as e:
            typer.echo(f"❌ 扫描过程中出现错误: {e}", err=True)

        return self.modules

    def _scan_domains(self, domains_path: Path):
        """扫描 domains 目录"""
        for domain_dir in domains_path.iterdir():
            if domain_dir.is_dir() and not domain_dir.name.startswith("__"):
                errors_file = domain_dir / "errors.py"
                if errors_file.exists():
                    self._scan_errors_file(errors_file, domain_dir.name)

    def _scan_external_systems(self):
        """扫描外部系统"""
        # 这里可以添加扫描 kingeye 等其他系统的逻辑
        pass

    def _scan_errors_file(self, file_path: Path, module_name: str):
        """扫描单个错误文件 - 使用动态导入"""
        try:
            # 动态导入模块
            spec = importlib.util.spec_from_file_location(f"{module_name}_errors", file_path)
            if spec is None or spec.loader is None:
                typer.echo(f"⚠️  无法加载模块规范: {file_path}")
                return

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # 创建模块信息
            module_info = ModuleInfo(name=module_name, path=str(file_path))

            # 先扫描 ErrorCodes 类，收集实际使用的异常类
            if hasattr(module, "ErrorCodes"):
                used_exception_types = self._collect_used_exception_types(module.ErrorCodes)

                # 为每个使用的异常类型创建类信息
                for exc_type in used_exception_types:
                    class_info = self._parse_exception_class_from_object(exc_type)
                    module_info.exception_classes[exc_type.__name__] = class_info

                # 然后解析错误码并关联到对应的异常类
                self._parse_error_codes_from_object(module.ErrorCodes, module_info)

            if module_info.exception_classes:
                self.modules.append(module_info)

        except Exception as e:
            typer.echo(f"⚠️  解析文件 {file_path} 时出错: {e}")

    def _collect_used_exception_types(self, error_codes_class: type) -> set[type]:
        """收集 ErrorCodes 中实际使用的异常类型"""
        used_types: set[type] = set()

        for name in dir(error_codes_class):
            if not name.startswith("_"):  # 跳过私有属性
                try:
                    error_obj = getattr(error_codes_class, name)
                    # 检查是否是异常实例
                    if isinstance(error_obj, Exception):
                        used_types.add(type(error_obj))
                except Exception as e:
                    typer.echo(f"⚠️  检查错误码 {name} 时出错: {e}")

        return used_types

    def _parse_exception_class_from_object(self, exc_class: type) -> ExceptionClassInfo:
        """从类对象解析异常类信息"""
        class_info = ExceptionClassInfo(name=exc_class.__name__, docstring=exc_class.__doc__ or "")
        # 读取类属性
        if hasattr(exc_class, "SYSTEM_CODE"):
            class_info.system_code = str(getattr(exc_class, "SYSTEM_CODE", ""))
        if hasattr(exc_class, "MODULE_CODE"):
            class_info.module_code = str(getattr(exc_class, "MODULE_CODE", ""))
        if hasattr(exc_class, "MESSAGE"):
            class_info.message = str(getattr(exc_class, "MESSAGE", ""))

        return class_info

    def _parse_error_codes_from_object(self, error_codes_class: type, module_info: ModuleInfo):
        """从 ErrorCodes 类对象解析错误码"""
        for name in dir(error_codes_class):
            if not name.startswith("_"):  # 跳过私有属性
                try:
                    error_obj = getattr(error_codes_class, name)
                    # 检查是否是异常实例
                    if isinstance(error_obj, Exception):
                        # 确定属于哪个异常类
                        exception_class_name = error_obj.__class__.__name__
                        if exception_class_name in module_info.exception_classes:
                            exception_class = module_info.exception_classes[exception_class_name]
                            # 直接存储异常实例
                            exception_class.error_instances.append((name, error_obj))
                except Exception as e:
                    typer.echo(f"⚠️  解析错误码 {name} 时出错: {e}")


class DocumentationStats:
    """文档统计信息"""

    def __init__(self, modules: list[ModuleInfo]):
        self.modules: list[ModuleInfo] = modules
        self.module_count: int = len(modules)
        self.class_count: int = sum(len(module.exception_classes) for module in modules)
        self.error_count: int = sum(
            len(exc_class.error_instances) for module in modules for exc_class in module.exception_classes.values()
        )


class ErrorCodeExtractor:
    """错误码信息提取器"""

    @staticmethod
    def extract_error_info(error_instance: Exception) -> tuple[str, str, str]:
        """提取错误实例的信息

        Returns:
            tuple: (error_code, full_code, message)
        """
        error_code = getattr(error_instance, "error_code", "") or ""

        full_code = ""
        if hasattr(error_instance, "get_error_code"):
            try:
                full_code = str(error_instance.get_error_code())
            except Exception:
                full_code = ""

        # 使用 _message 属性，因为 message 是 property
        message = getattr(error_instance, "_message", str(error_instance))

        return error_code if error_code else "- -", full_code if full_code else "- -", message if message else "- -"


class BaseDocumentGenerator:
    """文档生成器基类"""

    def __init__(self):
        self.stats: DocumentationStats | None = None
        self.extractor: ErrorCodeExtractor = ErrorCodeExtractor()

    def generate(self, modules: list[ModuleInfo]) -> str:
        """生成文档的主方法"""
        self.stats = DocumentationStats(modules)

        # 模板方法模式
        header = self._generate_header()
        toc = self._generate_table_of_contents()
        content = self._generate_modules_content()
        footer = self._generate_footer()

        return self._combine_parts(header, toc, content, footer)

    def _generate_header(self) -> str:
        """生成文档头部 - 子类需要实现"""
        raise NotImplementedError

    def _generate_table_of_contents(self) -> str:
        """生成目录 - 子类需要实现"""
        raise NotImplementedError

    def _generate_modules_content(self) -> str:
        """生成模块内容 - 子类需要实现"""
        raise NotImplementedError

    def _generate_footer(self) -> str:
        """生成页脚 - 子类需要实现"""
        raise NotImplementedError

    def _combine_parts(self, header: str, toc: str, content: str, footer: str) -> str:
        """组合各部分内容 - 子类可以重写"""
        return f"{header}\n{toc}\n{content}\n{footer}"


class MarkdownGenerator(BaseDocumentGenerator):
    """Markdown 文档生成器"""

    def _generate_header(self) -> str:  # pyright: ignore[reportImplicitOverride]
        """生成 Markdown 头部"""
        assert self.stats is not None
        return "\n".join(
            [
                "# 🛡️ 异常处理文档\n",
                f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
                "**说明**: 本文档自动生成，展示系统中按异常类层级组织的错误码定义。\n",
                f"**统计**: {self.stats.module_count} 个模块，{self.stats.class_count} 个异常类，{self.stats.error_count} 个错误码\n",
            ]
        )

    def _generate_table_of_contents(self) -> str:  # pyright: ignore[reportImplicitOverride]
        """生成 Markdown 目录"""
        assert self.stats is not None
        toc_lines = ["## 📋 目录\n"]

        for module in self.stats.modules:
            toc_lines.append(f"- [{module.name.upper()}](#{module.name.lower()})")
            for exc_class_name in module.exception_classes:
                toc_lines.append(f"  - [{exc_class_name}](#{module.name.lower()}-{exc_class_name.lower()})")

        toc_lines.append("")
        return "\n".join(toc_lines)

    def _generate_modules_content(self) -> str:  # pyright: ignore[reportImplicitOverride]
        """生成 Markdown 模块内容"""
        assert self.stats is not None
        content_lines: list[str] = []

        for module in self.stats.modules:
            content_lines.extend(self._generate_module_section(module))
            content_lines.append("---\n")

        return "\n".join(content_lines)

    def _generate_module_section(self, module: ModuleInfo) -> list[str]:
        """生成单个模块的 Markdown 内容"""
        lines = [f"## {module.name.upper()}\n", f"**模块路径**: `{module.path}`\n"]

        for exc_class_name, exc_class in module.exception_classes.items():
            lines.extend(self._generate_exception_class_section(module, exc_class_name, exc_class))

        return lines

    def _generate_exception_class_section(
        self, module: ModuleInfo, exc_class_name: str, exc_class: ExceptionClassInfo
    ) -> list[str]:
        """生成异常类的 Markdown 内容"""
        lines = [f"### {exc_class_name} {{#{module.name.lower()}-{exc_class_name.lower()}}}\n"]

        if exc_class.docstring:
            lines.append(f"**说明**: {exc_class.docstring}\n")

        # 异常类属性表格
        lines.extend(
            [
                "**类属性**:",
                "| 属性 | 值 |",
                "|------|------|",
                f"| 系统代码 | `{exc_class.system_code}` |",
                f"| 模块代码 | `{exc_class.module_code}` |",
                f"| 默认消息 | {exc_class.message} |",
                "",
            ]
        )

        # 错误码表格
        if exc_class.error_instances:
            lines.extend(self._generate_error_codes_table(exc_class.error_instances))
        else:
            lines.append("*暂无错误码定义*\n")

        return lines

    def _generate_error_codes_table(self, error_instances: list[tuple[str, Exception]]) -> list[str]:
        """生成错误码表格"""
        lines = [
            "**错误码列表**:",
            "| 错误名称 | 错误码 | 完整代码 | 错误描述 |",
            "|----------|--------|----------|----------|",
        ]

        for error_name, error_instance in error_instances:
            error_code, full_code, message = self.extractor.extract_error_info(error_instance)
            lines.append(
                f"| `{error_name if error_name else '- -'}` | `{error_code if error_code else '- -'}` | `{full_code}` | {message} |"
            )

        lines.append("")
        return lines

    def _generate_footer(self) -> str:  # pyright: ignore[reportImplicitOverride]
        """生成 Markdown 页脚"""
        return ""
