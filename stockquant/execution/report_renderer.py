# -*- coding: utf-8 -*-
"""F018 报告渲染器 — Markdown 转图片/HTML/控制台"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("stockquant.execution.report_renderer")


def render_md_to_image(
    markdown_text: str,
    output_path: str = "./report.png",
    width: int = 800,
    font_path: Optional[str] = None,
) -> str:
    """
    将 Markdown 文本渲染为图片。

    尝试使用 imgkit (wkhtmltoimage) 转换，失败时回退到纯文本图片。

    Parameters
    ----------
    markdown_text : str
        Markdown 内容
    output_path : str
        输出图片路径
    width : int
        渲染宽度
    font_path : str | None
        字体文件路径（支持中文）

    Returns
    -------
    str
        输出文件路径
    """
    try:
        import imgkit
        import markdown

        html_text = markdown.markdown(
            markdown_text,
            extensions=["tables", "fenced_code"],
        )
        html_content = f"""
        <html>
        <head><meta charset="utf-8"></head>
        <body style="font-family: sans-serif; padding: 20px;">
        {html_text}
        </body>
        </html>
        """
        imgkit.from_string(
            html_content,
            output_path,
            options={"width": width},
        )
        logger.info("Markdown rendered to image: %s", output_path)
        return output_path
    except ImportError:
        logger.warning(
            "imgkit not installed. Install with: pip install imgkit wkhtmltopdf"
        )
        return _create_text_image(markdown_text, output_path, width, font_path)
    except Exception as e:
        logger.warning("imgkit conversion failed (%s), falling back to text image", e)
        return _create_text_image(markdown_text, output_path, width, font_path)


def _create_text_image(
    text: str,
    output_path: str,
    width: int = 800,
    font_path: Optional[str] = None,
) -> str:
    """Fallback: 创建简单文本图片（使用 PIL）。"""
    from PIL import Image, ImageDraw, ImageFont

    lines = text.split("\n")
    line_height = 20
    padding = 20
    img_height = len(lines) * line_height + padding * 2
    img = Image.new("RGB", (width, img_height), color="white")
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype(font_path or "simhei.ttf", 14)
    except (OSError, IOError):
        font = ImageFont.load_default()

    y = padding
    for line in lines:
        draw.text((padding, y), line, fill="black", font=font)
        y += line_height
        if y > img_height - padding:
            break

    img.save(output_path)
    logger.info("Markdown rendered to text image: %s", output_path)
    return output_path


def render_md_to_html(markdown_text: str) -> str:
    """
    将 Markdown 转为 HTML 字符串。

    Parameters
    ----------
    markdown_text : str
        Markdown 内容

    Returns
    -------
    str
        HTML 字符串
    """
    import markdown

    return markdown.markdown(
        markdown_text,
        extensions=["tables", "fenced_code"],
    )


def render_md_to_console(markdown_text: str) -> None:
    """
    将 Markdown 文本输出到控制台（纯文本格式）。

    Parameters
    ----------
    markdown_text : str
        Markdown 内容
    """
    print(markdown_text)
