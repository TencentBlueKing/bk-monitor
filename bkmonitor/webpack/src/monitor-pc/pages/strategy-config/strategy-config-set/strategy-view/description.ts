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

import { MetricType } from '../../strategy-config-set-new/typings';

export const allDescription = [
  {
    type: 'time_series',
    title: window.i18n.tc('指标'),
    description: `${window.i18n.tc(
      '指标数据即时序数据。数据来源有：蓝鲸监控采集，自定义上报，计算平台，日志平台。'
    )}\n${window.i18n.tc('支持数据的汇聚和实时查询')}，${window.i18n.tc(
      '支持多指标计算、兼容PromQL、各种函数、秒级监控等。'
    )}\n${window.i18n.tc('检测算法支持：静态阈值、同环比、单指标异常智能检测、单指标预测能力。 ')}\n`,
  },
  {
    type: 'event',
    title: window.i18n.tc('事件'),
    description: `${window.i18n.tc(
      '事件包括平台默认采集的系统事件，还有自定义上报的事件。系统事件未落存储，所以辅助视图是无数据状态。'
    )}\n${window.i18n.tc('注意：系统事件暂时未落存储，所以辅助视图是无数据状态。')}\n`,
  },
  {
    type: 'log',
    title: window.i18n.tc('日志'),
    description: `${window.i18n.tc('日志即通过日志关键字匹配的数量进行告警，主要有两种')}\n${window.i18n.tc(
      '1） 来自日志平台的日志数据，通过ES Query语法查询的日志关键字告警能力。'
    )}\n${window.i18n.tc('2） 通过插件采集，在Client端进行日志关键字匹配产生事件进行上报。')}\n`,
  },
  {
    type: 'alert',
    title: window.i18n.tc('关联告警'),
    description: `${window.i18n.tc('关联告警在需要判断多个告警事件关联产生才生效时就可以使用。')}\n${window.i18n.tc(
      '支持告警事件和策略'
    )}、${window.i18n.tc('支持')}&& ||\n`,
  },
  {
    type: MetricType.MultivariateAnomalyDetection,
    title: window.i18n.tc('场景智能检测'),
    description: `${window.i18n.tc(
      '针对 综合拨测、APM、主机、K8s 等场景，提供该场景定制化的异常发现和告警功能'
    )}。\n${window.i18n.tc(
      '以 主机 场景为例，将会对指定的主机下的 CPU使用率、网卡入流量、物理内存空闲 等多个关键指标进行智能异常检测，如果检出多个指标异常，将以发生异常的主机为单位生成告警'
    )}。\n`,
  },
];
