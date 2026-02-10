/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
import { formatDate, formatDateNanos, random } from '../../common/util';
import { getRGBAColors } from './colors';
import JsonFormatter from './json-formatter';
import StaticUtil from './static.util';

import type OptimizedHighlighter from './optimized-highlighter';
import type RetrieveEvent from './retrieve-events';
import { EventEmitter } from './event';
import { reportRouteLog } from '@/store/modules/report-helper.ts';
import { formatTimeZoneString } from '@/global/utils/time';


export default class extends EventEmitter<RetrieveEvent> {
  // 滚动条查询条件
  globalScrollSelector: string;

  // 搜索栏高度
  searchBarHeight: number;

  // 左侧字段设置宽度
  leftFieldSettingWidth: number;

  // 左侧字段设置是否展示
  leftFieldSettingShown = true;

  // 收藏栏宽度
  favoriteWidth: number;

  // 收藏栏是否展示
  isFavoriteShown: boolean;

  // 收藏栏是否仅查看当前索引集
  isViewCurrentIndex: boolean;

  // 趋势图添加随机类名
  // 用于监听趋势图高度变化
  randomTrendGraphClassName: string;

  // 趋势图高度
  trendGraphHeight: number;

  // 索引集id列表
  indexSetIdList: string[];

  // 索引集类型
  indexSetType: string;

  markInstance: OptimizedHighlighter = undefined;

  // JSON格式化辅助
  jsonFormatter: JsonFormatter;

  // 正则表达式提取日志级别
  logLevelRegex = {
    level_1: '(?<FATAL>\\b(?:FATAL|CRITICAL|EMERGENCY)\\b)',
    level_2: '(?<ERROR>\\b(?:ERROR|ERRORCODE|ERR|FAIL(?:ED|URE)?)\\b)',
    level_3: '(?<WARNING>\\b(?:WARNING|WARN|ALERT|NOTICE)\\b)',
    level_4: '(?<INFO>\\b(?:INFO|INFORMATION|LOG|STATUS)\\b)',
    level_5: '(?<DEBUG>\\b(?:DEBUG|DIAGNOSTIC)\\b)',
    level_6: '(?<TRACE>\\b(?:TRACE|TRACING|VERBOSE|DETAIL)\\b)',
  };

  logRowsContainerId: string;

  RGBA_LIST: string[];

  isSearching = false;

  // 上报日志
  reportLog: typeof reportRouteLog;

  constructor() {
    super();
    this.randomTrendGraphClassName = `random-${random(12)}`;
    this.logRowsContainerId = `result_container_key_${random(12)}`;
    this.RGBA_LIST = getRGBAColors(0.3);
    this.jsonFormatter = new JsonFormatter();
    this.reportLog = reportRouteLog;
  }

  /**
   * 格式化时间戳
   * @param data 时间戳
   * @param fieldType 字段类型
   * @param timezoneFormat 是否进行时区格式化，默认为 false
   * @returns 格式化后的时间戳
   */
  formatDateValue(data: string, fieldType: string, timezoneFormat = false) {
    const formatFn = {
      date: (val: number | string | Date) => formatDate(val, timezoneFormat),
      date_nanos: (val: string | number) => formatDateNanos(val, timezoneFormat),
    };

    if (formatFn[fieldType]) {
      if (`${data}`.startsWith('<mark>')) {
        const value = `${data}`.replace(/^<mark>/i, '').replace(/<\/mark>$/i, '');

        if (/^\d+$/.test(value)) {
          return `<mark>${formatFn[fieldType](Number(value))}</mark>`;
        }
        return `<mark>${formatFn[fieldType](value)}</mark>`;
      }

      if (/^\d+$/.test(data)) {
        return formatFn[fieldType](Number(data)) || data || '--';
      }

      return formatFn[fieldType](data) || data || '--';
    }
    return data;
  }

  /**
   * 格式化时间戳，支持时区转换
   * @param data 时间戳或时间字符串（支持 ISO 8601 格式，如 2024-11-01T08:56:24.274552Z）
   * @param fieldType 字段类型，date 或 date_nanos
   * @param timezone 时区
   * @returns 格式化后的时间戳
   */
  formatTimeZoneValue(data: number | string, fieldType: string, timezone: string = 'Asia/Shanghai') {
    if (['date', 'date_nanos', 'date_time', 'time'].includes(fieldType)) {
      let format = 'YYYY-MM-DD HH:mm:ss';
      if (fieldType === 'date_nanos') {
        const milliseconds = `${data}`.toString().split('.')[1]?.length ?? 0;
        if (milliseconds > 0) {
          format = `YYYY-MM-DD HH:mm:ss.${'S'.repeat(milliseconds)}`;
        } else {
          format = 'YYYY-MM-DD HH:mm:ss.SSS';
        }
      }

      if (`${data}`.startsWith('<mark>')) {
        const value = `${data}`.replace(/^<mark>/i, '').replace(/<\/mark>$/i, '');

        if (/^\d+$/.test(value)) {
          return `<mark>${formatTimeZoneString(Number(value), timezone, format, false)}</mark>`;
        }

        return `<mark>${formatTimeZoneString(value, timezone, format, false)}</mark>`;
      }

      if (/^\d+$/.test(`${data}`)) {
        return formatTimeZoneString(Number(data), timezone, format, false) || data || '--';
      }

      return formatTimeZoneString(data, timezone, format, false) || data || '--';
    }

    return data || '--';
  }


  getRegExp(reg: RegExp | boolean | number | string, flgs?: string, fullMatch = false, formatRegStr = true): RegExp {
    return StaticUtil.getRegExp(reg, flgs, fullMatch, formatRegStr);
  }
}
