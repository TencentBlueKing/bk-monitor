/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import { defineComponent, computed, type PropType } from 'vue';

import { Popover } from 'bkui-vue';

import type { ITraceListItem } from '../../../typings';

import './stacked-bar-chart-popover.scss';

interface ServiceColorMap {
  [key: string]: string;
}

export default defineComponent({
  name: 'StackedBarChartPopover',
  props: {
    // 服务分布数据
    data: {
      type: Object as PropType<ITraceListItem>,
      required: true,
    },
    // 服务颜色映射
    serviceColorMap: {
      type: Object as PropType<ServiceColorMap>,
      required: true,
    },
  },
  setup(props) {
    const serviceData = props.data?.service_distribution || {};
    const serviceColorMap = props.serviceColorMap || {};

    const services = computed(() =>
      Object.entries(serviceData).map(([key, value]) => ({
        name: key,
        color: serviceColorMap[key],
        percentage: value?.percentage || 0,
      }))
    );

    // 生成弹出框的内容
    const serviceContent = (
      <div class='serve-content'>
        <div class='serve-title'>{`共有 ${services.value.length} 个服务`}</div>
        {services.value.map(service => (
          <div
            key={service.name}
            class='status-wrap'
          >
            <div
              style={{ background: service.color }}
              class='status-color'
            />
            <div class='status-text'>{service.name}</div>
            <div class='status-percent'>{`${service.percentage}%`}</div>
          </div>
        ))}
      </div>
    );
    return {
      serviceContent,
      services,
    };
  },

  render() {
    return (
      <Popover
        extCls='popover-trace'
        arrow={false}
        content={this.serviceContent}
        renderType='auto'
        theme='light'
        allowHtml
      >
        <div class='stacked-bar'>
          {this.services.map(service => (
            <div
              key={service.name}
              style={{ background: service.color, width: `${service.percentage}%` }}
              class='bar'
            />
          ))}
        </div>
      </Popover>
    );
  },
});
