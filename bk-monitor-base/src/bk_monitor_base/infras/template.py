from collections.abc import Callable
from typing import Any, final

from django.utils import translation
from jinja2 import Undefined
from jinja2.compiler import CodeGenerator
from jinja2.sandbox import SandboxedEnvironment
from jinja2.utils import pass_context
from typing_extensions import override


@final
class UndefinedSilently(Undefined):
    @override
    def _fail_with_undefined_error(self, *args: Any, **kwargs: Any):  # pyright: ignore[reportIncompatibleMethodOverride]
        return UndefinedSilently()

    def __unicode__(self):
        return ""

    @override
    def __str__(self):
        return ""

    __add__ = __radd__ = __mul__ = __rmul__ = __div__ = __rdiv__ = __truediv__ = __rtruediv__ = __floordiv__ = (
        __rfloordiv__
    ) = __mod__ = __rmod__ = __pos__ = __neg__ = __call__ = __getitem__ = __lt__ = __le__ = __gt__ = __ge__ = (
        __int__
    ) = __float__ = __complex__ = __pow__ = __rpow__ = __sub__ = __rsub__ = _fail_with_undefined_error


@final
class LocalOverridingCodeGenerator(CodeGenerator):
    @override
    def visit_Template(self, *args: Any, **kwargs: Any):
        super().visit_Template(*args, **kwargs)
        overrides = getattr(self.environment, "_codegen_overrides", {})

        if overrides:
            self.writeline("")

        for name, _override in overrides.items():
            self.writeline(f"{name} = {_override}")


@final
class DynAutoEscapeEnvironment(SandboxedEnvironment):
    code_generator_class = LocalOverridingCodeGenerator

    def __init__(self, *args: Any, **kwargs: Any):
        escape_func = kwargs.pop("escape_func", None)
        markup_class = kwargs.pop("markup_class", None)

        super().__init__(*args, **kwargs)

        # we need to disable constant-evaluation at compile time, because it
        # calls jinja's own escape function.
        #
        # this is done by jinja itself if a finalize function is set and it
        # is marked as a contextfunction. this is accomplished by either
        # suppling a no-op contextfunction itself or wrapping an existing
        # finalize in a contextfunction
        if self.finalize:  # pyright: ignore[reportUnnecessaryComparison]
            if not getattr(self.finalize, "jinja_pass_arg", False):  # pyright: ignore[reportUnknownArgumentType]
                _finalize: Callable[..., Any] = self.finalize  # pyright: ignore[reportUnknownVariableType]
                self.finalize = lambda _, v: _finalize(v)  # pyright: ignore[reportUnknownLambdaType]
        else:
            self.finalize = lambda _, v: v  # pyright: ignore[reportUnknownLambdaType]

        pass_context(self.finalize)  # pyright: ignore[reportUnknownArgumentType]

        self._codegen_overrides: dict[str, str] = {}

        if escape_func:
            self._codegen_overrides["escape"] = "environment.escape_func"
            self.escape_func = escape_func
            self.filters["e"] = escape_func
            self.filters["escape"] = escape_func

        if markup_class:
            self._codegen_overrides["markup"] = "environment.markup_class"
            self.markup_class = markup_class


def jinja2_environment(**options: Any) -> SandboxedEnvironment:
    """Jinja2渲染器"""
    if options.get("autoescape", False) and "escape_func" in options:
        env = DynAutoEscapeEnvironment(
            undefined=UndefinedSilently,
            extensions=["jinja2.ext.i18n"],
            escape_func=options.pop("escape_func"),
            **options,
        )
    else:
        options.pop("escape_func", None)
        env = SandboxedEnvironment(undefined=UndefinedSilently, extensions=["jinja2.ext.i18n"], **options)
    env.install_gettext_translations(translation, newstyle=True)  # pyright: ignore[reportAttributeAccessIssue]
    return env
