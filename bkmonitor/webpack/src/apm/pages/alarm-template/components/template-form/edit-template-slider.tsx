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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getFunctions } from 'monitor-api/modules/grafana';
import { retrieveStrategyTemplate } from 'monitor-api/modules/model';
import {
  type VariableModelType,
  getCreateVariableParams,
  getVariableModel,
} from 'monitor-pc/pages/query-template/variables';

import TemplateForm from './template-form';

import type { TemplateDetail } from './typing';

import './edit-template-slider.scss';

interface EditTemplateSliderEvents {
  onShowChange: (isShow: boolean) => void;
}

interface EditTemplateSliderProps {
  appName: string;
  isShow: boolean;
  templateId: number;
}

@Component
export default class EditTemplateSlider extends tsc<EditTemplateSliderProps, EditTemplateSliderEvents> {
  @Prop({ default: false }) isShow!: boolean;
  @Prop({ required: true }) templateId!: number;
  @Prop({ required: true }) appName!: string;

  loading = false;

  detailData: TemplateDetail = null;

  variablesList: VariableModelType[] = [];

  metricFunctions = [];

  @Watch('isShow')
  async handleIsShowChange(isShow: boolean) {
    if (isShow) {
      this.loading = true;
      this.detailData = await retrieveStrategyTemplate({
        strategy_template_id: this.templateId,
        app_name: this.appName,
      });
      const createVariableParams = await getCreateVariableParams(this.detailData.query_template?.variables);
      this.variablesList = createVariableParams.map(item =>
        getVariableModel({ ...item, value: this.detailData.context[item.name.slice(2, item.name.length - 1)] })
      );
      this.loading = false;
    } else {
      this.loading = false;
    }
  }

  async handleGetMetricFunctions() {
    this.metricFunctions = await getFunctions().catch(() => []);
  }

  mounted() {
    this.handleGetMetricFunctions();
  }

  @Emit('showChange')
  handleShowChange(isShow: boolean) {
    return isShow;
  }

  render() {
    return (
      <bk-sideslider
        width={800}
        class='edit-template-slider'
        is-show={this.isShow}
        quick-close
        {...{ on: { 'update:isShow': this.handleShowChange } }}
      >
        <div
          class='edit-template-slider-header'
          slot='header'
        >
          <span class='title'>{this.$tc('编辑模板')}</span>
          <span class='desc'>{this.detailData?.query_template?.name}</span>
        </div>
        <div
          class='edit-template-form'
          slot='content'
        >
          <TemplateForm
            data={this.detailData}
            metricFunctions={this.metricFunctions}
            scene='edit'
            variablesList={this.variablesList}
          />
        </div>
      </bk-sideslider>
    );
  }
}
