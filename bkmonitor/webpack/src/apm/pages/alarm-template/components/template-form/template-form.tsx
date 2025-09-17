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
import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { listUserGroup } from 'monitor-api/modules/model';
import VariablePanel from 'monitor-pc/pages/query-template/variables/components/variable-panel/variable-panel';

import Threshold from './detect-rules/threshold';
import { type AlgorithmItem, type TemplateDetail, TemplateTypeMap } from './typing';

import type { VariableModelType } from 'monitor-pc/pages/query-template/variables';

import './template-form.scss';

interface TemplateFormEvents {
  onAlgorithmsChange: (algorithms: AlgorithmItem[]) => void;
  onAutoApplyChange: (autoApply: boolean) => void;
  onCancel: () => void;
  onNameChange: (name: string) => void;
  onSubmit: () => void;
  onTriggerCountChange: (count: number) => void;
  onTriggerWindowChange: (window: number) => void;
  onVariableValueChange: (value: any, index: number) => void;
}

interface TemplateFormProps {
  data: TemplateDetail;
  metricFunctions?: any[];
  scene: 'edit' | 'view';
  variablesList: VariableModelType[];
}

@Component
export default class TemplateForm extends tsc<TemplateFormProps, TemplateFormEvents> {
  @Prop({ default: 'edit' }) scene: 'edit' | 'view';
  @Prop({ default: () => ({}) }) data: TemplateDetail;
  @Prop({ default: () => [] }) variablesList: VariableModelType[];
  @Prop({ default: () => [] }) metricFunctions!: any[];
  @Ref('templateForm') templateFormRef;

  alarmGroupLoading = false;

  alarmGroupList = [];

  rules = {};

  get monitorData() {
    if (this.data?.query_template?.alias) {
      return `${this.data.query_template.alias}(${this.data.query_template.name})`;
    }
    return this.data?.query_template?.name;
  }

  get selectUserGroup() {
    return this.data?.user_group_list?.map(item => item.id) || [];
  }

  handleNameChange(value: string) {
    console.log(value, 'handleNameChange');
    if (value !== this.data?.name) {
      this.$emit('nameChange', value);
    }
  }

  handleAlgorithmsChange(value: AlgorithmItem[]) {
    console.log(value, 'handleAlgorithmsChange');
    if (JSON.stringify(value) !== JSON.stringify(this.data.algorithms)) {
      this.$emit('algorithmsChange', value);
    }
  }

  handleTriggerWindowChange(value: number) {
    console.log(value, 'handleTriggerWindowChange');
    if (value !== this.data?.detect?.trigger_check_window) {
      this.$emit('triggerWindowChange', value);
    }
  }

  handleTriggerCountChange(value: number) {
    console.log(value, 'handleTriggerCountChange');
    if (value !== this.data?.detect?.trigger_count) {
      this.$emit('triggerCountChange', value);
    }
  }

  handleVariableValueChange(value: any, index: number) {
    console.log(value, index, 'handleVariableValueChange');
    this.$emit('variableValueChange', value, index);
  }

  handleChangeAutoApply(value: boolean) {
    console.log(value, 'handleChangeAutoApply');
    this.$emit('autoApplyChange', value);
  }

  handleSubmit() {
    this.templateFormRef.validate().then(() => {
      this.$emit('submit');
    });
  }

  @Emit('cancel')
  handleCancel() {}

  // 获取告警组数据
  getAlarmGroupList() {
    this.alarmGroupLoading = true;
    return listUserGroup({ exclude_detail_info: 1 })
      .then(data => {
        this.alarmGroupList = data.map(item => ({
          id: item.id,
          name: item.name,
          needDuty: item.need_duty,
          receiver:
            item?.users?.map(rec => rec.display_name).filter((item, index, arr) => arr.indexOf(item) === index) || [],
        }));
      })
      .finally(() => {
        this.alarmGroupLoading = false;
      });
  }

  mounted() {
    this.getAlarmGroupList();
  }

  render() {
    return (
      <bk-form
        ref='templateForm'
        class='template-form'
        {...{
          props: {
            model: {
              ...this.data,
              selectUserGroup: this.selectUserGroup,
            },
            rules: this.rules,
          },
        }}
        label-width={122}
      >
        <bk-form-item
          class='form-item-text'
          label={this.$tc('监控数据')}
        >
          <span class='text'>{this.monitorData}</span>
        </bk-form-item>
        <bk-form-item
          class='form-item-text mt16'
          label={this.$tc('模板类型')}
        >
          <span class='text'>{TemplateTypeMap[this.data?.system]}</span>
        </bk-form-item>
        <bk-form-item
          class='mt16'
          label={this.$tc('模板名称')}
          property='name'
          required
        >
          {this.scene === 'edit' ? (
            <bk-input
              value={this.data?.name}
              onBlur={this.handleNameChange}
              onEnter={this.handleNameChange}
            />
          ) : (
            <span>{this.data?.name}</span>
          )}
        </bk-form-item>
        <bk-form-item
          class='mt24'
          label={this.$tc('检测规则')}
          property='algorithms'
          required
        >
          <Threshold
            data={this.data?.algorithms}
            onChange={this.handleAlgorithmsChange}
          />
        </bk-form-item>
        <bk-form-item
          class='mt24'
          label={this.$tc('判断条件')}
          property='detect'
          required
        >
          <i18n path='在{0}个周期内累计满足{1}次检测算法'>
            <bk-input
              class='small-input'
              behavior='simplicity'
              show-controls={false}
              size='small'
              type='number'
              value={this.data?.detect?.trigger_check_window}
              onBlur={this.handleTriggerWindowChange}
              onEnter={this.handleTriggerWindowChange}
            />
            <bk-input
              class='small-input'
              behavior='simplicity'
              show-controls={false}
              size='small'
              type='number'
              value={this.data?.detect?.trigger_count}
              onBlur={this.handleTriggerCountChange}
              onEnter={this.handleTriggerCountChange}
            />
          </i18n>
        </bk-form-item>
        <bk-form-item
          class='mt24'
          label={this.$tc('告警组')}
          property='selectUserGroup'
          required
        >
          <bk-select
            loading={this.alarmGroupLoading}
            value={this.selectUserGroup}
            collapse-tag
            display-tag
            multiple
            searchable
          >
            {this.alarmGroupList.map(item => (
              <bk-option
                id={item.id}
                key={item.id}
                name={item.name}
              />
            ))}
          </bk-select>
        </bk-form-item>
        {this.variablesList.map((variable, index) => (
          <bk-form-item
            key={variable.id}
            label={variable.alias || variable.variableName}
          >
            <VariablePanel
              metricFunctions={this.metricFunctions}
              scene='edit'
              showLabel={false}
              variable={variable}
              variableList={this.variablesList}
              onValueChange={value => {
                this.handleVariableValueChange(value, index);
              }}
            />
          </bk-form-item>
        ))}
        <bk-form-item
          class='mt24'
          label={this.$tc('自动下发')}
          property='is_auto_apply'
        >
          <bk-switcher
            theme='primary'
            value={this.data?.is_auto_apply}
            onChange={this.handleChangeAutoApply}
          />
        </bk-form-item>
        {this.scene === 'edit' && (
          <bk-form-item
            class='submit-btns'
            label=''
          >
            <bk-button
              class='submit-btn'
              theme='primary'
              onClick={this.handleSubmit}
            >
              {this.$tc('保存')}
            </bk-button>
            <bk-button
              class='cancel-btn'
              onClick={this.handleCancel}
            >
              {this.$tc('取消')}
            </bk-button>
          </bk-form-item>
        )}
      </bk-form>
    );
  }
}
