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
import { Component, Inject, Provide, ProvideReactive } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import MonitorK8sApm from 'monitor-pc/pages/monitor-k8s/monitor-k8s-apm';

@Component
export default class ApmMonitorK8s extends tsc<Record<string, never>> {
  // 处理时间范围变化
  @Inject('handleTimeRangeChange') handleTimeRangeChange: (v: [string, string]) => void;
  // 处理自定义路由参数变化
  @Inject({ from: 'handleCustomRouteQueryChange', default: () => {} }) handleCustomRouteQueryChange: (
    customRouteQuery: Record<string, number | string>
  ) => void;

  @ProvideReactive('isApmMonitor') isApmMonitor = true;

  // apm容器事件汇总处理
  @Provide('handleApmK8sNewEventChange')
  handleK8sNewEventChange(eventName: string, params: any) {
    // 图表滑动时间范围同步
    if (eventName === 'apmK8sNewTimeRangeChange') {
      this.handleTimeRangeChange(params);
      return;
    }
    // 更新apm自定义路由参数
    if (eventName === 'apmK8sNewCustomRouteQueryChange') {
      this.handleCustomRouteQueryChange({
        apmK8sParams: JSON.stringify(params),
      });
      return;
    }
  }

  render() {
    return <MonitorK8sApm />;
  }
}
