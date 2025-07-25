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
import { Component, Emit, InjectReactive, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { THRESHOLD_METHOD_LIST } from '../../../../../../constant/constant';
import { type IDetectionTypeRuleData, DetectionRuleTypeEnum } from '../../../typings';
import ThresholdSelect, { type IItem } from './threshold-select';

import './threshold.scss';

interface ThresholdEvents {
  onDataChange: IDetectionTypeRuleData;
}

interface ThresholdProps {
  data?: IDetectionTypeRuleData;
  methodList?: IItem[];
  otherSelectRuleData?: IDetectionTypeRuleData[];
  readonly?: boolean;
  unit?: string;
}

@Component({})
export default class Threshold extends tsc<ThresholdProps, ThresholdEvents> {
  @Prop({ type: Object }) data: IDetectionTypeRuleData;
  @Prop({ type: Boolean, default: false }) readonly: boolean;
  /** 其他已选择的算法数据 */
  @Prop({ type: Array, default: () => [] }) otherSelectRuleData: IDetectionTypeRuleData[];
  /** 方法列表 */
  @Prop({ type: Array, default: () => [...THRESHOLD_METHOD_LIST] }) methodList: IItem[];
  /** 单位 */
  @Prop({ type: String, default: '' }) unit: string;

  @InjectReactive('yAxisNeedUnit') needShowUnit;

  @Ref() formRef;

  localData: IDetectionTypeRuleData = {
    type: DetectionRuleTypeEnum.Threshold,
    level: 1,
    config: [
      [
        {
          method: 'gte',
          threshold: 0,
        },
      ],
    ],
  };

  rules = {
    level: [{ required: true, message: this.$t('必填项'), trigger: 'change' }],
    config: [
      {
        validator: this.checkConfig,
        message: this.$t('检测算法填写不完整，请完善后添加'),
        trigger: 'change',
      },
    ],
  };

  get otherSelectLevel() {
    return this.otherSelectRuleData.reduce((pre, cur) => {
      if (cur.type === DetectionRuleTypeEnum.Threshold) pre.push(cur.level);
      return pre;
    }, []);
  }

  /** 根据其他已选择静态阈值算法的级别，来确定本次可选的级别 */
  get levelList() {
    const list = [
      { id: 1, name: window.i18n.t('致命'), disabled: false, icon: 'icon-danger' },
      { id: 2, name: window.i18n.t('预警'), disabled: false, icon: 'icon-mind-fill' },
      { id: 3, name: window.i18n.t('提醒'), disabled: false, icon: 'icon-tips' },
    ];
    list.forEach(item => {
      item.disabled = this.otherSelectLevel.includes(item.id);
    });
    return list;
  }

  created() {
    if (this.data) {
      this.localData = this.data;
    } else {
      this.initData();
    }
  }

  /** 初始化数据 */
  initData() {
    this.localData.level = this.levelList.find(item => !item.disabled).id;
    this.emitLocalData();
  }

  validate() {
    return new Promise((res, rej) => {
      this.formRef
        .validate()
        .then(validator => res(validator))
        .catch(validator => rej(validator));
    });
  }

  clearError() {
    this.formRef.clearError();
  }

  checkConfig(value) {
    return value.length > 0 && value[0].every(item => item.threshold !== '');
  }

  handleThresholdSelectChange(val) {
    this.localData.config = val;
    this.emitLocalData();
  }

  @Emit('dataChange')
  emitLocalData() {
    return this.localData;
  }

  render() {
    return (
      <div class='threshold-wrap'>
        <bk-form
          ref='formRef'
          {...{ props: { model: this.localData } }}
          label-width={126}
          rules={this.rules}
        >
          <bk-form-item
            label={this.$t('告警级别')}
            property='level'
            required
          >
            <bk-select
              ext-cls='level-select'
              v-model={this.localData.level}
              clearable={false}
              ext-popover-cls='level-select-popover'
              prefix-icon={`icon-monitor ${this.levelList[this.localData.level - 1].icon}`}
              onChange={this.emitLocalData}
            >
              {this.levelList.map(level => (
                <bk-option
                  id={level.id}
                  key={level.id}
                  v-bk-tooltips={{
                    content: this.$t('已有相同算法,设置为{name}级别', { name: level.name }),
                    disabled: !level.disabled,
                    allowHTML: false,
                  }}
                  disabled={level.disabled}
                  name={level.name}
                >
                  <i class={`icon-monitor ${level.icon}`} />
                  <span class='name'>{level.name}</span>
                </bk-option>
              ))}
            </bk-select>
          </bk-form-item>

          <bk-form-item
            error-display-type='normal'
            label={this.$t('告警条件')}
            property='config'
            required
          >
            <ThresholdSelect
              method-list={this.methodList}
              readonly={this.readonly}
              unit={this.needShowUnit ? this.unit : ''}
              value={this.localData.config}
              onChange={this.handleThresholdSelectChange}
            />
          </bk-form-item>
        </bk-form>
      </div>
    );
  }
}
