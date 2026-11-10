/**
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
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

/** 清洗类型 */
export type CleanType = 'bk_log_json' | 'bk_log_delimiter' | 'bk_log_regexp';

/** clean_type 与文本/icon 的映射 */
export const CLEAN_TYPE_MAP: Record<CleanType, { label: string; icon: string }> = {
  bk_log_json: { label: 'JSON', icon: 'bklog-icon bklog-json-fanxuliehua' },
  bk_log_delimiter: { label: '分隔符', icon: 'bklog-icon bklog-fengefu' },
  bk_log_regexp: { label: '正则', icon: 'bklog-icon bklog-zhengzetiqu' },
};

/** 获取 clean_type 文本 */
export const getCleanTypeLabel = (cleanType: CleanType): string => {
  return CLEAN_TYPE_MAP[cleanType]?.label ?? cleanType;
};

/** 获取 clean_type icon */
export const getCleanTypeIcon = (cleanType: CleanType): string => {
  return CLEAN_TYPE_MAP[cleanType]?.icon ?? '';
};
