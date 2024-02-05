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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { IRelationStatusItem, LegendActionType } from '../../typings';

import './relation-legend.scss';

interface IStatistics {
  id: string;
  name: string;
  data: { name: string; size: number }[];
}

interface IRelationLegendProps {
  legendStatusData: IRelationStatusItem[];
  sizeCategory?: string;
}

interface IEvents {
  onStatisticsChange?: string;
  onSelectLegend?: (p: { actionType: string; item: any }) => void;
}

@Component({})
export default class RelationLegend extends tsc<IRelationLegendProps, IEvents> {
  @Prop({ default: {}, type: Array }) legendStatusData: IRelationStatusItem[];
  @Prop({ default: () => [], type: Array }) statistics: IStatistics[];
  @Prop({ default: '', type: String }) sizeCategory: string;

  dropdownShow = false;
  statisticsId = '';
  optionData = [];

  created() {
    this.statisticsId = this.sizeCategory || this.statistics[0].id;
    this.optionData = this.statistics.find(item => item.id === this.statisticsId).data as any;
  }

  @Emit('statisticsChange')
  handleChangeStatistics(item: IStatistics) {
    this.statisticsId = item.id;
    this.optionData = this.statistics.find(item => item.id === this.statisticsId).data as any;
    return this.statisticsId;
  }

  @Emit('selectLegend')
  handleLegendEvent(e: MouseEvent, actionType: LegendActionType, item: any, option: string) {
    let eventType = actionType;
    if (e.shiftKey && actionType === 'click') {
      eventType = 'shift-click';
    }
    return { actionType: eventType, item, option };
  }

  @Watch('statistics', { deep: true })
  handleStatisticsChange(val) {
    this.optionData = val.find(item => item.id === this.statisticsId).data as any;
  }

  render() {
    return (
      <div class='relation-legend'>
        <div class='legend-card relation-option'>
          <bk-dropdown-menu
            class='option-dropdown-menu'
            trigger='click'
            on-show={() => (this.dropdownShow = true)}
            on-hide={() => (this.dropdownShow = false)}
          >
            <div slot='dropdown-trigger'>
              <span class='btn-name'>{this.statistics.find(item => item.id === this.statisticsId)?.name}</span>
              <i class={['icon-monitor', this.dropdownShow ? 'icon-arrow-up' : 'icon-arrow-down']}></i>
            </div>
            <ul
              class='bk-dropdown-list'
              slot='dropdown-content'
            >
              {this.statistics.map(item => (
                <li onClick={() => this.handleChangeStatistics(item)}>
                  <a class='legend-name'>{item.name}</a>
                </li>
              ))}
            </ul>
          </bk-dropdown-menu>
          {this.optionData.map((item, index) => (
            <div
              class='legend-card-item'
              key={index}
              onClick={e => this.handleLegendEvent(e, 'click', item, this.statisticsId)}
            >
              <span
                class='circle-icon'
                style={{
                  width: `${12 + item.size}px`,
                  height: `${12 + item.size}px`,
                  background: item.select ? '#acacac' : '#fff'
                }}
              />
              <span class='legend-name'>{item.name}</span>
            </div>
          ))}
        </div>
        <div class='legend-card relation-status'>
          {this.legendStatusData.map((item, index) => (
            <div
              class='legend-card-item'
              key={index}
              onClick={e => this.handleLegendEvent(e, 'click', item, 'status')}
            >
              <span
                class='legend-icon'
                style={{ background: item.show ? item.color : '#ccc' }}
              ></span>
              <span
                class='legend-name'
                style={{ color: item.show ? '#63656e' : '#ccc' }}
              >
                {item.name}
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  }
}
