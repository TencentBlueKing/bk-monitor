"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import math

from django.conf import settings
from django.http import HttpResponse
from PIL import Image, ImageDraw, ImageFont


def produce_watermark(text):
    if not settings.GRAPH_WATERMARK:
        text = " "

    imageW = 720
    imageH = 537
    k = 24

    textImageW = int(imageW * 1.5)  # 确定写文字图片的尺寸，如前所述，要比照片大，这里取1.5倍
    textImageH = int(imageH * 1.5)
    blank = Image.new("RGBA", (textImageW, textImageH), (255, 255, 255, 0))  # 创建用于添加文字的空白图像
    d = ImageDraw.Draw(blank)  # 创建draw对象
    d.ink = 0 + 0 * 256 + 0 * 256 * 256  # 黑色
    Font = ImageFont.truetype(settings.SIGNATURE_FONT_PATH, k)  # 创建Font对象，k之为字号
    textW, textH = Font.getbbox(text)[2:4]  # 获取文字尺寸
    d.text(((textImageW - textW) / 2, (textImageH - textH) / 2), text, font=Font, fill=(180, 180, 190, 110))
    # 旋转文字
    textRotate = blank.rotate(30)
    # textRotate.show()
    rLen = math.sqrt((textW / 2) ** 2 + (textH / 2) ** 2)
    oriAngle = math.atan(textH / textW)
    cropW = rLen * math.cos(oriAngle + math.pi / 6) * 2  # 被截取区域的宽高
    cropH = rLen * math.sin(oriAngle + math.pi / 6) * 2
    box = (
        int((textImageW - cropW) / 2 - 1) - 40,
        int((textImageH - cropH) / 2 - 1) - 40,
        int((textImageW + cropW) / 2 + 40),
        int((textImageH + cropH) / 2 + 40),
    )
    textIm = textRotate.crop(box)  # 截取文字图片
    # textIm.show()
    cropW, cropH = textIm.size

    # 旋转后的文字图片粘贴在一个新的blank图像上
    textBlank = Image.new("RGBA", (imageW, imageH), (255, 255, 255, 0))
    for i in range(4):
        if i % 2 == 1:
            continue
        for j in range(4):
            pasteBox = (int(cropW * j), int(cropH * i))
            textBlank.paste(textIm, pasteBox)
    textBlank = textBlank.resize((imageW, imageH), Image.Resampling.LANCZOS)
    return textBlank


def render_img_file(img_file):
    # serialize to HTTP response
    response = HttpResponse(content_type="image/png")
    img_file.save(response, "PNG")
    return response
