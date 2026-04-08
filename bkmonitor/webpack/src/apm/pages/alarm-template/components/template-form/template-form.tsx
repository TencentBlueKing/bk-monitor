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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { listUserGroup } from 'monitor-api/modules/model';
import VariablePanel from 'monitor-pc/pages/query-template/variables/components/variable-panel/variable-panel';

import AlgorithmRules from './algorithm-rules/algorithm-rules';
import {
  type AlgorithmItemUnion,
  type DetectConfig,
  type EditTemplateFormData,
  type UserGroupItem,
  AlgorithmEnum,
} from './typing';

import type { VariableModelType } from 'monitor-pc/pages/query-template/variables';

import './template-form.scss';

interface TemplateFormEvents {
  onAlarmGroupChange: (alarmGroup: UserGroupItem[]) => void;
  onAlgorithmsChange: (algorithms: AlgorithmItemUnion[]) => void;
  onAutoApplyChange: (autoApply: boolean) => void;
  onCancel: () => void;
  onDetectChange: (detect: DetectConfig) => void;
  onNameChange: (name: string) => void;
  onSubmit: () => void;
  onVariableValueChange: (value: any, index: number) => void;
}

interface TemplateFormProps {
  data: EditTemplateFormData;
  labelWidth?: number;
  loading?: boolean;
  metricFunctions?: any[];
  scene: 'edit' | 'view';
  variablesList: VariableModelType[];
}

@Component
export default class TemplateForm extends tsc<TemplateFormProps, TemplateFormEvents> {
  /** 场景类别 编辑 或者 预览编辑 */
  @Prop({ default: 'edit' }) scene: 'edit' | 'view';
  /** 表单数据 */
  @Prop({ default: () => ({}) }) data: EditTemplateFormData;
  /** 变量列表 */
  @Prop({ default: () => [] }) variablesList: VariableModelType[];
  /** 函数列表 */
  @Prop({ default: () => [] }) metricFunctions!: any[];

  @Prop({ default: 122 }) labelWidth!: number;

  @Prop({ default: false }) loading!: boolean;

  /** 模板表单 */
  @Ref('form') formRef;

  /** 检测规则单位 */
  algorithmsUnit = '';

  /** 用户组列表loading */
  alarmGroupLoading = false;
  /** 用户组列表 */
  alarmGroupList = [];
  /** 校验规则 */
  rules = {
    name: [
      {
        required: true,
        message: this.$t('模板名称必填'),
        trigger: 'blur',
      },
    ],
    algorithms: [
      {
        required: true,
        message: this.$t('必须选择一个检测规则'),
        trigger: 'change',
      },
      {
        validator: this.validAlgorithms,
        message: this.$t('检测算法填写不完整，请完善后添加'),
        trigger: 'blur',
      },
    ],
    detect: [
      {
        validator: this.validateDetect,
        message: this.$t('触发周期数 >=1 且 >= 检测数'),
        trigger: 'blur',
      },
    ],
    selectUserGroup: [
      {
        validator: this.validateAlarmGroup,
        message: this.$t('告警组必填'),
        trigger: 'change',
      },
    ],
  };

  get showAlarmGroupList() {
    return this.alarmGroupList.length > 0 ? this.alarmGroupList : this.data?.user_group_list || [];
  }

  /** 监控指标 */
  get monitorData() {
    if (this.data?.query_template?.alias) {
      return `${this.data.query_template.alias}(${this.data.query_template.name})`;
    }
    return this.data?.query_template?.name;
  }

  /** 已选择的用户组id */
  get selectUserGroup() {
    return this.data?.user_group_list?.map(item => item.id) || [];
  }

  @Watch('data')
  handleDataChange(val: EditTemplateFormData) {
    this.algorithmsUnit = val.algorithms?.[0]?.unit_prefix;
  }

  /** 校验告警组 */
  validateAlarmGroup() {
    return this.selectUserGroup.length > 0;
  }

  /** 校验检测规则 */
  validAlgorithms() {
    return this.data.algorithms.every(item => {
      if (item.type === AlgorithmEnum.Threshold) {
        return item.config.threshold || item.config.threshold === 0;
      }
      if (item.type === AlgorithmEnum.YearRoundAndRingRatio) {
        return item.config.ceil >= 1 && item.config.floor >= 1;
      }
      return true;
    });
  }

  /** 校验判断条件 */
  validateDetect(val: DetectConfig) {
    return !(
      val.config.trigger_check_window < 1 ||
      val.config.trigger_count < 1 ||
      `${val.config.trigger_check_window}`.match(/\./) ||
      `${val.config.trigger_count}`.match(/\./) ||
      +val.config.trigger_check_window < +val.config.trigger_count
    );
  }

  /**
   * @description 修改模板名称
   * @param value 模板名称
   */
  handleNameChange(value: string) {
    if (value !== this.data?.name) {
      this.$emit('nameChange', value);
    }
  }

  /**
   * @description 修改检测规则
   * @param value 检测规则
   */
  handleAlgorithmsChange(value: AlgorithmItemUnion[]) {
    if (JSON.stringify(value) !== JSON.stringify(this.data.algorithms)) {
      this.$emit('algorithmsChange', value);
      this.formRef?.validateField('algorithms');
    }
  }

  /**
   * @description 修改算法之间的关系
   * @param value 算法关系(or || and)
   */
  handleConnectorChange(value: string) {
    this.$emit('detectChange', {
      type: this.data?.detect?.type,
      connector: value,
      config: this.data?.detect?.config,
    });
  }

  /**
   * @description 修改判断窗口
   * @param value 窗口次数
   */
  handleTriggerWindowChange(value: number) {
    if (value !== this.data?.detect?.config.trigger_check_window) {
      this.$emit('detectChange', {
        type: this.data?.detect?.type,
        connector: this.data?.detect?.connector,
        config: {
          ...this.data?.detect?.config,
          trigger_check_window: value,
        },
      });
    }
  }

  /**
   * @description 修改触发次数
   * @param value 触发次数
   */
  handleTriggerCountChange(value: number) {
    if (value !== this.data?.detect?.config.trigger_count) {
      this.$emit('detectChange', {
        type: this.data?.detect?.type,
        config: {
          ...this.data?.detect?.config,
          trigger_count: value,
        },
      });
    }
  }

  /**
   * @description 修改用户组
   * @param value 用户组
   */
  handleUserGroupSelect(value: number[]) {
    if (JSON.stringify(value) !== JSON.stringify(this.selectUserGroup)) {
      this.$emit(
        'alarmGroupChange',
        value.map(id => {
          return {
            id,
            name: this.showAlarmGroupList.find(item => item.id === id)?.name,
          };
        })
      );
    }
  }

  /**
   * @description 修改变量值
   * @param value 新变量值
   * @param index 变量索引
   */
  handleVariableValueChange(value: any, index: number) {
    this.$emit('variableValueChange', value, index);
  }

  /**
   * 修改下发状态
   * @param value 是否下发
   */
  handleChangeAutoApply(value: boolean) {
    this.$emit('autoApplyChange', value);
  }

  /** 提交 */
  handleSubmit() {
    this.formRef.validate().then(() => {
      this.$emit('submit');
    });
  }

  handleCancel() {
    this.$emit('cancel');
  }

  handleUserGroupToggle(show: boolean) {
    if (show && !this.alarmGroupList.length) {
      this.getAlarmGroupList();
    }
  }

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

  render() {
    return (
      <div class='template-form'>
        {this.loading ? (
          <div class='bk-form template-form-skeleton-wrap'>
            {new Array(10).fill(0).map((_, ind) => (
              <div
                key={ind}
                class={[
                  'skeleton-element bk-form-item',
                  {
                    'form-item-text': ind === 0 || ind === 1,
                    'algorithm-item': ind === 3,
                  },
                ]}
              />
            ))}
          </div>
        ) : (
          <bk-form
            ref='form'
            {...{
              props: {
                model: this.data,
                rules: this.rules,
              },
            }}
            label-width={this.labelWidth}
          >
            <bk-form-item
              class='form-item-text'
              label={this.$t('监控数据')}
            >
              <span
                class='text monitor-data'
                v-bk-tooltips={{
                  content: this.data?.query_template?.description,
                  disabled: !this.data?.query_template?.description,
                }}
              >
                {this.monitorData}
              </span>
            </bk-form-item>
            <bk-form-item
              class='form-item-text mt16'
              label={this.$t('模板类型')}
            >
              <span class='text'>{this.data?.system.alias}</span>
            </bk-form-item>
            <bk-form-item
              class='mt16'
              error-display-type='normal'
              label={this.$t('模板名称')}
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
              error-display-type='normal'
              label={this.$t('检测规则')}
              property='algorithms'
              required
            >
              <AlgorithmRules
                algorithms={this.data?.algorithms}
                algorithmsUnit={this.algorithmsUnit}
                connector={this.data?.detect?.connector}
                onChange={this.handleAlgorithmsChange}
                onConnectorChange={this.handleConnectorChange}
              />
            </bk-form-item>
            <bk-form-item
              class='mt24'
              error-display-type='normal'
              label={this.$t('判断条件')}
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
                  value={this.data?.detect?.config.trigger_check_window}
                  onBlur={this.handleTriggerWindowChange}
                  onEnter={this.handleTriggerWindowChange}
                />
                <bk-input
                  class='small-input'
                  behavior='simplicity'
                  show-controls={false}
                  size='small'
                  type='number'
                  value={this.data?.detect?.config.trigger_count}
                  onBlur={this.handleTriggerCountChange}
                  onEnter={this.handleTriggerCountChange}
                />
              </i18n>
            </bk-form-item>
            <bk-form-item
              class='mt24'
              error-display-type='normal'
              label={this.$t('告警组')}
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
                onSelected={this.handleUserGroupSelect}
                onToggle={this.handleUserGroupToggle}
              >
                {this.showAlarmGroupList.map(item => (
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
                desc={{
                  width: 320,
                  content: `${this.$t('变量名')}: ${variable.variableName}<br />${this.$t('变量别名')}: ${variable.alias}<br />${this.$t('变量描述')}: ${variable.description}`,
                  allowHTML: true,
                }}
                label={variable.alias || variable.variableName}
              >
                <VariablePanel
                  metricFunctions={this.metricFunctions}
                  scene='edit'
                  showConditionTag={true}
                  showLabel={false}
                  variable={variable}
                  variableList={this.variablesList}
                  onValueChange={value => {
                    this.handleVariableValueChange(value, index);
                  }}
                />
              </bk-form-item>
            ))}
            {this.scene === 'edit' && (
              <bk-form-item
                class='mt24'
                label={this.$t('自动下发')}
                property='is_auto_apply'
              >
                <bk-switcher
                  theme='primary'
                  value={this.data?.is_auto_apply}
                  onChange={this.handleChangeAutoApply}
                />
              </bk-form-item>
            )}

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
                  {this.$t('保存')}
                </bk-button>
                <bk-button
                  class='cancel-btn'
                  onClick={this.handleCancel}
                >
                  {this.$t('取消')}
                </bk-button>
              </bk-form-item>
            )}
          </bk-form>
        )}
      </div>
    );
  }
}
