import colorsys
from typing import Annotated

import typer


def _apply_rainbow_filter(text: str) -> str:
    try:
        from rich.console import Console
        from rich.text import Text
    except ImportError:
        return text

    console = Console(force_terminal=True, color_system="truecolor")
    styled_text = Text()

    lines = text.splitlines()
    for i, line in enumerate(lines):
        for j, char in enumerate(line):
            if char == "\n":
                continue
            # Hue varies by position to create a diagonal rainbow effect
            hue = (i * 0.05 + j * 0.01) % 1.0
            r, g, b = colorsys.hls_to_rgb(hue, 0.5, 1.0)
            color_hex = f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"
            styled_text.append(char, style=color_hex)
        styled_text.append("\n")

    with console.capture() as capture:
        console.print(styled_text, end="")
    return capture.get()


def shell(
    colors: Annotated[str, typer.Option("--colors", help="设置 IPython 的 colors 参数")] = "neutral",
    header_filter: Annotated[str, typer.Option("--filter", help="设置 header 的 filter，例如 rainbow")] = "rainbow",
) -> None:
    """
    进入项目的 Python shell

    可以自动加载项目环境并使用IPython

    Args:
        colors: IPython 的 colors 参数
        header_filter: Header 过滤器，支持 "rainbow"
    """

    from IPython import embed  # pyright: ignore[reportUnknownVariableType]

    # https://patorjk.com/software/taag/#p=display&f=ANSI+Regular&t=bkm-base&x=none&v=4&h=4&w=80&we=false
    header = """██████  ██   ██ ███    ███       ██████   █████  ███████ ███████ 
██   ██ ██  ██  ████  ████       ██   ██ ██   ██ ██      ██      
██████  █████   ██ ████ ██ █████ ██████  ███████ ███████ █████   
██   ██ ██  ██  ██  ██  ██       ██   ██ ██   ██      ██ ██      
██████  ██   ██ ██      ██       ██████  ██   ██ ███████ ███████ 

Welcome to the BK Monitor Base shell!
This shell is pre-configured to work with the BK Monitor Base project.
You can use this shell to interact with the project's models, views, and other components.
"""

    if header_filter == "rainbow":
        header = _apply_rainbow_filter(header)

    embed(colors=colors, header=header)
