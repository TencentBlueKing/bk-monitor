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
export const TABLE_DEFAULT_CONFIG = Object.freeze({
  tableConfig: {
    lineHeight: 32,
    align: 'left',
    showOverflow: 'ellipsis',
    emptyPlaceholder: '--',
  },
  traceConfig: {
    displayFields: [
      'trace_id',
      'min_start_time',
      'root_span_name',
      'root_service',
      'root_service_span_name',
      'root_service_category',
      'root_service_status_code',
      'trace_duration',
      'hierarchy_count',
      'service_count',
    ],
  },
  spanConfig: {
    displayFields: [
      'span_id',
      'span_name',
      'start_time',
      'end_time',
      'elapsed_time',
      'status.code',
      'kind',
      'trace_id',
    ],
  },
} as const);

/** trace检索table 状态码 不同类型显示 tag color 配置 */
export const SERVICE_STATUS_COLOR_MAP = {
  error: {
    tagColor: '#ea3536',
    tagBgColor: '#feebea',
  },
  normal: {
    tagColor: '#14a568',
    tagBgColor: '#e4faf0',
  },
};

export const TABLE_MOCK_DATA = [];
