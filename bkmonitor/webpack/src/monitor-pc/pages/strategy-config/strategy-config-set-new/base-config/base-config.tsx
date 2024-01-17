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

/* eslint-disable camelcase */
import { Component, Emit, Prop, PropSync, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import Schema from 'async-validator';

import { strategyLabelList } from '../../../../../monitor-api/modules/strategies';
import { transformDataKey } from '../../../../../monitor-common/utils/utils';
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
  bizId: string | number;
  scenarioList: IScenarioItem[];
  scenarioReadonly: boolean;
  readonly?: boolean;
}
export interface IBaseConfig {
  bk_biz_id: string | number;
  scenario: string;
  name: string;
  labels: string[];
  isEnabled: boolean;
  priority: number | null | string;
}
@Component
export default class BaseInfo extends tsc<IBaseConfigProps> {
  @PropSync('data', { type: Object, required: true }) baseConfig: IBaseConfig;
  @Prop({ type: Array, required: true }) bizList: any;
  @Prop({ type: [String, Number], required: true }) bizId: string | number;
  @Prop({ type: Array, default: () => [] }) scenarioList: IScenarioItem[];
  @Prop({ type: Boolean, default: false }) scenarioReadonly: boolean;
  @Prop({ type: Boolean, default: false }) readonly: boolean;

  @Ref('strategyName') strategyNameEl;
  @Ref('strategyPriority') strategyPriorityEl;

  labelTreeData = [];

  errorsMsg = {
    name: '',
    priority: ''
  };

  created() {
    this.getLabelListApi();
  }

  handleLabelsChange(v) {
    this.baseConfig.labels = [v];
    this.handleBaseConfigChange();
  }

  getLabelListApi() {
    const params = {
      bk_biz_id: this.$store.getters.bizId,
      strategy_id: 0
    };
    return strategyLabelList(params).then(res => {
      const data = transformDataKey(res);
      const globalData = [
        ...data.global,
        ...data.globalParentNodes.map(item => ({ id: item.labelId, labelName: item.labelName }))
      ];
      const customData = [
        ...data.custom,
        ...data.customParentNodes.map(item => ({ id: item.labelId, labelName: item.labelName }))
      ];
      this.labelTreeData = [
        {
          group: 'global',
          groupName: this.$t('全局标签'),
          children: labelListToTreeData(globalData)
        },
        {
          group: 'custom',
          groupName: this.$t('自定义标签'),
          children: labelListToTreeData(customData)
        }
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
            }
          }
        ]
      };
      const validator = new Schema(descriptor);
      validator.validate({ name: this.baseConfig.name, priority: this.baseConfig.priority }, {}, (errors, fields) => {
        if (!errors) {
          this.errorsMsg = { name: '', priority: '' };
          resolve(null);
        } else {
          this.errorsMsg = { name: '', priority: '' };
          errors.forEach(item => {
            this.errorsMsg[item.field] = item.message;
          });
          // eslint-disable-next-line no-restricted-syntax
          for (const field in fields as Object) {
            // 按顺序给依次给表单 input 聚焦。（仅执行一次）
            const methodMap = {
              name: () => this.handleFocusStrategyName(),
              priority: () => this.handleFocusStrategyPriority()
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
      priority: ''
    };
  }

  handleBaseConfigPriorityInput(value) {
    this.errorsMsg.priority = value < 0 || value > 10000 ? this.$tc('优先级应为 0 - 10000 之间的整数') : '';
  }

  render() {
    return (
      <div class='base-config'>
        <CommonItem
          isWrap={true}
          title={this.$t('所属')}
          isRequired={true}
        >
          <bk-select
            value={this.bizId}
            searchable
            clearable={false}
            readonly={this.bizId > 0}
            class='base-config-select simplicity-select'
            behavior='simplicity'
            on-change={this.handleBaseConfigChange}
          >
            {this.bizList.map(item => (
              <bk-option
                key={item.id}
                id={item.id}
                name={item.text}
              ></bk-option>
            ))}
          </bk-select>
        </CommonItem>
        <CommonItem
          isWrap={true}
          title={this.$t('监控对象')}
          isRequired={false}
        >
          <bk-select
            behavior='simplicity'
            class='base-config-select simplicity-select'
            v-model={this.baseConfig.scenario}
            clearable={false}
            readonly={this.scenarioReadonly}
            on-change={this.handleBaseConfigChange}
          >
            {this.scenarioList.map((group, index) => (
              <bk-option-group
                name={group.name}
                key={index}
              >
                {group.children.map(option => (
                  <bk-option
                    key={option.id}
                    id={option.id}
                    name={option.name}
                  ></bk-option>
                ))}
              </bk-option-group>
            ))}
          </bk-select>
        </CommonItem>

        <CommonItem
          isWrap
          title={this.$t('策略名称')}
          isRequired={true}
        >
          <ErrorMsg
            message={this.errorsMsg.name}
            style='width: 100%;'
          >
            <bk-input
              behavior='simplicity'
              class='base-config-input simplicity-input'
              ref='strategyName'
              v-model={this.baseConfig.name}
              maxlength={128}
              minlength={1}
              readonly={this.readonly}
              on-input={() => (this.errorsMsg.name = '')}
              on-change={this.handleBaseConfigChange}
            />
          </ErrorMsg>
        </CommonItem>
        <CommonItem
          isWrap
          title={this.$t('优先级')}
          tips={this.$t('数值越大，优先级越高，完全相同的一条数据检测到异常时以优先级高的策略为主。')}
        >
          <ErrorMsg
            message={this.errorsMsg.priority}
            style='width: 100%;'
          >
            <bk-input
              behavior='simplicity'
              class='base-config-input simplicity-input'
              ref='strategyPriority'
              v-model={this.baseConfig.priority}
              type='number'
              max={10000}
              min={0}
              maxlength={5}
              minlength={1}
              readonly={this.readonly}
              on-input={v => this.handleBaseConfigPriorityInput(v)}
              on-change={this.handleBaseConfigChange}
            />
          </ErrorMsg>
        </CommonItem>

        <CommonItem
          title={this.$t('标签')}
          desc={this.$tc('(输入并回车即可创建新标签。可使用“/”创建多级分类，如：主机/系统告警)')}
        >
          {this.readonly && !this?.baseConfig?.labels?.length ? (
            <div style='padding-left: 3px;'>--</div>
          ) : (
            <MultiLabelSelect
              style='width: 100%;'
              mode='select'
              behavior='simplicity'
              readonly={this.readonly}
              checked-node={this.baseConfig.labels}
              tree-data={this.labelTreeData}
              on-checkedChange={v => (this.baseConfig.labels = v)}
            ></MultiLabelSelect>
          )}
        </CommonItem>
        <CommonItem
          is-switch={true}
          title={this.$t('是否启用')}
        >
          <bk-switcher
            disabled={this.readonly}
            behavior='simplicity'
            theme='primary'
            size='small'
            v-model={this.baseConfig.isEnabled}
            change={this.handleBaseConfigChange}
          />
        </CommonItem>
      </div>
    );
  }
}
