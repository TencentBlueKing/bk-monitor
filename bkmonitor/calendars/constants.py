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

from django.utils.translation import gettext_lazy as _

# 删除事项类型
DELETE_ALL = 0
DELETE_CURRENT = 1
DELETE_FEATURE = 2

DELETE_TYPE = {DELETE_ALL: _("删除整个事项"), DELETE_CURRENT: _("删除当前事项"), DELETE_FEATURE: _("删除当前事项及未来所有事项")}
DELETE_TYPE_LIST = list(DELETE_TYPE.keys())

# 编辑事项类型
CHANGE_ALL = 0
CHANGE_CURRENT = 1
CHANGE_FEATURE = 2

CHANGE_TYPE = {CHANGE_ALL: _("修改整个事项"), CHANGE_CURRENT: _("修改当前事项"), CHANGE_FEATURE: _("修改当前事项及未来所有事项")}
CHANGE_TYPE_LIST = list(CHANGE_TYPE.keys())

# 时区
TIME_ZONE_DICT = {
    _("香港"): "Asia/Hong_Kong",
    _("重庆"): "Asia/Chongqing",
    _("澳门"): "Asia/Macao",
    _("台北"): "Asia/Taipei",
    _("上海"): "Asia/Shanghai",
    _("维也纳"): "Europe/Vienna",
    _("都柏林"): "Europe/Dublin",
    _("雷克雅未克"): "Atlantic/Reykjavik",
    _("明斯克"): "Europe/Minsk",
    _("索非亚"): "Europe/Sofia",
    _("华沙"): "Europe/Warsaw",
    _("柏林"): "Europe/Berlin",
    _("哥本哈根"): "Europe/Copenhagen",
    _("莫斯科"): "Europe/Moscow",
    _("巴黎"): "Europe/Paris",
    _("赫尔辛基"): "Europe/Helsinki",
    _("阿姆斯特丹"): "Europe/Amsterdam",
    _("布拉格"): "Europe/Prague",
    _("里加"): "Europe/Riga",
    _("维尔纽斯"): "Europe/Vilnius",
    _("布加勒斯特"): "Europe/Bucharest",
    _("斯科普里"): "Europe/Skopje",
    _("卢森堡"): "Europe/Luxembourg",
    _("摩纳哥"): "Europe/Monaco",
    _("奥斯路"): "Europe/Oslo",
    _("里斯本"): "Europe/Lisbon",
    _("斯德哥尔摩"): "Europe/Stockholm",
    _("布拉提斯拉发"): "Europe/Bratislava",
    _("卢布尔雅那"): "Europe/Ljubljana",
    _("基辅"): "Europe/Kiev",
    _("马德里"): "Europe/Madrid",
    _("雅典"): "Europe/Athens",
    _("布达佩斯"): "Europe/Budapest",
    _("罗马"): "Europe/Rome",
    _("伦敦"): "Europe/London",
    _("喀布尔"): "Asia/Kabul",
    _("马斯喀特"): "Asia/Muscat",
    _("巴库"): "Asia/Baku",
    _("廷布"): "Asia/Thimphu",
    _("平壤"): "Asia/Pyongyang",
    _("马尼拉"): "Asia/Manila",
    _("首尔"): "Asia/Seoul",
    _("金边"): "Asia/Phnom_Penh",
    _("科威特"): "Asia/Kuwait",
    _("万象"): "Asia/Vientiane",
    _("贝鲁特"): "Asia/Beirut",
    _("吉隆坡"): "Asia/Kuala_Lumpur",
    _("达卡"): "Asia/Dhaka",
    _("仰光"): "Asia/Yangon",
    _("加德满都"): "Asia/Kathmandu",
    _("东京"): "Asia/Tokyo",
    _("利雅得"): "Asia/Riyadh",
    _("科伦坡"): "Asia/Colombo",
    _("曼谷"): "Asia/Bangkok",
    _("塔什干"): "Asia/Tashkent",
    _("新加坡"): "Asia/Singapore",
    _("大马士革"): "Asia/Damascus",
    _("德黑兰"): "Asia/Tehran",
    _("巴格达"): "Asia/Baghdad",
    _("耶路撒冷"): "Asia/Jerusalem",
    _("雅加达"): "Asia/Jakarta",
    _("安曼"): "Asia/Amman",
    _("哈瓦那"): "America/Havana",
    _("波哥大"): "America/Bogota",
    _("利马"): "America/Lima",
    _("墨西哥城"): "America/Mexico_City",
    _("蒙得维的亚"): "America/Montevideo",
    _("加拉加斯"): "America/Caracas",
    _("圣地亚哥"): "America/Santiago",
    _("巴拿马"): "America/Panama",
    _("阿尔及尔"): "Africa/Algiers",
    _("开罗"): "Africa/Cairo",
    _("亚的斯亚贝巴"): "Africa/Addis_Ababa",
    _("罗安达"): "Africa/Luanda",
    _("布琼布拉"): "Africa/Bujumbura",
    _("马拉博"): "Africa/Malabo",
    _("布拉柴维尔"): "Africa/Brazzaville",
    _("金沙萨"): "Africa/Kinshasa",
    _("科纳克里"): "Africa/Conakry",
    _("哈拉雷"): "Africa/Harare",
    _("内罗华"): "Africa/Nairobi",
    _("的黎波里"): "Africa/Tripoli",
    _("塔那那利佛"): "Indian/Antananarivo",
    _("努瓦克肖特"): "Africa/Nouakchott",
    _("温得和克"): "Africa/Windhoek",
    _("喀土穆"): "Africa/Khartoum",
    _("摩加迪沙"): "Africa/Mogadishu",
    _("突尼斯"): "Africa/Tunis",
    _("坎帕拉"): "Africa/Kampala",
    _("卢萨卡"): "Africa/Lusaka",
    _("恩贾梅纳"): "Africa/Ndjamena",
    _("班吉"): "Africa/Bangui",
    _("堪培拉"): "Australia/Canberra",
    _("莫尔兹比港"): "Pacific/Port_Moresby",
    _("夏威夷檀香山"): "Pacific/Honolulu",
    _("阿拉斯加安克雷奇"): "America/Anchorage",
    _("洛杉矶"): "America/Los_Angeles",
    _("凤凰城"): "America/Phoenix",
    _("丹佛"): "America/Denver",
    _("圣保罗"): "America/Sao_Paulo",
    _("芝加哥"): "America/Chicago",
    _("印地安纳波利斯"): "America/Indianapolis",
    _("底特律"): "America/Detroit",
    _("纽约"): "America/New_York",
    _("艾德蒙顿"): "America/Edmonton",
    _("温尼伯"): "America/Winnipeg",
    _("温哥华"): "America/Vancouver",
    _("多伦多"): "America/Toronto",
    _("蒙特利尔"): "America/Montreal",
    _("圣约翰斯"): "America/St_Johns",
    _("哈里法克斯"): "America/Halifax",
    _("布里斯班"): "Australia/Brisbane",
    _("墨尔本"): "Australia/Melbourne",
    _("悉尼"): "Australia/Sydney",
    _("阿德莱德"): "Australia/Adelaide",
    _("达尔文"): "Australia/Darwin",
    _("珀斯"): "Australia/Perth",
    _("符拉迪沃斯托克"): "Asia/Vladivostok",
    _("堪察加"): "Asia/Kamchatka",
    _("阿纳德尔"): "Asia/Anadyr",
    _("苏黎世"): "Europe/Zurich",
    _("危地马拉"): "America/Guatemala",
    _("特古西加尔巴"): "America/Tegucigalpa",
    _("马那瓜"): "America/Managua",
    _("亚丁"): "Asia/Aden",
    _("阿尔及尔"): "Africa/Algiers",
    _("圣诞岛"): "Pacific/Kiritimati",
    _("卡拉奇"): "Asia/Karachi",
    _("查塔姆群岛"): "Pacific/Chatham",
    _("奥克兰"): "Pacific/Auckland",
}


class ItemFreq:
    """
    事项频率
    """

    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"
