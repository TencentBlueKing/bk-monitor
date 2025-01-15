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
import Vue from 'vue';

import { VariablesService } from 'monitor-ui/chart-plugins/utils/variable';

import type { IViewOptions, PanelModel } from 'monitor-ui/chart-plugins/typings';
/**
 * @description: 获取单个panel数据
 * @param {PanelModel} panel panelModel
 * @param {IViewOptions} viewOptions viewOption
 * @return {*}
 */
export async function getPanelData(panel: PanelModel, viewOptions: IViewOptions) {
  if (panel?.targets?.[0]) {
    const [item] = panel.targets;
    const variablesService = new VariablesService({
      ...viewOptions,
      ...viewOptions.filters,
      ...viewOptions.variables,
    });
    const params = variablesService.transformVariables(item.data);
    const data = await Vue.prototype.$api[item.apiModule][item.apiFunc](params).catch(() => []);
    return data;
  }
}
