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
import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { DATE_UNIT_SECONDS_STEPS } from 'monitor-common/utils';

import { type IDetectionTypeRuleData, type MetricDetail, DetectionRuleTypeEnum } from '../../../typings';

import './new-series.scss';

interface NewSeriesEvent {
  onDataChange: IDetectionTypeRuleData;
}

interface NewSeriesProps {
  data?: IDetectionTypeRuleData;
  metricData: MetricDetail[];
  otherSelectRuleData?: IDetectionTypeRuleData[];
  readonly?: boolean;
}

@Component
export default class NewDimension extends tsc<NewSeriesProps, NewSeriesEvent> {
  @Prop({ type: Object }) data: IDetectionTypeRuleData;
  @Prop({ type: Boolean, default: false }) readonly: boolean;
  /** 其他已选择的算法数据 */
  @Prop({ type: Array, default: () => [] }) otherSelectRuleData: IDetectionTypeRuleData[];
  /** 指标数据 */
  @Prop({ type: Array, default: () => [] }) metricData: MetricDetail[];

  @Ref() formRef;

  formData = {
    /** 告警级别 */
    level: 1,
    /** 时间 */
    date: 1,
    /** 时间单位 */
    unit: 'd',
  };

  get localData(): IDetectionTypeRuleData {
    const unit = this.unitList.find(item => item.id === this.formData.unit);
    return {
      type: DetectionRuleTypeEnum.NewSeries,
      level: this.formData.level,
      config: {
        effective_delay: 86400,
        max_series: 100000,
        detect_range: unit.seconds * this.formData.date,
      },
    };
  }

  get dimensionList() {
    return (
      this.metricData?.[0]?.agg_dimension.map(id => ({
        id,
        name: this.metricData[0].dimensions.find(dimension => dimension.id === id)?.name,
      })) || []
    );
  }

  rules = {
    level: [{ required: true, message: this.$t('必填项'), trigger: 'change' }],
    date: [
      {
        validator: this.checkDate,
        message: this.$t('时间不能为空且必须大于0'),
        trigger: 'change',
      },
    ],
  };

  get unitList() {
    return DATE_UNIT_SECONDS_STEPS.filter(item => item.id !== 's');
  }

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
    for (const item of list) {
      item.disabled = this.otherSelectLevel.includes(item.id);
    }
    return list;
  }

  created() {
    if (this.data) {
      const unit = this.unitList.find(unit => this.data.config.detect_range >= unit.seconds);

      this.formData = {
        level: this.data.level,
        date: this.data.config.detect_range / unit.seconds,
        unit: unit.id,
      };
    } else {
      this.initData();
    }
  }

  /** 初始化数据 */
  initData() {
    this.formData.level = this.levelList.find(item => !item.disabled).id;
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

  checkDate(value) {
    return value && value > 0;
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
      <div class='new-series-wrap'>
        <bk-form
          ref='formRef'
          {...{ props: { model: this.formData } }}
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
              v-model={this.formData.level}
              clearable={false}
              ext-popover-cls='level-select-popover'
              prefix-icon={`icon-monitor ${this.levelList[this.formData.level - 1].icon}`}
              readonly={this.readonly}
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
            label={this.$t('判断间隔')}
            property='date'
            required
          >
            <div class='date-interval'>
              <bk-input
                class='inline-input input-arrow date-input'
                v-model={this.formData.date}
                behavior='simplicity'
                min={1}
                readonly={this.readonly}
                show-controls={false}
                type='number'
                onChange={this.emitLocalData}
              />
              <bk-select
                class='inline-select unit-select'
                v-model={this.formData.unit}
                clearable={false}
                readonly={this.readonly}
                onChange={this.emitLocalData}
              >
                {this.unitList.map(item => (
                  <bk-option
                    id={item.id}
                    key={item.id}
                    name={item.name}
                  />
                ))}
              </bk-select>
            </div>
            <bk-alert
              class='dimension-alert'
              type='info'
            >
              <i18n
                slot='title'
                path='根据所选维度（组合）{0}，{1}内出现新的维度时，将产生告警'
              >
                <div class='dimension-list'>
                  {this.dimensionList.map(item => (
                    <div
                      key={item.id}
                      class='dimension-item'
                    >
                      {item.name}
                    </div>
                  ))}
                </div>
                <span>
                  <span class='count'>{this.formData.date}</span>
                  <span class='unit'>{this.unitList.find(item => item.id === this.formData.unit).name}</span>
                </span>
              </i18n>
            </bk-alert>
          </bk-form-item>
        </bk-form>
      </div>
    );
  }
}
