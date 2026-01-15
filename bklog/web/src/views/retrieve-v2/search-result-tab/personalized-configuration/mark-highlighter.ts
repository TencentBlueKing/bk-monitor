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

import { ActionType, FormData, MatchType } from './types';

/**
 * 将匹配内容用 mark 标签包裹
 * @param content 原始内容
 * @param color 背景颜色
 * @param taskName 任务名称（用于 data-tag）
 * @returns 包裹后的内容
 */
function wrapWithMarkTag(content: string, color: string, taskName: string): string {
  const transparentColor = `${color}80`;
  return `<mark style="background-color: ${transparentColor};" data-tag="${taskName}">${content}</mark>`;
}

/**
 * 移除字符串中的所有 mark 标签（包括带属性和不带属性的）
 * @param value 包含 mark 标签的字符串
 * @returns 移除 mark 标签后的纯文本
 */
function removeMarkTags(value: string): string {
  // 匹配带属性和不带属性的 mark 标签
  const MARK_TAG_REGEX = /<mark\b[^>]*>(.*?)<\/mark>/gis;
  return value.replace(MARK_TAG_REGEX, '$1');
}

/**
 * 对字符串值应用正则匹配并包裹 mark 标签
 * @param value 字符串值
 * @param regex 正则表达式字符串
 * @param color 背景颜色
 * @param taskName 任务名称
 * @returns 处理后的值
 */
function applyRegexMark(value: string, regex: string, color: string, taskName: string): string {
  if (!value) return value;

  try {
    const regExp = new RegExp(regex, 'g');
    // 先检查是否有匹配，有存在匹配的情况下移除已有的 mark 标签
    if (regExp.test(value)) {
      const cleanValue = removeMarkTags(value);
      // 重置正则表达式的 lastIndex
      regExp.lastIndex = 0;
      return cleanValue.replace(regExp, match => wrapWithMarkTag(match, color, taskName));
    }
    return value;
  } catch (e) {
    console.warn(`正则表达式解析失败: ${regex}`, e);
    return value;
  }
}

/**
 * 处理日志列表，根据个性化配置添加 mark 标签
 * @param logList 日志列表
 * @param settings 个性化配置列表
 * @param fieldList 字段列表（用于过滤时间字段）
 * @returns 处理后的日志列表
 */
export function processLogListWithMarkHighlight(
  logList: any[],
  settings: FormData[] = [],
  fieldList: { field_name: string; field_type: string }[] = []
): any[] {
  // 1. 筛选 actionType 为 mark 的配置项
  const markSettings = settings.filter(setting => setting.actionType === ActionType.MARK);

  if (markSettings.length === 0) {
    return logList;
  }

  // 2. 创建字段名到字段类型的映射
  const fieldTypeMap = new Map<string, string>();
  fieldList.forEach(field => {
    fieldTypeMap.set(field.field_name, field.field_type);
  });

  // 3. 判断字段是否为时间字段
  const isDateField = (fieldName: string): boolean => {
    return ['date', 'date_nanos', 'long'].includes(fieldTypeMap.get(fieldName) || '');
  };

  // 4. 分离字段匹配和正则匹配配置
  const fieldMatchSettings = markSettings.filter(setting => setting.matchType === MatchType.FIELD);
  const regexMatchSettings = markSettings.filter(setting => setting.matchType === MatchType.REGEX);

  // 5. 处理每条日志记录
  return logList.map(logItem => {
    // 深拷贝日志项，避免修改原始数据
    const processedItem = { ...logItem };

    // 记录已经进行字段匹配的字段名，用于跳过正则匹配
    const fieldMatchedKeys = new Set<string>();

    // 5.1 优先处理字段匹配
    for (const setting of fieldMatchSettings) {
      const { selectField, color, taskName } = setting;

      // 检查日志项中是否存在该字段
      if (selectField && Object.prototype.hasOwnProperty.call(processedItem, selectField)) {
        // 跳过时间字段
        if (isDateField(selectField)) {
          continue;
        }

        const fieldValue = processedItem[selectField];

        // 只处理字符串类型
        if (typeof fieldValue !== 'string' || !fieldValue) {
          continue;
        }

        // 将整个字段值用 mark 标签包裹
        processedItem[selectField] = wrapWithMarkTag(fieldValue, color, taskName);
        // 记录已匹配的字段
        fieldMatchedKeys.add(selectField);
      }
    }

    // 5.2 处理正则匹配（跳过已进行字段匹配的字段和时间字段）
    for (const setting of regexMatchSettings) {
      const { regex, color, taskName } = setting;

      if (!regex) continue;

      // 遍历日志项的所有字段
      for (const key of Object.keys(processedItem)) {
        // 跳过已进行字段匹配的字段
        if (fieldMatchedKeys.has(key)) continue;
        // 跳过时间字段
        if (isDateField(key)) continue;

        const fieldValue = processedItem[key];

        // 只处理字符串类型
        if (typeof fieldValue !== 'string') {
          continue;
        }

        processedItem[key] = applyRegexMark(fieldValue, regex, color, taskName);
      }
    }

    return processedItem;
  });
}
