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
import { Component } from 'vue-property-decorator';

import { updateQueryTemplate } from 'monitor-api/modules/model';

import TemplateCreate from '../create/template-create';
import { createQueryTemplateQueryConfigsParams, fetchQueryTemplateDetail } from '../service';
import { getVariableSubmitParams } from '../variables';
import { isVariableName } from '../variables/template/utils';

import './template-edit.scss';

@Component
export default class TemplateEdit extends TemplateCreate {
  title = this.$t('route-编辑查询模板');

  scene: 'create' | 'edit' = 'edit';

  templateBizId = 0;

  get editId() {
    return this.$route.params.id;
  }

  /**
   * @description 获取查询模板详情
   */
  async getQueryTemplateDetail() {
    this.loading = true;
    const { expressionConfig, queryConfigs, name, alias, description, space_scope, variables, bk_biz_id } =
      await fetchQueryTemplateDetail(this.editId);
    this.templateBizId = bk_biz_id;
    this.queryConfigs = queryConfigs;
    this.expressionConfig = expressionConfig;
    this.basicInfoData = {
      name,
      description,
      alias,
      space_scope: bk_biz_id === 0 ? ['all'] : space_scope,
    };
    this.variablesList = variables;
    this.loading = false;
  }

  async init() {
    this.curStep = 1;
    await this.getQueryTemplateDetail();
  }

  async handleSubmit() {
    const isClear = await this.isClearUnUsedVariable();
    const variablesList = isClear
      ? this.variablesList.filter(variable => this.useVariables.includes(variable.name))
      : this.variablesList;
    const params = {
      name: this.basicInfoData.name,
      alias: this.basicInfoData.alias,
      description: this.basicInfoData.description,
      space_scope: this.templateBizId === 0 ? [] : this.basicInfoData.space_scope,
      variables: variablesList.map(variable => getVariableSubmitParams(variable)),
      query_configs: createQueryTemplateQueryConfigsParams(this.queryConfigs),
      expression: this.expressionConfig.expression,
      functions: this.expressionConfig.functions.map(f => {
        if (isVariableName(f.id)) {
          return f.id;
        }
        return f;
      }),
    };
    this.submitLoading = true;
    const data = await updateQueryTemplate(this.editId, params).catch(() => false);
    this.submitLoading = false;
    this.needCheck = false;
    if (!data) return;
    this.$bkMessage({
      theme: 'success',
      message: this.$t('编辑查询模板成功'),
    });
    this.$router.push({
      name: 'query-template',
    });
  }
}
