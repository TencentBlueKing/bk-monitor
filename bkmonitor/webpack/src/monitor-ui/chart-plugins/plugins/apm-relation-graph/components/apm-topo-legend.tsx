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
import { Component, Prop, Emit } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import type { EdgeDataType } from './utils';

import './apm-topo-legend.scss';

interface TopoLegendProps {
  edgeType: EdgeDataType;
  legendFilter: { status: string; size: string };
}

interface TopoLegendEvent {
  onEdgeTypeChange(type: EdgeDataType): void;
  onLegendFilterChange(filter: { status: string; size: string }): void;
}

@Component
export default class TopoLegend extends tsc<TopoLegendProps, TopoLegendEvent> {
  @Prop() edgeType: EdgeDataType;
  @Prop() legendFilter: { status: string; size: string };

  nodeColor = [
    { color: '#2DCB56', label: window.i18n.tc('正常'), id: 'success' },
    { color: '#FF9C01', label: window.i18n.tc('错误率 < 10%'), id: 'warning' },
    { color: '#EA3636', label: window.i18n.tc('错误率 ≥ 10%'), id: 'error' },
    { color: '#DCDEE5', label: window.i18n.tc('无数据'), id: 'empty' },
  ];
  nodeSize = [
    {
      id: 'small',
      label: window.i18n.tc('请求数 0~200'),
    },
    {
      id: 'medium',
      label: window.i18n.tc('请求数 200~1k'),
    },
    {
      id: 'large',
      label: window.i18n.tc('请求数 1k 以上'),
    },
  ];
  durationList: { id: EdgeDataType; label: string }[] = [
    { id: 'duration_avg', label: window.i18n.tc('平均耗时') },
    { id: 'duration_p99', label: window.i18n.tc('P99 耗时') },
    { id: 'duration_p95', label: window.i18n.tc('P95 耗时') },
  ];

  get scene() {
    if (this.edgeType === 'request_count') return 'request';
    return 'duration';
  }

  connectLineTypeClick(type: EdgeDataType) {
    if (type === this.edgeType) return;
    this.handleEdgeTypeChange(type);
  }

  @Emit('edgeTypeChange')
  handleEdgeTypeChange(type: EdgeDataType) {
    return type;
  }

  @Emit('legendFilterChange')
  handleLegendFilterChange(type: string, val: string) {
    if (type === 'color') {
      return {
        status: val === this.legendFilter.status ? '' : val,
        size: this.legendFilter.size,
      };
    }
    return {
      status: this.legendFilter.status,
      size: val === this.legendFilter.size ? '' : val,
    };
  }

  render() {
    return (
      <div class='topo-graph-legend'>
        <div class='filter-category'>
          <div class='filter-title'>{this.$t('节点颜色')}</div>
          <div class='filter-list node-color'>
            {this.nodeColor.map(item => (
              <div
                key={item.id}
                class={{
                  'color-item': true,
                  active: !this.legendFilter.status || this.legendFilter.status === item.id,
                }}
                onClick={() => {
                  this.handleLegendFilterChange('color', item.id);
                }}
              >
                <div
                  style={{
                    background:
                      !this.legendFilter.status || this.legendFilter.status === item.id ? item.color : '#c4c6cc',
                  }}
                  class='color-mark'
                />
                {item.label}
              </div>
            ))}
          </div>
        </div>
        <div class='filter-category'>
          <div class='filter-title'>{this.$t('节点大小')}</div>
          <div class='filter-list node-size'>
            {this.nodeSize.map(item => (
              <div
                key={item.id}
                class='node-item'
                onClick={() => {
                  this.handleLegendFilterChange('size', item.id);
                }}
              >
                <div
                  class={{
                    radio: true,
                    active: this.legendFilter.size === item.id,
                  }}
                />
                <span>{item.label}</span>
              </div>
            ))}
          </div>
        </div>
        <div class='filter-category'>
          <div class='filter-title line'>
            {this.$t('连接线')}
            <div class='line-type'>
              <div
                class={{ active: this.scene === 'request' }}
                onClick={() => {
                  this.connectLineTypeClick('request_count');
                }}
              >
                {this.$t('请求量')}
              </div>
              <div
                class={{ active: this.scene === 'duration' }}
                onClick={() => {
                  this.connectLineTypeClick('duration_avg');
                }}
              >
                {this.$t('耗时')}
              </div>
            </div>
          </div>
          <div class='filter-list connect-line'>
            {this.scene === 'request'
              ? [
                  <div
                    key='1'
                    class='request-item'
                  >
                    <div class='flow-block'>
                      {new Array(10).fill(null).map((_, index) => (
                        <div
                          key={index}
                          class='seldom'
                        />
                      ))}
                    </div>
                    {this.$t('请求量少')}
                  </div>,
                  <div
                    key='2'
                    class='request-item'
                  >
                    <div class='flow-block'>
                      {new Array(7).fill(null).map((_, index) => (
                        <div
                          key={index}
                          class='many'
                        />
                      ))}
                    </div>
                    {this.$t('请求量多')}
                  </div>,
                ]
              : this.durationList.map(item => (
                  <div
                    key={item.id}
                    class='duration-item'
                    onClick={() => {
                      this.connectLineTypeClick(item.id);
                    }}
                  >
                    <div
                      class={{
                        radio: true,
                        active: this.edgeType === item.id,
                      }}
                    />
                    <span>{item.label}</span>
                  </div>
                ))}
          </div>
        </div>
      </div>
    );
  }
}
