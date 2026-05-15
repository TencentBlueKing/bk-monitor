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
export const PROTOCOLS = [
  {
    icon: 'icon-Opentelemetry',
    id: 'OT',
    name: window.i18n.t('OT 协议'),
    labels: ['OpenTelemetry'],
    desc: window.i18n.t(
      '遵循 OpenTelemetry 标准，数据通过 OTLP 格式上报，兼容可观测平台生态，适合已有 OTel 基础设施的团队。'
    ),
    tags: [window.i18n.t('标准格式'), window.i18n.t('生态兼容'), window.i18n.t('Trace 关联')],
  },
  {
    icon: 'icon-Aegis',
    id: 'Aegis',
    name: window.i18n.t('Aegis 协议'),
    labels: [window.i18n.t('蓝鲸原生')],
    desc: window.i18n.t('蓝鲸监控原生上报协议，接入成本低，数据结构针对 RUM 场景深度优化，适合新项目快速接入'),
    tags: [window.i18n.t('轻量接入'), window.i18n.t('深度优化'), window.i18n.t('配置简单')],
  },
];
