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
export const NODE_TYPE_ICON = {
  // node
  apm_service: 'icon-mc-apm_service',
  apm_service_instance: 'icon-mc-service_instance',
  service: 'icon-mc-bcs-service',
  pod: 'icon-mc-pod',
  system: 'icon-mc-system',
  idc: 'icon-mc-idc',
  idc_unit: 'icon-mc-idc_unit',
  // service
  http: 'icon-wangye',
  rpc: 'icon-yuanchengfuwu',
  db: 'icon-shujuku',
  messaging: 'icon-xiaoxizhongjianjian',
  async_backend: 'icon-renwu',
  all: 'icon-mc-service-all',
  other: 'icon-mc-service-unknown',
  // python: '',
  // go: '',
  // '其他语言': '',
  metric: 'icon-zhibiaojiansuo',
  log: 'icon-a-logrizhi',
  trace: 'icon-Tracing',
  profiling: 'icon-Profiling',
};

export const getIconByNodeType = (nodeType?: string) => {
  return NODE_TYPE_ICON[nodeType as keyof typeof NODE_TYPE_ICON] || NODE_TYPE_ICON.other;
};
