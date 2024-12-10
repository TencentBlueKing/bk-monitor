import { Component, Prop, ProvideReactive } from 'vue-property-decorator';
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
import { Component as tsc } from 'vue-tsx-support';

import FlexDashboardPanel from 'monitor-ui/chart-plugins/components/flex-dashboard-panel';
import { DEFAULT_METHOD } from 'monitor-ui/chart-plugins/constants/dashbord';

import { CP_METHOD_LIST, PANEL_INTERVAL_LIST } from '../../../../constant/constant';
import { METHOD_LIST } from '../../typings/panel-tools';
import FilterVarSelectSimple from '../filter-var-select/filter-var-select-simple';
import TimeCompareSelect from '../panel-tools/time-compare-select';
import { PanelList } from './mock';

import type { IViewOptions } from 'monitor-ui/chart-plugins/typings';
import type { IPanelModel } from 'monitor-ui/chart-plugins/typings/dashboard-panel';

import './k8s-charts.scss';
@Component
export default class K8SCharts extends tsc<void> {
  @Prop() a: number;
  // 视图变量
  @ProvideReactive('viewOptions') viewOptions: IViewOptions = {};
  @ProvideReactive('timeOffset') timeOffset: string[] = [];

  // 汇聚周期
  interval: number | string = 'auto';
  // 汇聚方法
  method = DEFAULT_METHOD;
  showTimeCompare = false;
  panels: IPanelModel[] = PanelList;
  // created() {
  //   const list = [];
  //   for (const item of PanelList) {
  //     list.push(new PanelModel(item));
  //   }
  //   this.panels = list;
  // }
  updateViewOptions() {
    this.viewOptions = {
      interval: this.interval,
      method: this.method,
    };
  }
  // 刷新间隔设置
  handleIntervalChange(v: string) {
    this.interval = v;
    this.updateViewOptions();
  }
  // 汇聚方法改变时触发
  handleMethodChange(v: string) {
    this.method = v;
    this.updateViewOptions();
  }
  /** 时间对比值变更 */
  handleCompareTimeChange(timeList: string[]) {
    this.timeOffset = timeList;
    this.updateViewOptions();
  }

  handleShowTimeCompare(v: boolean) {
    if (!v) {
      this.handleCompareTimeChange([]);
    }
  }
  render() {
    return (
      <div class='k8s-charts'>
        <div class='content-converge-wrap'>
          <div class='content-converge'>
            <FilterVarSelectSimple
              field={'interval'}
              label={this.$t('汇聚周期')}
              options={PANEL_INTERVAL_LIST}
              value={this.interval}
              onChange={this.handleIntervalChange}
            />
            <FilterVarSelectSimple
              class='ml-36'
              field={'method'}
              label={this.$t('汇聚方法')}
              options={METHOD_LIST.concat(...CP_METHOD_LIST)}
              value={this.method}
              onChange={this.handleMethodChange}
            />
            <span class='ml-36 mr-8'>{this.$t('时间对比')}</span>
            <bk-switcher
              v-model={this.showTimeCompare}
              size='small'
              theme='primary'
              onChange={this.handleShowTimeCompare}
            />

            {this.showTimeCompare && (
              <TimeCompareSelect
                class='ml-18'
                timeValue={this.timeOffset}
                onTimeChange={this.handleCompareTimeChange}
              />
            )}
          </div>
        </div>
        <div class='k8s-charts-list'>
          <FlexDashboardPanel
            id='k8s-charts'
            column={1}
            panels={this.panels}
          />
        </div>
      </div>
    );
  }
}
