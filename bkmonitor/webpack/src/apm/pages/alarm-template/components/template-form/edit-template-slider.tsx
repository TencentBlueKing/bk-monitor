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

import { cloneStrategyTemplate, updateStrategyTemplate } from 'monitor-api/modules/model';

import { getAlarmTemplateDetail } from '../../service';
import TemplateForm from './template-form';

import type { AlgorithmItemUnion, DetectConfig, EditTemplateFormData, TemplateDetail, UserGroupItem } from './typing';
import type { VariableModelType } from 'monitor-pc/pages/query-template/variables';

import './edit-template-slider.scss';

interface EditTemplateSliderEvents {
  onShowChange: (isShow: boolean) => void;
  onSuccess: () => void;
}

interface EditTemplateSliderProps {
  appName: string;
  isShow: boolean;
  metricFunctions?: any[];
  scene?: 'clone' | 'edit';
  templateId: number;
}

@Component
export default class EditTemplateSlider extends tsc<EditTemplateSliderProps, EditTemplateSliderEvents> {
  @Prop({ default: false }) isShow!: boolean;
  @Prop({ required: true }) templateId!: number;
  /** 应用名称 */
  @Prop({ required: true }) appName!: string;
  /** 函数列表 */
  @Prop({ default: () => [] }) metricFunctions!: any[];
  /** 场景（编辑或者克隆） */
  @Prop({ default: 'edit' }) scene!: 'clone' | 'edit';

  loading = false;

  detailData: TemplateDetail = null;

  formData: EditTemplateFormData = null;

  variablesList: VariableModelType[] = [];

  @Watch('isShow')
  async handleIsShowChange(isShow: boolean) {
    if (isShow) {
      this.loading = true;
      const { detailData, variablesList } = await getAlarmTemplateDetail({
        id: this.templateId,
        app_name: this.appName,
      }).catch(() => ({ detailData: null, variablesList: [] }));
      this.detailData = detailData;
      this.formData = {
        name: this.scene === 'clone' ? `${this.detailData?.name}_copy` : this.detailData?.name,
        system: this.detailData?.system,
        algorithms: this.detailData?.algorithms,
        detect: this.detailData?.detect,
        user_group_list: this.detailData?.user_group_list,
        query_template: this.detailData?.query_template,
        is_auto_apply: this.detailData?.is_auto_apply,
      };
      this.variablesList = variablesList;
      this.loading = false;
    } else {
      this.loading = false;
    }
  }

  @Emit('showChange')
  handleShowChange(isShow: boolean) {
    return isShow;
  }

  handleNameChange(name: string) {
    this.formData.name = name;
  }

  handleAlgorithmsChange(algorithms: AlgorithmItemUnion[]) {
    this.formData.algorithms = algorithms;
  }

  handleDetectChange(detect: DetectConfig) {
    this.formData.detect = detect;
  }

  handleAlarmGroupChange(userGroupList: UserGroupItem[]) {
    this.formData.user_group_list = userGroupList;
  }

  handleVariableValueChange(value, index: number) {
    this.variablesList[index].value = value;
  }

  handleAutoApplyChange(isAutoApply: boolean) {
    this.formData.is_auto_apply = isAutoApply;
  }

  handleSubmit() {
    if (this.scene === 'edit') {
      this.handleEditSubmit();
    } else {
      this.handleCloneSubmit();
    }
  }

  /** 克隆 */
  handleCloneSubmit() {
    cloneStrategyTemplate({
      app_name: this.appName,
      source_id: this.templateId,
      edit_data: {
        name: this.formData.name,
        algorithms: this.formData.algorithms,
        detect: this.formData.detect,
        user_group_list: this.formData.user_group_list,
        context: this.variablesList.reduce((pre, cur) => {
          pre[cur.variableName] = cur.value;
          return pre;
        }, {}),
        is_auto_apply: this.formData.is_auto_apply,
        is_enabled: this.detailData.is_enabled,
      },
    }).then(() => {
      this.$bkMessage({
        message: this.$t('克隆模板成功'),
        theme: 'success',
      });
      this.$emit('success');
      this.handleShowChange(false);
    });
  }

  /** 编辑提交 */
  handleEditSubmit() {
    updateStrategyTemplate(this.detailData.id, {
      app_name: this.appName,
      name: this.formData.name,
      algorithms: this.formData.algorithms,
      detect: this.formData.detect,
      user_group_list: this.formData.user_group_list,
      context: this.variablesList.reduce((pre, cur) => {
        pre[cur.variableName] = cur.value;
        return pre;
      }, {}),
      is_auto_apply: this.formData.is_auto_apply,
      is_enabled: this.detailData.is_enabled,
    }).then(() => {
      this.$bkMessage({
        message: this.$t('模板修改成功'),
        theme: 'success',
      });
      this.$emit('success');
      this.handleShowChange(false);
    });
  }

  handleCancel() {
    this.handleShowChange(false);
  }

  render() {
    return (
      <bk-sideslider
        width={800}
        class='edit-template-slider'
        is-show={this.isShow}
        zIndex={977}
        quick-close
        {...{ on: { 'update:isShow': this.handleShowChange } }}
      >
        <div
          class='edit-template-slider-header'
          slot='header'
        >
          <span class='title'>{this.$t(this.scene === 'edit' ? '编辑模板' : '克隆模板')}</span>
          <span class='desc'>{this.detailData?.query_template?.name}</span>
        </div>
        <div
          class='edit-template-form'
          slot='content'
        >
          <TemplateForm
            data={this.formData}
            loading={this.loading}
            metricFunctions={this.metricFunctions}
            scene='edit'
            variablesList={this.variablesList}
            onAlarmGroupChange={this.handleAlarmGroupChange}
            onAlgorithmsChange={this.handleAlgorithmsChange}
            onAutoApplyChange={this.handleAutoApplyChange}
            onCancel={this.handleCancel}
            onDetectChange={this.handleDetectChange}
            onNameChange={this.handleNameChange}
            onSubmit={this.handleSubmit}
            onVariableValueChange={this.handleVariableValueChange}
          />
        </div>
      </bk-sideslider>
    );
  }
}
