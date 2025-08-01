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
import { Component, Emit, Prop, PropSync, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { skipToDocsLink } from 'monitor-common/utils/docs';
import bus from 'monitor-common/utils/event-bus';
import { deepClone } from 'monitor-common/utils/utils';

import TimePickerMultiple, {
  type IProps as ITimeRangeMultipleProps,
} from '../../../../components/time-picker-multiple/time-picker-multiple';
import { HANDLE_SHOW_SETTING } from '../../../nav-tools';
import { isRecoveryDisable, isStatusSetterNoData } from '../../common';
import StrategyTemplatePreview from '../../strategy-config-set/strategy-template-preview/strategy-template-preview.vue';
import StrategyVariateList from '../../strategy-config-set/strategy-variate-list/strategy-variate-list.vue';
// import CommonItem from '../components/common-form-item.vue'
import CommonItem from '../components/common-form-item';
import VerifyItem from '../components/verify-item';
import { levelList } from '../type';

import type { IOptionsItem } from '../../../calendar/types';
import type { EditModeType, ICommonItem, MetricDetail } from '../typings/index';

import './judging-condition.scss';

export const DEFAULT_TIME_RANGES: ITimeRangeMultipleProps['value'] = [['00:00', '23:59']]; // 默认的生效时间段
export enum RecoveryConfigStatusSetter {
  RECOVERY = 'recovery',
  RECOVERY_NODATA = 'recovery-nodata',
}
export interface IJudgingData {
  noDataConfig: {
    continuous: number;
    dimensions: unknown[];
    isEnabled: boolean;
    level: number;
  };
  noticeTemplate: {
    anomalyTemplate: string;
    previewTemplate: boolean;
    triggerList: unknown[];
    variateList: unknown[];
    variateListShow: boolean;
  };
  recoveryConfig: {
    checkWindow: number;
    statusSetter: RecoveryConfigStatusSetter;
  };
  triggerConfig: {
    calendars: string[];
    checkType: string;
    checkWindow: number;
    count: number;
    timeRanges: ITimeRangeMultipleProps['value'];
  };
}
interface Idata {
  calendarList: IOptionsItem[];
  data: IJudgingData;
  editMode?: EditModeType;
  isAlert?: boolean; // 是否为关联告警
  isDetailMode?: boolean;
  isFta?: boolean;
  judgeTimeRange?: string[]; // 关联告警时只显示生效时间段
  legalDimensionList?: ICommonItem[];
  metricData: MetricDetail[];
  scenario: string;
}
interface IEvent {
  onChange?: IJudgingData;
  onNoDataChange?: boolean;
  onTimeChange?: string[]; // 生效时间段
  onValidatorErr?: () => void; // 校验不通过派出
}

@Component({
  name: 'JudgingCondition',
})
export default class JudgingCondition extends tsc<Idata, IEvent> {
  @PropSync('data', {
    required: true,
    default: () => ({
      triggerConfig: {
        // 触发条件
        count: 0,
        checkWindow: 0,
        checkType: 'total',
        timeRanges: DEFAULT_TIME_RANGES,
        calendars: [],
      },
      recoveryConfig: {
        // 恢复条件
        checkWindow: 0,
        statusSetter: RecoveryConfigStatusSetter.RECOVERY,
      },
      noDataConfig: {
        // 无数据告警
        continuous: 0,
        isEnabled: true,
        dimensions: [],
        level: 2,
      },
      noticeTemplate: {
        anomalyTemplate: '',
        triggerList: [],
        variateList: [],
        previewTemplate: false,
        variateListShow: false,
      },
    }),
  })
  localData: IJudgingData;
  @Prop({ type: String, default: 'os' }) scenario: string;
  @Prop({ type: Array, default: () => [] }) metricData: MetricDetail[];
  @Prop({ type: Boolean, default: false }) isDetailMode: boolean;
  @Prop({ type: Boolean, default: false }) isFta: boolean;
  @Prop({ type: Boolean, default: false }) isAlert: boolean; // 是否为关联告警
  @Prop({ type: Array, default: () => ['00:00:00', '23:59:59'] }) judgeTimeRange: string[];
  @Prop({ type: Array, default: () => [] }) calendarList: IOptionsItem[]; // 日历列表可选项
  @Prop({ type: String, default: 'Edit' }) editMode: EditModeType;
  @Ref() calendarSelectRef: any;

  aggList = [];
  errMsg = {
    triggerConfig: '',
    recoveryConfig: '',
    noDataConfig: '',
    timeRanges: '',
  };
  levelList = levelList;

  timeRange = ['00:00:00', '23:59:59'];

  curDimensions = [];

  /* 手动输入的维度(promql模式专用) */
  promqlDimensions = [];

  get aggDimensionCollection() {
    return this.metricData.reduce((acc, cur) => {
      cur.agg_dimension.forEach(dim => {
        if (!acc.includes(dim)) {
          acc.push(dim);
        }
      });
      return acc;
    }, []);
  }

  get optionalDimensions() {
    return this.metricData
      .map(item => item.dimensions.filter(dim => dim.is_dimension || dim.is_dimension === undefined))
      .sort((a, b) => b.length - a.length)[0]
      ?.filter(dim => this.aggDimensionCollection.includes(dim.id));
  }

  get isNoDataDisable() {
    if (this.editMode === 'Source') {
      return false;
    }
    return !(this.metricData.length && ['time_series', 'log'].includes(this.metricData[0]?.data_type_label));
  }

  get dimensionsOfSeries() {
    return this.$store.state['strategy-config'].dimensionsOfSeries.map(id => ({
      id,
      name: id,
    }));
  }

  @Watch('optionalDimensions')
  handleOptionalDimensions(v) {
    if (v?.length) {
      this.curDimensions = deepClone(v);
      this.localData.noDataConfig.dimensions =
        deepClone(this.localData.noDataConfig.dimensions.filter(dim => this.aggDimensionCollection.includes(dim))) ||
        [];
    } else {
      this.curDimensions = [];
      this.localData.noDataConfig.dimensions = [];
    }
  }

  created() {
    this.aggList = [
      {
        id: 'total',
        name: this.$t('累计'),
      },
    ];
  }

  @Watch('judgeTimeRange')
  handleJudgeTimeRange(v: string[]) {
    this.timeRange = v;
  }

  @Emit('timeChange')
  handleTimeChange() {
    return this.timeRange;
  }

  @Emit('change')
  emitValueChange() {
    this.clearError();
    return this.localData;
  }
  @Emit('noDataChange')
  emitNoDataChange(val: boolean): boolean {
    return val;
  }
  handleTemplateChange(v) {
    const { noticeTemplate } = this.localData;
    noticeTemplate.anomalyTemplate = v || '';
  }
  // 点击模板预览触发
  handlePreviewDetail() {
    const { noticeTemplate } = this.localData;
    if (noticeTemplate.anomalyTemplate.length) {
      noticeTemplate.previewTemplate = true;
    }
  }
  // 点击变量列表
  handleVariateList() {
    const { noticeTemplate } = this.localData;
    noticeTemplate.variateListShow = true;
  }
  handleGoto(name) {
    skipToDocsLink(name);
  }
  // 恢复条件 checkbox 值改变后回调
  handleRecoveryConfigChange(v) {
    this.localData.recoveryConfig.statusSetter = v
      ? RecoveryConfigStatusSetter.RECOVERY_NODATA
      : RecoveryConfigStatusSetter.RECOVERY;
    this.emitValueChange();
  }

  /**
   * @description: 校验
   * @param {*}
   * @return {*}
   */
  validator() {
    const { triggerConfig, recoveryConfig, noDataConfig } = this.localData;
    if (
      triggerConfig.checkWindow < 1 ||
      triggerConfig.count < 1 ||
      `${triggerConfig.checkWindow}`.match(/\./) ||
      `${triggerConfig.count}`.match(/\./) ||
      +triggerConfig.checkWindow < +triggerConfig.count
    ) {
      this.errMsg.triggerConfig = `${this.$t('触发周期数 >=1 且 >= 检测数')}`;
      this.$emit('validatorErr');
      return false;
    }
    if (recoveryConfig.checkWindow < 1 || `${recoveryConfig.checkWindow}`.match(/\./)) {
      this.errMsg.recoveryConfig = `${this.$t('恢复条件参数不得小于1')}`;
      this.$emit('validatorErr');
      return false;
    }
    if (
      noDataConfig.isEnabled &&
      (noDataConfig.continuous < 5 || noDataConfig.continuous > 60 || `${noDataConfig.continuous}`.match(/\./))
    ) {
      this.errMsg.noDataConfig = `${this.$t('周期数不得小于5且不得大于60')}`;
      this.$emit('validatorErr');
      return false;
    }
    if (!triggerConfig.timeRanges.length) {
      this.errMsg.timeRanges = `${this.$t('选择生效时间段')}`;
      this.$emit('validatorErr');
      return false;
    }
    this.errMsg.timeRanges = '';

    return true;
  }
  /**
   * @description: 清空校验异常
   * @param {*}
   * @return {*}
   */
  clearError() {
    this.errMsg = {
      triggerConfig: '',
      recoveryConfig: '',
      noDataConfig: '',
      timeRanges: '',
    };
  }

  // 维度搜索可用id或者name搜索
  handleSearchDim(searchValue: string) {
    this.curDimensions = this.optionalDimensions.filter(
      item => String(item.id).includes(searchValue) || String(item.name).includes(searchValue)
    );
  }

  /** 打开日历服务 */
  handleShowCalendar() {
    this.calendarSelectRef?.close?.();
    bus.$emit(HANDLE_SHOW_SETTING, 'calendar');
  }

  handleClearTimeRangeError(val: ITimeRangeMultipleProps['value']) {
    if (val.length) {
      this.errMsg.timeRanges = '';
    }
  }

  /**
   * @description: 只读模式
   * @param {*}
   * @return {*}
   */
  getReadonlyComponent() {
    const { noticeTemplate, triggerConfig, recoveryConfig, noDataConfig } = this.localData;
    return (
      <div class='alarm-condition alarm-condition-readonly'>
        <CommonItem
          title={this.$t('触发条件')}
          show-semicolon
        >
          <i18n
            class='i18n-path'
            path='在{0}个周期内{1}满足{2}次检测算法，触发告警通知'
          >
            <span class='bold-span'>{triggerConfig.checkWindow}</span>
            <span class='bold-span'>{this.aggList.find(item => triggerConfig.checkType === item.id).name}</span>
            <span class='bold-span'>{triggerConfig.count}</span>
          </i18n>
        </CommonItem>
        <CommonItem
          title={this.$t('恢复条件')}
          show-semicolon
        >
          <i18n
            class='i18n-path'
            path='连续{0}个周期内不满足触发条件{1}'
          >
            <span class='bold-span'>{recoveryConfig.checkWindow}</span>
            {!isRecoveryDisable(this.metricData) && isStatusSetterNoData(this.localData.recoveryConfig.statusSetter) ? (
              <span class='bold-span'>{this.$t('或无数据')}</span>
            ) : null}
          </i18n>
        </CommonItem>
        <CommonItem
          title={this.$t('无数据')}
          show-semicolon
        >
          <span class='judging-nodata'>
            <bk-switcher
              class='small-switch'
              v-model={this.localData.noDataConfig.isEnabled}
              disabled={true}
              size='small'
              theme='primary'
            />
            <i18n
              class='i18n-path'
              path='当数据连续丢失{0}个周期时，触发告警通知'
            >
              <span class='bold-span'>{noDataConfig.continuous}</span>
            </i18n>
            {this.localData.noDataConfig.dimensions?.length ? (
              <i18n
                class='judging-dismension'
                path='基于以下维度{0}进行判断'
              >
                <span class='bold-span'>{this.localData.noDataConfig.dimensions.join(',')}</span>
              </i18n>
            ) : undefined}
            <span class='i18n-path'>
              ，{this.$t('告警级别')}
              <span class='bold-span'>
                {this.levelList.find(item => this.localData.noDataConfig.level === item.id).name}
              </span>
            </span>
          </span>
        </CommonItem>
        <CommonItem
          class='time-range'
          title={this.$t('生效时间段')}
          show-semicolon
        >
          <bk-time-picker
            class='time-input'
            v-model={this.timeRange}
            allowCrossDay={true}
            behavior='simplicity'
            clearable={false}
            disabled={this.isDetailMode}
            type='timerange'
            on-change={() => this.handleTimeChange()}
          />
        </CommonItem>
        <StrategyTemplatePreview
          dialogShow={noticeTemplate.previewTemplate}
          scenario={this.scenario}
          template={noticeTemplate.anomalyTemplate}
          {...{ on: { 'update:dialogShow': val => (noticeTemplate.previewTemplate = val) } }}
        />
      </div>
    );
  }

  /**
   * @description: 编辑模式
   * @param {*}
   * @return {*}
   */
  getNormalComponent() {
    const { noticeTemplate } = this.localData;
    return (
      <div class='alarm-condition'>
        <CommonItem
          title={this.$t('触发条件')}
          show-semicolon
        >
          <VerifyItem errorMsg={this.errMsg.triggerConfig}>
            <i18n
              class='i18n-path'
              path='在{0}个周期内{1}满足{2}次检测算法，触发告警通知'
            >
              <bk-input
                class='small-input'
                v-model={this.localData.triggerConfig.checkWindow}
                behavior='simplicity'
                size='small'
                type='number'
                on-change={this.emitValueChange}
              />
              {this.$t('累计')}
              <bk-input
                class='small-input'
                v-model={this.localData.triggerConfig.count}
                behavior='simplicity'
                size='small'
                type='number'
                on-change={this.emitValueChange}
              />
            </i18n>
          </VerifyItem>
        </CommonItem>

        <CommonItem
          title={this.$t('恢复条件')}
          show-semicolon
        >
          <VerifyItem errorMsg={this.errMsg.recoveryConfig}>
            <div class='judging-recovery-config'>
              <i18n
                class='i18n-path'
                path='连续{0}个周期内不满足触发条件{1}'
              >
                <bk-input
                  class='small-input'
                  v-model={this.localData.recoveryConfig.checkWindow}
                  behavior='simplicity'
                  size='small'
                  type='number'
                  on-change={this.emitValueChange}
                />
                {!isRecoveryDisable(this.metricData) ? (
                  <bk-checkbox
                    value={isStatusSetterNoData(this.localData.recoveryConfig.statusSetter)}
                    onChange={this.handleRecoveryConfigChange}
                  >
                    {this.$t('或无数据')}
                  </bk-checkbox>
                ) : null}
              </i18n>
            </div>
          </VerifyItem>
        </CommonItem>
        <CommonItem
          title={this.$t('无数据')}
          show-semicolon
        >
          <VerifyItem errorMsg={this.errMsg.noDataConfig}>
            <span class='judging-nodata'>
              <i18n
                class='i18n-path flex-wrap'
                path={
                  Array.isArray(this.localData.noDataConfig.dimensions) || this.editMode === 'Source'
                    ? '{0}当数据连续丢失{1}个周期时，触发告警通知基于以下维度{2}进行判断，告警级别{3}'
                    : '{0}当数据连续丢失{1}个周期时，触发告警通知，告警级别{2}'
                }
              >
                <bk-switcher
                  class='small-switch'
                  v-model={this.localData.noDataConfig.isEnabled}
                  v-bk-tooltips={{
                    content: this.$t('只有监控指标及日志关键字可配置无数据'),
                    placements: ['top'],
                    disabled: !this.isNoDataDisable,
                  }}
                  disabled={this.isNoDataDisable}
                  size='small'
                  theme='primary'
                  onChange={this.emitNoDataChange}
                />
                <bk-input
                  class='small-input'
                  v-model={this.localData.noDataConfig.continuous}
                  v-bk-tooltips={
                    !this.localData.noDataConfig.isEnabled
                      ? { content: this.$t('先打开无数据功能'), showOnInit: false, placements: ['top'] }
                      : { disabled: true }
                  }
                  behavior='simplicity'
                  disabled={!this.localData.noDataConfig.isEnabled}
                  max={60}
                  min={5}
                  size='small'
                  type='number'
                  on-change={this.emitValueChange}
                />
                {(() => {
                  if (this.editMode === 'Source') {
                    return (
                      <bk-tag-input
                        class='small-select'
                        v-model={this.promqlDimensions}
                        v-bk-tooltips={
                          !this.localData.noDataConfig.isEnabled
                            ? { content: this.$t('先打开无数据功能'), showOnInit: false, placements: ['top'] }
                            : { disabled: true }
                        }
                        allow-create={true}
                        disabled={!this.localData.noDataConfig.isEnabled}
                        has-delete-icon={true}
                        list={this.dimensionsOfSeries}
                        placeholder={this.$t('输入')}
                        trigger={'focus'}
                      />
                    );
                  }
                  return Array.isArray(this.localData.noDataConfig.dimensions) ? (
                    <bk-select
                      class='small-select'
                      v-model={this.localData.noDataConfig.dimensions}
                      v-bk-tooltips={
                        !this.localData.noDataConfig.isEnabled
                          ? { content: this.$t('先打开无数据功能'), showOnInit: false, placements: ['top'] }
                          : {
                              content: this.localData.noDataConfig.dimensions.join('; '),
                              trigger: 'mouseenter',
                              zIndex: 9999,
                              boundary: document.body,
                              allowHTML: false,
                            }
                      }
                      behavior='simplicity'
                      clearable={false}
                      disabled={!this.localData.noDataConfig.isEnabled}
                      multiple={true}
                      popover-min-width={140}
                      remote-method={this.handleSearchDim}
                      size={'small'}
                      searchable
                      show-select-all
                      on-change={this.emitValueChange}
                    >
                      {this.curDimensions.map(option => (
                        <bk-option
                          id={option.id}
                          key={option.id}
                          v-bk-tooltips={{
                            content: option.id,
                            placement: 'right',
                            zIndex: 9999,
                            boundary: document.body,
                            appendTo: document.body,
                            allowHTML: false,
                          }}
                          name={option.name}
                        />
                      ))}
                    </bk-select>
                  ) : undefined;
                })()}
                <bk-select
                  class='small-select'
                  v-model={this.localData.noDataConfig.level}
                  v-bk-tooltips={
                    !this.localData.noDataConfig.isEnabled
                      ? { content: this.$t('先打开无数据功能'), showOnInit: false, placements: ['top'] }
                      : { disabled: true }
                  }
                  behavior='simplicity'
                  clearable={false}
                  disabled={!this.localData.noDataConfig.isEnabled}
                  popover-min-width={80}
                  size={'small'}
                  on-change={this.emitValueChange}
                >
                  {this.levelList.map(option => (
                    <bk-option
                      id={option.id}
                      key={option.id}
                      name={option.name}
                    />
                  ))}
                </bk-select>
              </i18n>
            </span>
          </VerifyItem>
        </CommonItem>
        <CommonItem
          class='time-range'
          title={this.$t('生效时间段')}
          show-semicolon
        >
          <VerifyItem
            class='time-range-row'
            errorMsg={this.errMsg.timeRanges}
          >
            <TimePickerMultiple
              v-model={this.localData.triggerConfig.timeRanges}
              onChange={this.handleClearTimeRangeError}
            />
          </VerifyItem>
          <span
            class='calendar-title'
            v-bk-tooltips={this.$t('默认是所有时间都生效，日历中添加的为不生效时间段')}
          >
            {this.$t('关联日历')}
          </span>
          {this.calendarSelect(this.$tc('选择'))}
        </CommonItem>
        <StrategyTemplatePreview
          dialogShow={noticeTemplate.previewTemplate}
          {...{ on: { 'update:dialogShow': val => (noticeTemplate.previewTemplate = val) } }}
          scenario={this.scenario}
          template={noticeTemplate.anomalyTemplate}
        />
        <StrategyVariateList
          dialogShow={noticeTemplate.variateListShow}
          {...{ on: { 'update:dialogShow': val => (noticeTemplate.variateListShow = val) } }}
          variate-list={noticeTemplate.variateList}
        />
      </div>
    );
  }

  /**
   * 关联日历选择器
   * @returns vnode
   */
  calendarSelect(placeholder?: string) {
    return (
      <bk-select
        ref='calendarSelectRef'
        class='calendar-select simplicity-select'
        v-model={this.localData.triggerConfig.calendars}
        behavior='simplicity'
        ext-popover-cls='link-calendar-popover'
        placeholder={placeholder || this.$t('关联日历')}
        multiple
      >
        {this.calendarList.map(item => (
          <bk-option
            id={item.id}
            key={item.id + item.name}
            name={item.name}
          />
        ))}
        <div
          class='calendar-extension'
          slot='extension'
          onClick={this.handleShowCalendar}
        >
          {this.$t('前往日历服务')}
        </div>
      </bk-select>
    );
  }

  // 当关联告警时显示的内容
  getAlertComponent() {
    return (
      <div class='alarm-condition'>
        <CommonItem
          class='time-range'
          title={this.$t('生效时间段')}
          show-semicolon
        >
          <VerifyItem
            class='time-range-row'
            errorMsg={this.errMsg.timeRanges}
          >
            <TimePickerMultiple
              v-model={this.localData.triggerConfig.timeRanges}
              onChange={this.handleClearTimeRangeError}
            />
          </VerifyItem>
          {this.calendarSelect()}
        </CommonItem>
      </div>
    );
  }

  render() {
    return this.isAlert
      ? this.getAlertComponent()
      : this.isDetailMode
        ? this.getReadonlyComponent()
        : this.getNormalComponent();
  }
}
