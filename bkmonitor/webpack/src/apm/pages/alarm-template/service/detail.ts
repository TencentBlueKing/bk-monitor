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
import { retrieveStrategyTemplate } from 'monitor-api/modules/model';
import { getCreateVariableParams, getVariableModel } from 'monitor-pc/pages/query-template/variables';

import type { TemplateDetail } from '../components/template-form/typing';

/**
 * @description 获取告警模板详情
 * @param params 接口请求参数
 * @returns 变量列表和模板详情
 */
export const getAlarmTemplateDetail = async (params: { app_name: string; id: number }) => {
  const detailData: TemplateDetail = await retrieveStrategyTemplate(params.id, { app_name: params.app_name });
  const createVariableParams = await getCreateVariableParams(detailData.query_template?.variables || []);
  console.log(detailData, createVariableParams);
  const variablesList = createVariableParams.map(item =>
    getVariableModel({ ...item, value: detailData.context[item.name.slice(2, item.name.length - 1)] })
  );
  return {
    detailData,
    variablesList,
  };
};
