/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { computed, unref } from 'vue';
import type { MaybeRef } from 'vue';

import { Message } from 'bkui-vue';
import dayjs from 'dayjs';
import { copyText as copyToClipboard } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';

import { formatUnitValue } from '../../utils';
import { OVERVIEW_DATETIME_FIELDS } from '../constants';

import type { IRumField } from '../../typings';
import type { IRumCardResolveCtx } from '../typings';

/** 详情里的时间字段以微秒存储，按秒级精度展示（设计稿不展示毫秒与时区偏移） */
const DATETIME_FORMAT = 'YYYY-MM-DD HH:mm:ss';

/**
 * @description 构造字段格式化上下文，供卡片描述符与各区块共用
 *
 * 字段别名、单位与枚举别名全部取自列表侧已拉取的 view_config，详情不重复请求字段元信息。
 * @param fields 视图配置里的全量字段
 * @param originData 当前 span 的原始数据
 */
export function useDetailFormatter(fields: MaybeRef<IRumField[]>, originData: MaybeRef<Record<string, any>>) {
  const { t } = useI18n();

  const fieldMap = computed(() => new Map(unref(fields).map(field => [field.name, field])));

  const getField = (fieldName: string) => fieldMap.value.get(fieldName);

  const getFieldAlias = (fieldName: string) => getField(fieldName)?.alias || fieldName;

  /**
   * @description 按字段元信息格式化取值：枚举别名 > 日期时间 > 单位换算 > 原样输出
   */
  const formatField = (fieldName: string, value: unknown): string => {
    if (value === null || value === undefined || value === '') return '';
    const field = getField(fieldName);
    const optionAlias = field?.option_values?.find(option => option.value === String(value))?.alias;
    if (optionAlias) return optionAlias;
    if (OVERVIEW_DATETIME_FIELDS.has(fieldName) || field?.field_display_type === 'datetime') {
      /** 时间戳位数不定（秒 / 毫秒 / 微秒），统一按毫秒对齐后交给 dayjs */
      return dayjs.tz(+String(value).slice(0, 13).padEnd(13, '0')).format(DATETIME_FORMAT);
    }
    if (field?.field_unit) return formatUnitValue(value, field.field_unit);
    return String(value);
  };

  const copyText = (value: string) => {
    copyToClipboard(value);
    Message({ theme: 'success', message: t('复制成功') });
  };

  const resolveCtx = computed<IRumCardResolveCtx>(() => ({
    originData: unref(originData) || {},
    related: {},
    getField,
    getFieldAlias,
    formatField,
    copyText,
  }));

  return { fieldMap, getField, getFieldAlias, formatField, copyText, resolveCtx };
}
