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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { ALL_LABEL } from './custom-escalation-detail';
import DimensionTabDetail from './dimension-tab-detail';
import MetricTabDetail from './metric-tab-detail';

import './timeseries-detail.scss';

interface IGroup {
  name: string;
  metric_count: number;
  manual_list?: string[];
  auto_rules?: string[];
}

@Component
export default class TimeseriesDetailNew extends tsc<any, any> {
  // @Prop({ default: () => [] }) metricTable;
  @Prop({ default: () => [] }) unitList;
  @Prop({ default: '' }) selectedLabel;
  @Prop({ default: () => [] }) customGroups;
  @Prop({ default: 0 }) nonGroupNum;
  @Prop({ default: 0 }) metricNum;
  @Prop({ default: 0 }) dimensionNum;
  showAddGroupDialog = false;
  /** 当前拖拽id */
  dragId = '';
  dragoverId = '';
  groupList: IGroup[] = [
    {
      name: '分组1',
      metric_count: 23,
    },
    {
      name: '分组2',
      metric_count: 2,
    },
    {
      name: '分组放大哈第三方和',
      metric_count: 3,
    },
  ];
  isShowRightWindow = true; // 是否显示右侧帮助栏

  tabs = [
    {
      title: '指标',
      id: 'metric',
    },
    {
      title: '维度',
      id: 'dimension',
    },
  ];
  activeTab = this.tabs[0].id;

  /** 分割线 ================================ */
  handleMenuClick(item) {
    // TODO
  }
  @Emit('handleClickSlider')
  handleClickSlider(v: boolean): boolean {
    return v;
  }
  @Emit('changeGroup')
  changeGroup(id: string) {
    return id;
  }

  getCmpByActiveTab(activeTab: string) {
    const cmpMap = {
      /** 指标 */
      metric: () => (
        <MetricTabDetail
          customGroups={this.customGroups}
          metricNum={this.metricNum}
          // metricTable={this.metricTable}
          {...{
            attrs: this.$attrs,
            on: {
              ...this.$listeners,
            },
          }}
          nonGroupNum={this.nonGroupNum}
          selectedLabel={this.selectedLabel}
          unitList={this.unitList}
          onChangeGroup={this.changeGroup}
          onHandleClickSlider={this.handleClickSlider}
        />
      ),
      /** 维度 */
      dimension: () => (
        <DimensionTabDetail
          {...{
            attrs: this.$attrs,
            on: {
              ...this.$listeners,
            },
          }}
        />
      ),
    };
    return cmpMap[activeTab]();
  }

  getCountByType(type: string) {
    const obj = {
      metric: this.metricNum,
      dimension: this.dimensionNum,
    };
    return obj[type];
  }

  render() {
    return (
      <div>
        <div class='list-header'>
          <div class='detail-information-title'>{this.$t('指标与维度')}</div>
          <div class='head'>
            <div class='tabs'>
              {this.tabs.map(({ title, id }) => (
                <span
                  key={id}
                  class={['tab', id === this.activeTab ? 'active' : '']}
                  onClick={() => (this.activeTab = id)}
                >
                  {`${title}(${this.getCountByType(id)})`}
                </span>
              ))}
            </div>
            <div class='tools'>
              <span class='tool'>导入</span>
              <span class='tool'>导出</span>
            </div>
          </div>
        </div>
        {this.getCmpByActiveTab(this.activeTab)}
      </div>
    );
  }
}
