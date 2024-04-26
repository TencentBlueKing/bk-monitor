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
/*
 * @Date: 2021-06-24 10:27:24
 * @LastEditTime: 2021-06-25 11:22:58
 * @Description: 策略基本信息
 */

import { Component, Emit, Prop, PropSync, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import Schema from 'async-validator';
import { strategyLabelList } from 'monitor-api/modules/strategies';
import { transformDataKey } from 'monitor-common/utils/utils';

import ErrorMsg from '../../../../components/error-msg/error-msg';
import MultiLabelSelect from '../../../../components/multi-label-select/multi-label-select';
import { labelListToTreeData } from '../../../../components/multi-label-select/utils';
import { ISpaceItem } from '../../../../types';
import CommonItem from '../components/common-item';
import { IScenarioItem } from '../typings/index';

import './base-config.scss';

interface IBaseConfigProps {
  data: IBaseConfig;
  bizList: ISpaceItem[];
  bizId: number | string;
  scenarioList: IScenarioItem[];
  scenarioReadonly: boolean;
  readonly?: boolean;
}
export interface IBaseConfig {
  bk_biz_id: number | string;
  scenario: string;
  name: string;
  labels: string[];
  isEnabled: boolean;
  priority: null | number | string;
}
@Component
export default class BaseInfo extends tsc<IBaseConfigProps> {
  @PropSync('data', { type: Object, required: true }) baseConfig: IBaseConfig;
  @Prop({ type: Array, required: true }) bizList: any;
  @Prop({ type: [String, Number], required: true }) bizId: number | string;
  @Prop({ type: Array, default: () => [] }) scenarioList: IScenarioItem[];
  @Prop({ type: Boolean, default: false }) scenarioReadonly: boolean;
  @Prop({ type: Boolean, default: false }) readonly: boolean;

  @Ref('strategyName') strategyNameEl;
  @Ref('strategyPriority') strategyPriorityEl;
  @Ref('strategyLabels') strategyLabelsEl;

  labelTreeData = [];

  errorsMsg = {
    name: '',
    priority: '',
    labels: '',
  };

  created() {
    this.getLabelListApi();
  }

  handleLabelsChange(v) {
    this.baseConfig.labels = v;
    this.errorsMsg.labels = v.some(item => item.length > 120) ? this.$tc('标签长度不能超过 120 字符') : '';
  }

  getLabelListApi() {
    const params = {
      bk_biz_id: this.$store.getters.bizId,
      strategy_id: 0,
    };
    return strategyLabelList(params).then(res => {
      const data = transformDataKey(res);
      const globalData = [
        ...data.global,
        ...data.globalParentNodes.map(item => ({ id: item.labelId, labelName: item.labelName })),
      ];
      const customData = [
        ...data.custom,
        ...data.customParentNodes.map(item => ({ id: item.labelId, labelName: item.labelName })),
      ];
      this.labelTreeData = [
        {
          group: 'global',
          groupName: this.$t('全局标签'),
          children: labelListToTreeData(globalData),
        },
        {
          group: 'custom',
          groupName: this.$t('自定义标签'),
          children: labelListToTreeData(customData),
        },
      ];
    });
  }

  @Emit('change')
  handleBaseConfigChange() {
    return this.baseConfig;
  }

  handleFocusStrategyName() {
    this.strategyNameEl.$refs.input.focus();
  }

  handleFocusStrategyPriority() {
    this.strategyPriorityEl.$refs.input.focus();
  }

  handleStrategyLabels() {
    this.strategyLabelsEl.focusInputer();
  }

  // 校验方法
  public validate(): Promise<any> {
    return new Promise((resolve, reject) => {
      const descriptor = {
        name: [{ required: true, message: this.$tc('必填项') }],
        priority: [
          {
            asyncValidator: (rule, value) => {
              return new Promise<void>((resolve, reject) => {
                if (value < 0 || value > 10000) {
                  reject(this.$t('优先级应为 0 - 10000 之间的整数'));
                } else {
                  resolve();
                }
              });
            },
          },
        ],
        labels: [
          {
            validator: (rule, value) => {
              return !value.some(item => item.length > 120);
            },
            message: this.$tc('标签长度不能超过 120 字符'),
          },
        ],
      };
      const validator = new Schema(descriptor);
      const { name, priority, labels } = this.baseConfig;
      validator.validate({ name, priority, labels }, {}, (errors, fields) => {
        if (!errors) {
          this.errorsMsg = { name: '', priority: '', labels: '' };
          resolve(null);
        } else {
          this.errorsMsg = { name: '', priority: '', labels: '' };
          errors.forEach(item => {
            this.errorsMsg[item.field] = item.message;
          });

          for (const field in fields) {
            // 按顺序给依次给表单 input 聚焦。（仅执行一次）
            const methodMap = {
              name: () => this.handleFocusStrategyName(),
              priority: () => this.handleFocusStrategyPriority(),
              labels: () => this.handleStrategyLabels(),
            };
            methodMap[field]();
            break;
          }
          reject({ errors, fields });
        }
      });
    });
  }
  // 清除校验
  public clearErrorMsg() {
    this.errorsMsg = {
      name: '',
      priority: '',
      labels: '',
    };
  }

  handleBaseConfigPriorityInput(value) {
    this.errorsMsg.priority = value < 0 || value > 10000 ? this.$tc('优先级应为 0 - 10000 之间的整数') : '';
  }

  render() {
    return (
      <div class='base-config'>
        <CommonItem
          isRequired={true}
          isWrap={true}
          title={this.$t('所属')}
        >
          <bk-select
            class='base-config-select simplicity-select'
            behavior='simplicity'
            clearable={false}
            readonly={Number(this.bizId) > 0}
            value={this.bizId}
            searchable
            on-change={this.handleBaseConfigChange}
          >
            {this.bizList.map(item => (
              <bk-option
                id={item.id}
                key={item.id}
                name={item.text}
              ></bk-option>
            ))}
          </bk-select>
        </CommonItem>
        <CommonItem
          isRequired={false}
          isWrap={true}
          title={this.$t('监控对象')}
        >
          <bk-select
            class='base-config-select simplicity-select'
            v-model={this.baseConfig.scenario}
            behavior='simplicity'
            clearable={false}
            readonly={this.scenarioReadonly}
            on-change={this.handleBaseConfigChange}
          >
            {this.scenarioList.map((group, index) => (
              <bk-option-group
                key={index}
                name={group.name}
              >
                {group.children.map(option => (
                  <bk-option
                    id={option.id}
                    key={option.id}
                    name={option.name}
                  ></bk-option>
                ))}
              </bk-option-group>
            ))}
          </bk-select>
        </CommonItem>

        <CommonItem
          isRequired={true}
          title={this.$t('策略名称')}
          isWrap
        >
          <ErrorMsg
            style='width: 100%;'
            message={this.errorsMsg.name}
          >
            <bk-input
              ref='strategyName'
              class='base-config-input simplicity-input'
              v-model={this.baseConfig.name}
              behavior='simplicity'
              maxlength={128}
              minlength={1}
              readonly={this.readonly}
              on-change={this.handleBaseConfigChange}
              on-input={() => (this.errorsMsg.name = '')}
            />
          </ErrorMsg>
        </CommonItem>
        <CommonItem
          tips={this.$t('数值越大，优先级越高，完全相同的一条数据检测到异常时以优先级高的策略为主。')}
          title={this.$t('优先级')}
          isWrap
        >
          <ErrorMsg
            style='width: 100%;'
            message={this.errorsMsg.priority}
          >
            <bk-input
              ref='strategyPriority'
              class='base-config-input simplicity-input'
              v-model={this.baseConfig.priority}
              behavior='simplicity'
              max={10000}
              maxlength={5}
              min={0}
              minlength={1}
              readonly={this.readonly}
              type='number'
              on-change={this.handleBaseConfigChange}
              on-input={v => this.handleBaseConfigPriorityInput(v)}
            />
          </ErrorMsg>
        </CommonItem>

        <CommonItem
          desc={this.$tc('(输入并回车即可创建新标签。可使用“/”创建多级分类，如：主机/系统告警)')}
          title={this.$t('标签')}
        >
          {this.readonly && !this?.baseConfig?.labels?.length ? (
            <div style='padding-left: 3px;'>--</div>
          ) : (
            <ErrorMsg
              style='width: 100%;'
              message={this.errorsMsg.labels}
            >
              <MultiLabelSelect
                ref='strategyLabels'
                style='width: 100%;'
                behavior='simplicity'
                checked-node={this.baseConfig.labels}
                mode='select'
                readonly={this.readonly}
                tree-data={this.labelTreeData}
                on-checkedChange={this.handleLabelsChange}
              ></MultiLabelSelect>
            </ErrorMsg>
          )}
        </CommonItem>
        <CommonItem
          is-switch={true}
          title={this.$t('是否启用')}
        >
          <bk-switcher
            v-model={this.baseConfig.isEnabled}
            behavior='simplicity'
            change={this.handleBaseConfigChange}
            disabled={this.readonly}
            size='small'
            theme='primary'
          />
        </CommonItem>
      </div>
    );
  }
}
