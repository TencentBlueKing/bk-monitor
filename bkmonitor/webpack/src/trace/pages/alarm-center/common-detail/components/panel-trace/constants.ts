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

/** 调用链表格展示字段配置信息 */
export const ALERT_TRACE_FIELD_CONFIGS = [
  {
    name: 'trace_id',
    alias: 'Trace ID',
    type: 'keyword',
    can_displayed: true,
  },
  {
    name: 'min_start_time',
    alias: window.i18n.t('开始时间'),
    type: 'long',
    can_displayed: true,
  },
  {
    name: 'root_span_name',
    alias: window.i18n.t('根 Span 接口'),
    type: 'keyword',
    can_displayed: true,
  },
  {
    name: 'root_service',
    alias: window.i18n.t('入口服务'),
    type: 'keyword',
    can_displayed: true,
  },
  {
    name: 'root_service_span_name',
    alias: window.i18n.t('入口服务接口'),
    type: 'keyword',
    can_displayed: true,
  },
  {
    name: 'error_msg',
    alias: window.i18n.t('错误信息'),
    type: 'keyword',
    can_displayed: true,
  },
];
