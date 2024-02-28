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
import { Component, InjectReactive } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';
import bus from 'monitor-common/utils/event-bus';
import CommonTable from 'monitor-pc/pages/monitor-k8s/components/common-table';

import { PanelModel } from '../../typings';
import { TableChart } from '../table-chart/table-chart';

import './list-chart.scss';

interface INumberChartProps {
  panel: PanelModel;
}
@Component
class ListChart extends TableChart {
  // 是否在分屏展示
  @InjectReactive('isSplitPanel') isSplitPanel: boolean;
  handleDashboardModeChange() {
    if (this.isSplitPanel) {
      bus.$emit('dashboardModeChangeInSplitPanel', 'list');
    } else {
      bus.$emit('dashboardModeChange', true);
    }
  }
  render() {
    return (
      <div class='list-chart-wrap'>
        <div class='list-chart-header'>
          <span class='title'>{this.panel.title || window.i18n.t('列表')}</span>
          <span
            class='view-more'
            onClick={this.handleDashboardModeChange}
            v-bk-overflow-tips
          >
            {window.i18n.t('完整查看')}
          </span>
        </div>
        <div class='list-chart-contain'>
          {this.tableData?.length ? (
            <CommonTable
              checkable={false}
              hasColnumSetting={false}
              data={this.tableData}
              columns={this.columns}
              defaultSize='small'
              paginationType='simple'
              showLimit={false}
              pagination={this.pagination}
              onSortChange={this.handleSortChange}
              onLimitChange={this.handleLimitChange}
              onPageChange={this.handlePageChange}
            />
          ) : (
            <div class='empty-text'>{this.emptyText}</div>
          )}
        </div>
      </div>
    );
  }
}

export default ofType<INumberChartProps>().convert(ListChart);
