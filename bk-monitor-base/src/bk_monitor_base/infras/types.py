from io import BufferedRandom, BytesIO, FileIO, StringIO, TextIOWrapper

from django.core.files.base import ContentFile, File

# 定义JSON类型
JSON_TYPE = list["JSON_TYPE"] | dict[str, "JSON_TYPE"] | int | float | str | bool | None

# 定义文件或内容类型
FILE_OR_CONTENT_TYPE = File | ContentFile | bytes | str | FileIO | StringIO | BytesIO | TextIOWrapper | BufferedRandom
