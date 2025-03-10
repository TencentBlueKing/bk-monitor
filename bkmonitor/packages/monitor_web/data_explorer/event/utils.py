from urllib import parse

from django.http import HttpResponse


def generate_file_download_response(file_content: str, file_name: str) -> HttpResponse:
    """生成一个带有文件内容和文件名的 HTTP 响应"""
    # 对文件名进行 URL 编码
    file_name = parse.quote(file_name, encoding="utf8")
    file_name = parse.unquote(file_name, encoding="ISO8859_1")
    response = HttpResponse(file_content)
    response["Content-Type"] = "application/x-msdownload"
    response["Content-Disposition"] = f'attachment; filename="{parse.quote(file_name, encoding="utf8")}"'
    return response
