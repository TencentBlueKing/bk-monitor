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
import base64Svg from 'monitor-common/svg/base64';
const templateIconEnum = {
  DEFAULT: 'DEFAULT',
  P99: 'P99',
  AVG: 'AVG',
  SUCCESS_RATE: 'SUCCESS_RATE',
  CICD: 'CICD',
};

export const templateIconMap = {
  [templateIconEnum.DEFAULT]: 'icon-gaojing',
  [templateIconEnum.P99]: 'icon-a-99haoshi',
  [templateIconEnum.AVG]: 'icon-pingjunhaoshi',
  [templateIconEnum.SUCCESS_RATE]: 'icon-check',
  [templateIconEnum.CICD]: base64Svg.bkci,
};

export const systemMap = {
  RPC: window.i18n.t('调用分析模板'),
  RPC_CALLEE: window.i18n.t('主调'),
  RPC_CALLER: window.i18n.t('被调'),
  K8S: window.i18n.t('容器'),
  LOG: window.i18n.t('日志'),
  TRACE: window.i18n.t('调用链'),
  EVENT: window.i18n.t('事件'),
};
