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
export default class NewSeries extends tsc<NewSeriesProps, NewSeriesEvent> {
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
    /** 告警阈值 */
    threshold: 0,
    /** 时间 */
    date: 1,
    /** 时间单位 */
    unit: 'd',
  };

  get localData(): IDetectionTypeRuleData {
    const unit = this.unitList.find(item => item.id === this.formData.unit);
    const detectRange = unit.seconds * this.formData.date;
    return {
      type: DetectionRuleTypeEnum.NewSeries,
      level: this.formData.level,
      config: {
        // 生效延迟(冷启动宽限)跟随检测窗口：宽限须盖住 detect_range,否则首轮存量维度学不全会误报。
        // 不再写死 86400(原值对 <1天 窗白等、对 >1天 窗欠学误报)。
        effective_delay: detectRange,
        max_series: 100000,
        detect_range: detectRange,
        threshold: Number(this.formData.threshold),
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

  /** 维度名拼接，用于检测说明文案 */
  get dimensionNames(): string {
    return this.dimensionList
      .map(item => item.name)
      .filter(Boolean)
      .join('、');
  }

  /** 检测周期文案（数值 + 单位名），用于检测说明文案 */
  get windowText(): string {
    const unit = this.unitList.find(item => item.id === this.formData.unit);
    return `${this.formData.date}${unit?.name ?? ''}`;
  }

  rules = {
    level: [{ required: true, message: this.$t('必填项'), trigger: 'change' }],
    threshold: [
      {
        validator: this.checkThreshold,
        message: this.$t('阈值不能为空且必须为整数'),
        trigger: 'change',
      },
    ],
    date: [
      {
        validator: this.checkDate,
        message: this.$t('时间不能为空且必须大于0'),
        trigger: 'change',
      },
    ],
  };

  get unitList() {
    return [
      { id: 'd', name: this.$t('天'), seconds: 86400 },
      { id: 'h', name: this.$t('小时'), seconds: 3600 },
      { id: 'm', name: this.$t('分钟'), seconds: 60 },
    ];
  }

  get otherSelectLevel() {
    return this.otherSelectRuleData.reduce((pre, cur) => {
      if (cur.type === DetectionRuleTypeEnum.NewSeries) pre.push(cur.level);
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
      const detectRange = Number(this.data.config?.detect_range) || 0;
      // 选能整除 detect_range 的最大单位；取不到时（detect_range 小于最小单位 / 非整除，多见于 AsCode 导入）
      // 兜底到最小单位，date 至少为 1，确保编辑与只读详情渲染都不抛错（原实现 find 返回 undefined 会崩溃）。
      const unit =
        this.unitList.find(item => detectRange >= item.seconds && detectRange % item.seconds === 0) ??
        this.unitList[this.unitList.length - 1];
      this.formData = {
        level: this.data.level,
        threshold: this.data.config?.threshold ?? 0,
        date: Math.max(1, Math.round(detectRange / unit.seconds)),
        unit: unit.id,
      };
    } else {
      this.initData();
    }
  }

  /** 初始化数据 */
  initData() {
    // 防御：正常情况下添加入口已限制最多三条（各占一级），这里兜底避免 find 返回 undefined 时崩溃。
    const firstEnabled = this.levelList.find(item => !item.disabled);
    this.formData.level = firstEnabled ? firstEnabled.id : 1;
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

  checkThreshold(value) {
    return value !== null && value !== undefined && String(value).trim() !== '' && Number.isInteger(Number(value));
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
            label={this.$t('告警阈值')}
            property='threshold'
            required
          >
            <div class='threshold-condition'>
              <span class='threshold-operator'>{this.$t('大于')}</span>
              <bk-input
                class='inline-input input-arrow threshold-input'
                v-model={this.formData.threshold}
                behavior='simplicity'
                precision={0}
                readonly={this.readonly}
                show-controls={false}
                type='number'
                onChange={this.emitLocalData}
              />
            </div>
            <i18n
              class='threshold-rule'
              path='触发规则：仅当对应数据值大于{0}时触发告警'
            >
              <span>{this.formData.threshold}</span>
            </i18n>
          </bk-form-item>
          <bk-form-item
            error-display-type='normal'
            label={this.$t('检测周期')}
            property='date'
            required
          >
            <div class='date-interval'>
              <bk-input
                class='inline-input input-arrow date-input'
                v-model={this.formData.date}
                behavior='simplicity'
                min={1}
                precision={0}
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
              title={this.$t(
                '每次检测任务出现新的维度值 {dimensions} 时，都会倒推过去 {window} 内是否出现过相同维度值，如果没有则告警，出现过则不告警。',
                { dimensions: this.dimensionNames || this.$t('维度组合'), window: this.windowText }
              )}
              type='info'
            />
          </bk-form-item>
        </bk-form>
      </div>
    );
  }
}
