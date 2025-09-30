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

import { getFunctions } from 'monitor-api/modules/grafana';
import { relationQueryTemplate, retrieveQueryTemplate } from 'monitor-api/modules/model';

import { type QueryTemplateListItem, Expression } from '../typings';
import { getCreateVariableParams, getVariableModel } from '../variables';
import { getRetrieveQueryTemplateQueryConfigs } from './metric';

/**
 * @description 获取查询模板详情
 * @param {QueryTemplateListItem['id']} templateId 查询模板ID
 */
export const fetchQueryTemplateDetail = async (templateId: QueryTemplateListItem['id']) => {
  const detail = await retrieveQueryTemplate(templateId).catch(() => ({
    query_configs: [],
    variables: [],
  }));
  const expressionConfig = new Expression({
    expression: detail.expression,
    functions: detail.functions.map(f => {
      if (typeof f === 'string') {
        return {
          id: f,
          name: '',
          params: [],
        };
      }
      return f;
    }),
  });
  let queryConfigs = [];
  if (detail.query_configs?.length) {
    queryConfigs = await getRetrieveQueryTemplateQueryConfigs(detail.query_configs);
  }
  const createVariableParams = await getCreateVariableParams(
    detail.variables,
    queryConfigs.map(item => item.metricDetail)
  );
  const variables = createVariableParams.map(item => getVariableModel(item));
  const metricFunctions = await getFunctions().catch(() => []);
  return {
    name: detail.name,
    bk_biz_id: detail.bk_biz_id,
    description: detail.description,
    can_edit: detail.can_edit,
    can_delete: detail.can_delete,
    alias: detail.alias,
    space_scope: detail.space_scope,
    queryConfigs,
    variables,
    metricFunctions,
    expressionConfig,
  };
};

/**
 * @description 获取查询模板关联资源
 * @param {QueryTemplateListItem['id']} templateId 查询模板ID
 */
export const fetchQueryTemplateRelation = async (templateId: QueryTemplateListItem['id']) => {
  const relationInfo = await relationQueryTemplate(templateId).catch(() => ({ total: 0, list: [] }));
  return relationInfo;
};
