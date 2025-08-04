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
import { random } from 'lodash';
import { traceChats } from 'monitor-api/modules/apm_trace';
import { echartsConnect } from 'monitor-ui/monitor-echarts/utils';
import { defineStore } from 'pinia';

import { type IPanelModel, PanelModel } from '../../plugins/typings';

export interface ISearchState {
  // loading
  chartLoading: boolean;
  // 图表配置列表
  chartPanelList: PanelModel[];
  dashboardId: string;
}
export const useSearchStore = defineStore('search', {
  state: (): ISearchState => ({
    chartPanelList: [],
    chartLoading: false,
    dashboardId: `${random(8)}`,
  }),
  actions: {
    /**
     * @description: 获取图表配置列表
     * @param {string} appName: 应用名称
     * @return {*}
     */
    async getPanelList(appName: string) {
      this.chartLoading = true;
      const panelList = await traceChats({
        app_name: appName,
      }).catch(() => []);
      this.chartPanelList = panelList.map(
        (panel: IPanelModel) =>
          new PanelModel({
            ...panel,
            dashboardId: this.dashboardId,
          })
      );
      echartsConnect(this.dashboardId);
      this.chartLoading = false;
    },
  },
});
