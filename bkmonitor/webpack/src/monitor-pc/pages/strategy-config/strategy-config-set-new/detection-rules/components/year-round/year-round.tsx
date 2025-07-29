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

import { deepClone, isPostiveInt } from 'monitor-common/utils';

import { SIMPLE_METHOD_LIST } from '../../../../../../constant/constant';
import { type IDetectionTypeRuleData, DetectionRuleTypeEnum } from '../../../typings';

import './year-round.scss';

interface YearRoundEvents {
  onDataChange: IDetectionTypeRuleData;
}

interface YearRoundProps {
  data?: IDetectionTypeRuleData;
  isRealtime?: boolean;
  otherSelectRuleData?: IDetectionTypeRuleData[];
  readonly?: boolean;
}

// 算法类型对应的数据模型
const typeModelMap = {
  [DetectionRuleTypeEnum.SimpleYearRound]: {
    floor: '',
    ceil: '',
  },
  [DetectionRuleTypeEnum.AdvancedYearRound]: {
    floor: '',
    floor_interval: '',
    ceil: '',
    ceil_interval: '',
    fetch_type: 'avg',
  },
  [DetectionRuleTypeEnum.YearRoundAmplitude]: {
    ratio: 0,
    shock: 0,
    days: 1,
    method: 'gte',
  },
  [DetectionRuleTypeEnum.YearRoundRange]: {
    ratio: 0,
    shock: 0,
    days: 1,
    method: 'gte',
  },
};

@Component({})
export default class YearRound extends tsc<YearRoundProps, YearRoundEvents> {
  /** 回填数据 */
  @Prop({ type: Object }) data: IDetectionTypeRuleData;
  /** 其他已选择的算法数据 */
  @Prop({ type: Array, default: () => [] }) otherSelectRuleData: IDetectionTypeRuleData[];
  /** 是否只读 */
  @Prop({ type: Boolean, default: false }) readonly: boolean;
  /** 是否是实时选项 */
  @Prop({ type: Boolean, default: false }) isRealtime: boolean;
  /** 表单实例 */
  @Ref() formRef;
  /** 本地数据 */
  localData: IDetectionTypeRuleData = {
    type: DetectionRuleTypeEnum.SimpleYearRound,
    level: 1,
    config: {
      floor: '',
      ceil: '',
    },
  };

  errorMsg = '';

  rules = {
    type: [{ required: true, message: this.$t('必填项'), trigger: 'change' }],
    level: [{ required: true, message: this.$t('必填项'), trigger: 'change' }],
    config: [
      {
        validator: this.checkConfig,
        message: this.showMsg,
        trigger: 'change',
      },
    ],
  };

  /** 简易模板 */
  simpleTemplate = [
    { value: 'ceil', text: this.$t('升') },
    { value: 'floor', text: this.$t('降') },
  ];

  /** 高级模板 */
  advancedTemplate = [
    { value1: 'ceil_interval', value2: 'ceil', value3: 'fetch_type', text: window.i18n.t('升') },
    { value1: 'floor_interval', value2: 'floor', value3: 'fetch_type', text: window.i18n.t('降') },
  ];

  // 在 同比策略 的 高级算法类型 下，记录当前在 告警条件 里是输入还是选择 均值/瞬间值 （因为在选择时不需要参与表单校验）
  inputOrSelectInAdvancedMode: '' | 'input' | 'select' = '';

  /**
   * 算法类型和已选择的告警级别的映射表
   * {
   *  算法类型： 已选择的告警级别
   * }
   */
  get selectTypeOrLevelMap() {
    const map = {
      [DetectionRuleTypeEnum.SimpleYearRound]: [],
      [DetectionRuleTypeEnum.AdvancedYearRound]: [],
      [DetectionRuleTypeEnum.YearRoundAmplitude]: [],
      [DetectionRuleTypeEnum.YearRoundRange]: [],
    };
    this.otherSelectRuleData.forEach(item => {
      if (map[item.type]) map[item.type].push(item.level);
    });
    return map;
  }

  /** 根据当前选择的算法类型来确定算法级别的可选项 */
  get levelList() {
    const list = [
      { id: 1, name: window.i18n.t('致命'), disabled: false, icon: 'icon-danger' },
      { id: 2, name: window.i18n.t('预警'), disabled: false, icon: 'icon-mind-fill' },
      { id: 3, name: window.i18n.t('提醒'), disabled: false, icon: 'icon-tips' },
    ];
    list.forEach(item => {
      item.disabled = this.selectTypeOrLevelMap[this.localData.type]?.includes(item.id);
    });
    return list;
  }

  /** 根据当前选择的算法级别来确定算法类型的可选项 */
  get typeList() {
    const list = [
      { id: DetectionRuleTypeEnum.SimpleYearRound, name: window.i18n.t('简易'), disabled: false },
      { id: DetectionRuleTypeEnum.AdvancedYearRound, name: window.i18n.t('高级'), disabled: false },
      { id: DetectionRuleTypeEnum.YearRoundAmplitude, name: window.i18n.t('振幅'), disabled: false },
      { id: DetectionRuleTypeEnum.YearRoundRange, name: window.i18n.t('区间'), disabled: false },
    ];
    list.forEach(item => {
      item.disabled = this.selectTypeOrLevelMap[item.id]?.includes(this.localData.level);
    });
    return list;
  }

  get getSimpleMethodList() {
    return SIMPLE_METHOD_LIST;
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
    // 初始化：可以选择的算法类型和告警级别
    const select = Object.entries(this.selectTypeOrLevelMap).find(item => item[1].length < 3);
    this.localData.type = select[0] as DetectionRuleTypeEnum;
    this.localData.level = this.levelList.find(item => !item.disabled).id;
    this.handleTypeChange();
  }

  /** 切换算法类型 */
  handleTypeChange() {
    this.localData.config = deepClone(typeModelMap[this.localData.type]);
    this.formRef?.clearError();
    this.emitLocalData();
  }

  showMsg() {
    return this.errorMsg;
  }

  /**
   * @description 校验算法数据格式
   * @param value 当前表单填写的值
   * @returns 是否校验成功
   */
  checkConfig(value) {
    if (this.isRealtime) {
      this.errorMsg = this.$tc('当前实时的查询不支持该检测算法，请删除');
      return false;
    }

    switch (this.localData.type) {
      case DetectionRuleTypeEnum.SimpleYearRound:
        return this.checkSimple(value);
      case DetectionRuleTypeEnum.AdvancedYearRound:
        return this.checkAdvanced(value);
      case DetectionRuleTypeEnum.YearRoundAmplitude:
      case DetectionRuleTypeEnum.YearRoundRange:
        return this.checkAmplitude(value);
      default:
        return true;
    }
  }

  /**
   * 同比简易算法校验
   * @param value 表单值
   * @returns 是否校验成功
   */
  checkSimple(value) {
    const { ceil, floor } = value;
    if (ceil !== '' && ceil >= 0 && floor === '') return true;
    if (floor !== '' && floor >= 0 && ceil === '') return true;
    if (floor !== '' && ceil !== '' && ceil >= 0 && floor >= 0) return true;
    this.errorMsg = this.$tc('检测算法填写不完整，请完善后添加');
    return false;
  }

  /**
   * 同比高级算法校验
   * @param value 表单值
   * @returns 是否校验成功
   */
  checkAdvanced(value) {
    const { ceil, floor, ceil_interval: ceilInterval, floor_interval: floorInterval } = value;
    if (!ceilInterval && !ceil && isPostiveInt(floorInterval) && floor !== '' && floor >= 0) return true;
    if (!floorInterval && !floor && isPostiveInt(ceilInterval) && ceil !== '' && ceil >= 0) return true;
    if (
      isPostiveInt(floorInterval) &&
      floor !== '' &&
      floor >= 0 &&
      isPostiveInt(ceilInterval) &&
      ceil !== '' &&
      ceil >= 0
    )
      return true;
    // 说明当前是在选择 均值/瞬间值 。
    if (this.inputOrSelectInAdvancedMode === 'select') return true;
    this.errorMsg = this.$tc('检测算法填写不完整，请完善后添加');
    return false;
  }

  /**
   * 同比振幅,同比区间算法校验
   * @param value 表单值
   * @returns 是否校验成功
   */
  checkAmplitude(value) {
    const { days, ratio, shock } = value;
    if (days >= 1 && ratio !== '' && shock !== '') return { isSuccess: true, msg: '' };
    this.errorMsg = this.$tc('检测算法填写不完整，请完善后添加');
    return false;
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

  @Emit('dataChange')
  emitLocalData() {
    return this.localData;
  }

  render() {
    return (
      <div class='year-round-wrap'>
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
              behavior='simplicity'
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
            label={this.$t('算法类型')}
            property='type'
            required
          >
            <bk-radio-group
              class='type-radio'
              v-model={this.localData.type}
              onChange={this.handleTypeChange}
            >
              {this.typeList.map(type => (
                <bk-radio
                  v-bk-tooltips={{
                    content: this.$t('已有相同算法,设置为{name}级别', {
                      name: this.levelList[this.localData.level - 1].name,
                    }),
                    disabled: !type.disabled,
                    allowHTML: false,
                  }}
                  disabled={type.disabled}
                  value={type.id}
                >
                  {type.name}
                </bk-radio>
              ))}
            </bk-radio-group>
          </bk-form-item>
          <bk-form-item
            error-display-type='normal'
            label={this.$t('告警条件')}
            property='config'
            required
          >
            {
              // 同比策略(简易)
              this.localData.type === DetectionRuleTypeEnum.SimpleYearRound && (
                <div
                  key={`${this.localData.type}-${this.localData.level}`}
                  class='year-round-condition-list'
                >
                  {this.simpleTemplate.map(item => (
                    <div class='year-round-condition-list-item'>
                      <i18n
                        class='i18n-path'
                        path='当前值较上周同一时刻{0}时触发告警'
                      >
                        <bk-input
                          style='margin: 0 10px;'
                          class='input-align-center inline-input input-arrow'
                          v-model={this.localData.config[item.value]}
                          behavior='simplicity'
                          min={0}
                          placeholder={this.$t('输入数字')}
                          readonly={this.readonly}
                          show-controls={false}
                          size='small'
                          type='number'
                          onChange={this.emitLocalData}
                        >
                          <template slot='prepend'>
                            <div class={['left-text', { 'left-text-red': item.value === 'floor' }]}> {item.text} </div>
                          </template>
                          <template slot='append'>
                            <div class='right-unit'>%</div>
                          </template>
                        </bk-input>
                      </i18n>
                    </div>
                  ))}
                </div>
              )
            }
            {
              // 同比策略(高级)
              this.localData.type === DetectionRuleTypeEnum.AdvancedYearRound && (
                <div
                  key={`${this.localData.type}-${this.localData.level}`}
                  class='year-round-condition-list'
                >
                  {this.advancedTemplate.map(item => (
                    <div class='year-round-condition-list-item'>
                      <i18n
                        class='i18n-path'
                        path='较前{0}天同一时刻绝对值的{1}{2}时触发告警'
                      >
                        <bk-input
                          style='width: 86px; margin: 0 10px;'
                          class='input-align-center inline-input'
                          v-model_number={this.localData.config[item.value1]}
                          behavior='simplicity'
                          clearable={true}
                          min={1}
                          placeholder={this.$t('输入整数')}
                          precision={0}
                          readonly={this.readonly}
                          show-controls={false}
                          type='number'
                          onChange={() => {
                            this.inputOrSelectInAdvancedMode = 'input';
                            this.emitLocalData();
                          }}
                        />
                        <bk-select
                          style='width: 100px;'
                          ext-cls='timing-selector'
                          v-model={this.localData.config[item.value3]}
                          behavior='simplicity'
                          clearable={false}
                          size='small'
                          onChange={() => {
                            this.inputOrSelectInAdvancedMode = 'select';
                            this.emitLocalData();
                          }}
                        >
                          <bk-option
                            id='avg'
                            name={this.$t('均值')}
                          />
                          <bk-option
                            id='last'
                            name={this.$t('瞬间值')}
                          />
                        </bk-select>
                        <bk-input
                          style='margin: 0 10px;'
                          class='input-align-center inline-input input-arrow'
                          v-model={this.localData.config[item.value2]}
                          behavior='simplicity'
                          min={0}
                          placeholder={this.$t('输入数字')}
                          readonly={this.readonly}
                          show-controls={false}
                          // class={['number-input', { 'is-readonly': this.readonly }]}
                          type='number'
                          onChange={() => {
                            this.inputOrSelectInAdvancedMode = 'input';
                            this.emitLocalData();
                          }}
                        >
                          <template slot='prepend'>
                            <div class={['left-text', { 'left-text-red': item.value1.indexOf('floor') > -1 }]}>
                              {' '}
                              {item.text}{' '}
                            </div>
                          </template>
                          <template slot='append'>
                            <div class='right-unit'>%</div>
                          </template>
                        </bk-input>
                      </i18n>
                    </div>
                  ))}
                </div>
              )
            }
            {
              // 同比策略(振幅)
              this.localData.type === DetectionRuleTypeEnum.YearRoundAmplitude && (
                <div
                  key={`${this.localData.type}-${this.localData.level}`}
                  class='amplitude-wrap concise'
                >
                  <i18n
                    class='i18n-path'
                    path='(当前值 - 前一时刻值){0}过去{1}天内任意一天同时刻的 (差值 ×{2}+{3}) 时触发告警'
                  >
                    <bk-select
                      class='select-method'
                      v-model={this.localData.config.method}
                      clearable={false}
                      popover-min-width={50}
                      readonly={this.readonly}
                      onChange={this.emitLocalData}
                    >
                      {this.getSimpleMethodList.map(opt => (
                        <bk-option
                          id={opt.id}
                          key={opt.id}
                          name={opt.name}
                        />
                      ))}
                    </bk-select>
                    <bk-input
                      style='width: 78px'
                      class='input-align-center inline-input number-handle-input'
                      v-model={this.localData.config.days}
                      behavior='simplicity'
                      clearable={false}
                      min={1}
                      precision={0}
                      readonly={this.readonly}
                      type='number'
                      onChange={this.emitLocalData}
                    />
                    <bk-input
                      style='width: 72px'
                      class='input-align-center inline-input number-handle-input'
                      v-model={this.localData.config.ratio}
                      behavior='simplicity'
                      clearable={false}
                      readonly={this.readonly}
                      type='number'
                      onChange={this.emitLocalData}
                    />
                    <bk-input
                      style='width: 72px'
                      class='input-align-center inline-input number-handle-input'
                      v-model={this.localData.config.shock}
                      behavior='simplicity'
                      clearable={false}
                      readonly={this.readonly}
                      type='number'
                      onChange={this.emitLocalData}
                    />
                  </i18n>
                </div>
              )
            }
            {
              // 同比策略(区间)
              this.localData.type === DetectionRuleTypeEnum.YearRoundRange && (
                <div
                  key={`${this.localData.type}-${this.localData.level}`}
                  class='amplitude-wrap concise'
                >
                  <i18n
                    class='i18n-path'
                    path='当前值 {0} 过去{1}天内同时刻绝对值 ×{2}+{3}'
                  >
                    <bk-select
                      class='select-method'
                      v-model={this.localData.config.method}
                      clearable={false}
                      popover-min-width={50}
                      readonly={this.readonly}
                      onChange={this.emitLocalData}
                    >
                      {this.getSimpleMethodList.map(opt => (
                        <bk-option
                          id={opt.id}
                          key={opt.id}
                          name={opt.name}
                        />
                      ))}
                    </bk-select>
                    <bk-input
                      style='width: 78px'
                      class='input-align-center inline-input number-handle-input'
                      v-model={this.localData.config.days}
                      behavior='simplicity'
                      clearable={false}
                      min={1}
                      precision={0}
                      readonly={this.readonly}
                      type='number'
                      onChange={this.emitLocalData}
                    />
                    <bk-input
                      style='width: 72px'
                      class='input-align-center inline-input number-handle-input'
                      v-model={this.localData.config.ratio}
                      behavior='simplicity'
                      clearable={false}
                      min={1}
                      precision={0}
                      readonly={this.readonly}
                      type='number'
                      onChange={this.emitLocalData}
                    />
                    <bk-input
                      style='width: 72px'
                      class='input-align-center inline-input number-handle-input'
                      v-model={this.localData.config.shock}
                      behavior='simplicity'
                      clearable={false}
                      readonly={this.readonly}
                      type='number'
                      onChange={this.emitLocalData}
                    />
                  </i18n>
                </div>
              )
            }
          </bk-form-item>
        </bk-form>
      </div>
    );
  }
}
