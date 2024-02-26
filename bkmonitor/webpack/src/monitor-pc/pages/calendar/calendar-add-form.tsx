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
import { Component, Emit, Model, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import dayjs from 'dayjs';
import { editItem, saveItem } from 'monitor-api/modules/calendar';

import CalendarInfo, { IProps as CalendarInfoPrps } from './components/calendar-info/calendar-info';
import DaysSelect from './components/days-select/days-select';
import CalendarAddInput from './calendar-add-input';
import {
  EDelAndEditType,
  ERepeatKey,
  ERepeatTypeId,
  getTimezoneOffset,
  ICalendarTableItem,
  IOptionsItem,
  IRepeatConfig,
  repeatParamsMap,
  WORKING_DATE_LIST,
  Z_INDEX
} from './types';

import './calendar-add-form.scss';

interface IProps {
  value?: boolean;
  calendarList: IOptionsItem[];
  editData?: ICalendarTableItem;
}
interface IEvents {
  onShowChange: boolean;
  onUpdateList: void;
  onUpdateCalendarList: void;
}
// /** 自定义类型id */
// export enum ERepeatTypeId {
//   days = 'day', // 天
//   weeks = 'week', // 周
//   months = 'month' // 月
// }
/** 自定义重复选项 */
interface IRepeatTypeOption {
  id: ERepeatTypeId;
  name: string;
}
/** 自定义重复表单数据 */
interface IRepeatFormData {
  repeatType: ERepeatTypeId;
  repeatDays: Array<number>;
  repeatNum: number;
  endDate: string;
  endDateNoRepeat: boolean;
}
/** 表单数据 */
interface IAddFormData {
  title: string;
  calendar: number | string;
  timeZone: string;
  startDate: string | Date;
  startTime: string;
  isAllDay: boolean;
  endDate: string | Date;
  endTime: string;
  repeat: ERepeatKey;
}
/**
 * 日历服务新增事项表格
 */
@Component
export default class CalendarAddForm extends tsc<IProps, IEvents> {
  @Model('showChange', { type: Boolean, default: false }) value: IProps['value'];
  /** 日历列表 */
  @Prop({ type: Array, default: () => [] }) calendarList: IOptionsItem[];
  /** 编辑数据 */
  @Prop({ type: Object }) editData: ICalendarTableItem;
  /** 新增日历组件 */
  @Ref() calendarAddInputRef: any;
  @Ref() addFormRef: any;

  /** 新建表单loading */
  addLoading = false;

  /** 自定义重复loading */
  repeatLoading = false;

  /** 新增弹窗 */
  showAddForm = false;
  /** 自定义重复弹窗 */
  showRepeatForm = false;

  /** 时区可选项 */
  timeZoneOptions: IOptionsItem[] = [];

  /** 重复内置可选项 */
  repeatOptions: IOptionsItem[] = [
    {
      id: 'no-repeat',
      name: window.i18n.tc('不重复')
    },
    {
      id: 'every-day',
      name: window.i18n.tc('每天重复')
    },
    {
      id: 'every-working-day',
      name: window.i18n.tc('每个工作日重复')
    },
    {
      id: 'every-week',
      name: window.i18n.tc('每周重复')
    },
    {
      id: 'every-month',
      name: window.i18n.tc('每月重复')
    },
    {
      id: 'every-year',
      name: window.i18n.tc('每年重复')
    },
    {
      id: 'custom',
      disabled: true,
      name: window.i18n.tc('自定义')
    }
  ];

  /** 重复类型选项 */
  repeatTypeOptions: IRepeatTypeOption[] = [
    {
      id: ERepeatTypeId.days,
      name: window.i18n.t('每天重复').toString()
    },
    {
      id: ERepeatTypeId.weeks,
      name: window.i18n.t('每周重复').toString()
    },
    {
      id: ERepeatTypeId.months,
      name: window.i18n.t('每月重复').toString()
    },
    {
      id: ERepeatTypeId.years,
      name: window.i18n.t('每年重复').toString()
    }
  ];

  /** 新增表单校验规则 */
  addFormRules = {
    title: [{ required: true, message: this.$tc('必填项'), trigger: 'none' }],
    calendar: [{ required: true, message: this.$tc('必填项'), trigger: 'none' }]
  };

  /** 新增、编辑表单 */
  addFormData: IAddFormData = {
    title: '', // 事项
    calendar: '', // 归属日历
    timeZone: null, // 时区
    startDate: dayjs.tz().format('YYYY-MM-DD'), // 开始日期
    startTime: '00:00:00', // 开始时间
    isAllDay: false, // 是否全天
    endDate: dayjs.tz().format('YYYY-MM-DD'), // 结束日期
    endTime: '23:59:59', // 结束时间
    repeat: ERepeatKey.noRepeat // 重复
  };

  /** 自定义重复表单数据 */
  repeatFormData: IRepeatFormData = {
    repeatType: ERepeatTypeId.days, // 重复类型 天、周、月
    repeatNum: 1, // 重复x天、周、月
    repeatDays: [], // 重复的日期
    endDate: '', // 结束时间
    endDateNoRepeat: false // 结束时间永不重复
  };

  /** 删除提示弹窗 */
  infoConfig: CalendarInfoPrps = {
    value: false,
    infoTitle: window.i18n.tc('确定修改日程？'),
    infoDesc: window.i18n.tc('当前日程包含重复内容，仅修改该日程还是全部修改？'),
    okText: window.i18n.tc('仅修改该日程'),
    cancelText: window.i18n.tc('全部修改'),
    zIndex: Z_INDEX + 100
  };

  /** 重复评率翻译 */
  get repeatI8nPath() {
    const map: Record<ERepeatTypeId, string> = {
      [ERepeatTypeId.days]: '每 {0} 天',
      [ERepeatTypeId.weeks]: '每 {0} 周',
      [ERepeatTypeId.months]: '每 {0} 月',
      [ERepeatTypeId.years]: '每 {0} 年'
    };
    return map[this.repeatFormData.repeatType];
  }

  /**
   * 是否允许修改重复项目
   * 如果是修改单独项的话，他就会把这个变成一个不重复项且无法修改重复，你这边可以判断一下repeat是否是{},如果是并且存在parent_id那就不允许修改重复
   */
  get repeatDisabled() {
    return !this.editData?.repeat?.freq && !!this.editData?.parent_id;
  }

  created() {
    this.createTimeZoneList();
  }

  @Watch('value')
  showChange(val: boolean) {
    if (val) this.initFormData();
    /** 编辑 */
    if (val && !!this.editData) {
      this.handleEditData();
    }
  }

  @Emit('showChange')
  handleShowChange(val?: boolean) {
    if (!val) this.addFormRef?.clearError?.();
    return val ?? !this.value;
  }

  /** 更新外部事项列表数据 */
  @Emit('updateList')
  handleUpdateList() {}

  /** 更新日历列表数据 */
  @Emit('updateCalendarList')
  handleUpdateCalendarList() {}

  /**
   * 初始化表单数据
   */
  initFormData() {
    this.addFormData = {
      title: '', // 事项
      calendar: '', // 归属日历
      timeZone: getTimezoneOffset(), // 时区
      startDate: dayjs.tz().format('YYYY-MM-DD'), // 开始日期
      startTime: '09:00:00', // 开始时间
      isAllDay: false, // 是否全天
      endDate: dayjs.tz().format('YYYY-MM-DD'), // 结束日期
      endTime: '10:00:00', // 结束时间
      repeat: ERepeatKey.noRepeat // 重复
    };
    this.repeatFormData = {
      repeatType: ERepeatTypeId.days, // 重复类型 天、周、月
      repeatNum: 1, // 重复x天、周、月
      repeatDays: [], // 重复的日期
      endDate: '', // 结束时间
      endDateNoRepeat: false // 结束时间永不重复
    };
  }

  /** 创建时区可选项 */
  createTimeZoneList() {
    for (let i = 0; i <= 24; i++) {
      let timeZone = i;
      if (i > 12) timeZone -= 24;
      i < 24 &&
        this.timeZoneOptions.push({
          id: timeZone,
          name: `UTC ${timeZone >= 0 ? '+' : ''}${timeZone}`
        });
    }
  }

  /** 展示自定义重复表单 */
  handleShowRepeatForm() {
    this.showRepeatForm = true;
  }

  /**
   * 切换永不重复按钮状态
   */
  handleNoRepeatStatus() {
    this.repeatFormData.endDateNoRepeat = !this.repeatFormData.endDateNoRepeat;
    if (this.repeatFormData.endDateNoRepeat) {
      this.repeatFormData.endDate = '';
    } else {
      this.repeatFormData.endDate = dayjs.tz().format('YYYY-MM-DD 23:59:59');
    }
  }

  /**
   * 隐藏新增日历组件输入框
   * @param val 弹层显隐状态
   */
  handleHideCalendarInput(val: boolean) {
    if (!val) this.calendarAddInputRef.handleCancel();
  }

  /**
   * 切换冲突频率操作
   */
  handleFrequencyChange() {
    this.repeatFormData.repeatDays = [];
  }

  /** 确认提交 */
  handleAddConfirmProxy() {
    this.addLoading = true;
    this.addFormRef
      .validate()
      .then(async () => {
        if (!!this.editData) {
          if (this.editData.repeat.freq) {
            this.infoConfig.value = true;
            if (this.editData.is_first) {
              this.infoConfig.infoDesc = this.$tc('当前日程包含重复内容，仅修改该日程还是全部修改？');
              this.infoConfig.cancelText = this.$tc('全部修改');
            } else {
              this.infoConfig.infoDesc = this.$tc('当前日程包含重复内容，仅修改该日程还是修改所有将来日程？');
              this.infoConfig.cancelText = this.$tc('修改所有将来日程');
            }
          } else {
            await this.hanldeEditSubmit();
          }
        } else {
          await this.handleAddConfirm();
        }
        this.addLoading = false;
      })
      .catch(() => {
        this.addLoading = false;
      });
  }

  /**
   * 提交编辑
   */
  async hanldeEditSubmit(type: EDelAndEditType = EDelAndEditType.current) {
    const params = this.getSubmitParams(true);
    // 修改事项类型（所有事项均修改：0；仅修改当前项：1；修改当前项及未来事项均生效：2
    params.change_type = type;
    const res = await editItem(params).then(() => true);
    if (res) {
      this.handleUpdateList();
      this.infoConfig.value = false;
      this.handleShowChange(false);
    }
  }

  /**
   * 新增提交
   */
  async handleAddConfirm() {
    const params = this.getSubmitParams();
    const res = await saveItem(params)
      .then(() => true)
      .catch(() => false);
    if (res) {
      this.handleUpdateList();
      this.handleShowChange(false);
    }
  }

  /**
   * 获取请求参数
   */
  getSubmitParams(isEdit = false) {
    const { title, calendar, startDate, startTime, endDate, endTime, repeat } = this.addFormData;
    const params = {
      name: title,
      calendar_id: calendar,
      start_time: dayjs.tz(`${startDate} ${startTime}`).unix(),
      end_time: dayjs.tz(`${endDate} ${endTime}`).unix(),
      time_zone: getTimezoneOffset(),
      repeat: repeat === ERepeatKey.custom ? this.getCustomRepeat() : repeatParamsMap[repeat],
      // all_day: isAllDay,
      // repeat_type: repeat,
      change_type: undefined,
      id: undefined
    };
    if (isEdit) {
      params.change_type = null;
      params.id = this.editData.id;
    }
    return params;
  }

  /** 自定重复参数 */
  getCustomRepeat(): IRepeatConfig {
    const { repeatType, repeatNum, repeatDays, endDate, endDateNoRepeat } = this.repeatFormData;
    return {
      freq: repeatType,
      interval: repeatNum, // 间隔
      until: endDateNoRepeat ? null : dayjs.tz(endDate).unix(), // 结束日期
      every: repeatDays, // 区间
      exclude_date: [] // 排除事项日期
    };
  }

  /** 选择全天 */
  handleSelectedAllDay() {
    this.addFormData.endDate = this.addFormData.startDate;
    if (this.addFormData.isAllDay) {
      this.addFormData.startTime = '00:00:00';
      this.addFormData.endTime = '23:59:59';
    } else {
      this.addFormData.startTime = '09:00:00';
      this.addFormData.endTime = '10:00:00';
    }
  }

  /**
   * 回填编辑数据
   */
  handleEditData() {
    const { name, calendar_id, time_zone, start_time, end_time, repeat } = this.editData;
    const startDate = dayjs.tz(start_time * 1000);
    const endDate = dayjs.tz(end_time * 1000);
    const startDateStr = startDate.format('YYYY-MM-DD');
    const endDateStr = endDate.format('YYYY-MM-DD');
    const startTimeStr = startDate.format('HH:mm:ss');
    const endTimeStr = endDate.format('HH:mm:ss');
    /** 重复类型 */
    let repeatType = null;
    const { freq, interval, every, exclude_date, until } = repeat;
    this.repeatFormData = {
      repeatType: freq,
      repeatNum: interval,
      repeatDays: every,
      endDate: !!until ? dayjs.tz(until * 1000).format('YYYY-MM-DD HH:mm:ss') : '',
      endDateNoRepeat: !until
    };
    if (!freq) {
      // 不重复
      repeatType = ERepeatKey.noRepeat;
    } else if (interval === 1 && !exclude_date.length) {
      repeatType = ERepeatKey.custom; // 自定义
      if (freq === ERepeatTypeId.days) {
        // 每天重复
        !every.length && !until && (repeatType = ERepeatKey.everyDay);
      } else if (freq === ERepeatTypeId.weeks) {
        // 每周
        every.length === 1 && !until && (repeatType = ERepeatKey.everyWeek);
        // 每个工作日
        WORKING_DATE_LIST.every(item => every.includes(item)) && !until && (repeatType = ERepeatKey.everyWorkingDay);
      } else if (freq === ERepeatTypeId.months) {
        // 每月
        every.length === 1 && !until && (repeatType = ERepeatKey.everyMonth);
      } else if (freq === ERepeatTypeId.years) {
        // 每年
        every.length === 1 && !until && (repeatType = ERepeatKey.everyYear);
      }
    } else {
      repeatType = ERepeatKey.custom; // 自定义
    }
    this.addFormData = {
      title: name,
      calendar: calendar_id,
      timeZone: time_zone || getTimezoneOffset(),
      startDate: startDateStr,
      startTime: startTimeStr,
      endDate: endDateStr,
      endTime: endTimeStr,
      isAllDay: startDateStr === endDateStr && startTimeStr === '00:00:00' && endTimeStr === '23:59:59',
      repeat: repeatType
    };
  }

  handleConfirmCustomRepeat() {
    this.addFormData.repeat = ERepeatKey.custom;
    this.showRepeatForm = false;
  }

  /** 确认修改类型 */
  handleInfoConfirm() {
    this.hanldeEditSubmit(EDelAndEditType.current);
  }
  /** 批量修改类型 */
  handleInfoCancel() {
    this.hanldeEditSubmit(this.editData.is_first ? EDelAndEditType.all : EDelAndEditType.currentAndFuture);
  }

  render() {
    return (
      <bk-dialog
        title={this.$t(this.editData ? '编辑事项' : '新建事项')}
        z-index={Z_INDEX}
        width={640}
        header-position='left'
        ext-cls='add-calendar-dialog-wrap'
        value={this.value}
        loading={this.addLoading}
        mask-close={false}
        onCancel={() => this.handleShowChange(false)}
        onConfirm={this.handleAddConfirmProxy}
      >
        <bk-form
          {...{
            props: {
              model: this.addFormData,
              rules: this.addFormRules
            }
          }}
          ref='addFormRef'
          form-type='vertical'
        >
          <bk-form-item
            property='title'
            error-display-type='normal'
          >
            <bk-input
              placeholder={this.$t('输入不工作时间事项')}
              v-model={this.addFormData.title}
            ></bk-input>
            <div class='form-item-des'>{this.$t('此事项为不工作时间事项')}</div>
          </bk-form-item>
          <bk-form-item
            label={this.$t('归属日历')}
            property='calendar'
            error-display-type='normal'
          >
            <bk-select
              clearable={false}
              z-index={Z_INDEX + 10}
              v-model={this.addFormData.calendar}
              onToggle={this.handleHideCalendarInput}
            >
              {this.calendarList.map(opt => (
                <bk-option
                  key={opt.id}
                  id={opt.id}
                  name={opt.name}
                ></bk-option>
              ))}
              <div
                slot='extension'
                class='calendar-custom-add-btn-wrap'
              >
                <CalendarAddInput
                  ref='calendarAddInputRef'
                  onConfirm={this.handleUpdateCalendarList}
                >
                  <span class='calendar-custom-add-btn'>
                    <i class='icon-monitor icon-jia'></i>
                    <span class='custom-add-btn-text'>{this.$t('新建日历')}</span>
                  </span>
                </CalendarAddInput>
              </div>
            </bk-select>
          </bk-form-item>
          {/* <bk-form-item label={this.$t('选择时区')}>
            <bk-select z-index={Z_INDEX + 10} v-model={this.addFormData.timeZone} clearable={false}>
              {
                this.timeZoneOptions.map(opt => (
                  <bk-option id={opt.id} name={opt.name}></bk-option>
                ))
              }
            </bk-select>
          </bk-form-item> */}
          <bk-form-item label={this.$t('开始')}>
            <div class='form-start'>
              <bk-date-picker
                class='date-picker'
                clearable={false}
                format='yyyy-MM-dd'
                value={this.addFormData.startDate}
                onChange={val => (this.addFormData.startDate = val)}
              ></bk-date-picker>
              <bk-time-picker
                class='time-picker'
                clearable={false}
                v-model={this.addFormData.startTime}
              ></bk-time-picker>
              <bk-checkbox
                v-model={this.addFormData.isAllDay}
                class='all-day'
                onChange={this.handleSelectedAllDay}
              >
                {this.$t('全天')}
              </bk-checkbox>
            </div>
          </bk-form-item>
          <bk-form-item label={this.$t('结束')}>
            <div class='form-end'>
              <bk-date-picker
                class='date-picker'
                clearable={false}
                format='yyyy-MM-dd'
                value={this.addFormData.endDate}
                onChange={val => (this.addFormData.endDate = val)}
              ></bk-date-picker>
              <bk-time-picker
                class='time-picker'
                clearable={false}
                v-model={this.addFormData.endTime}
              ></bk-time-picker>
            </div>
          </bk-form-item>
          <bk-form-item label={this.$t('重复')}>
            <bk-select
              v-model={this.addFormData.repeat}
              z-index={Z_INDEX + 10}
              class='repeat-select'
              clearable={false}
              disabled={this.repeatDisabled}
              ext-popover-cls='repeat-select-popover'
            >
              {this.repeatOptions.map(opt => (
                <bk-option
                  id={opt.id}
                  name={opt.name}
                  key={opt.id}
                  disabled={opt.disabled}
                ></bk-option>
              ))}
              <div
                slot='extension'
                class='repeat-extension'
                onClick={this.handleShowRepeatForm}
              >
                {this.$t('自定义')}
              </div>
            </bk-select>
          </bk-form-item>
        </bk-form>
        {/* 自定义重复弹窗 */}
        <bk-dialog
          value={this.showRepeatForm}
          width={480}
          title={this.$t('自定义重复')}
          ext-cls='add-calendar-repeat-dialog-wrap'
          z-index={Z_INDEX + 20}
          header-position='left'
          loading={this.repeatLoading}
          mask-close={false}
          onCancel={() => (this.showRepeatForm = false)}
          onConfirm={this.handleConfirmCustomRepeat}
        >
          <bk-form form-type='vertical'>
            <bk-form-item label={this.$t('频率')}>
              <div class='repeat-frequency'>
                <bk-select
                  v-model={this.repeatFormData.repeatType}
                  z-index={Z_INDEX + 30}
                  clearable={false}
                  class='frequency-type-select'
                  onSelected={this.handleFrequencyChange}
                >
                  {this.repeatTypeOptions.map(opt => (
                    <bk-option
                      id={opt.id}
                      key={opt.id}
                      name={opt.name}
                    ></bk-option>
                  ))}
                </bk-select>
                <i18n
                  path={this.repeatI8nPath}
                  class='frequency-input-num-wrap'
                >
                  <bk-input
                    class='frequency-input-num'
                    min={1}
                    v-model={this.repeatFormData.repeatNum}
                    type='number'
                  ></bk-input>
                </i18n>
              </div>
            </bk-form-item>
            {[ERepeatTypeId.weeks, ERepeatTypeId.months, ERepeatTypeId.years].includes(
              this.repeatFormData.repeatType
            ) && (
              <bk-form-item label=''>
                <DaysSelect
                  v-model={this.repeatFormData.repeatDays}
                  mode={this.repeatFormData.repeatType}
                ></DaysSelect>
              </bk-form-item>
            )}
            <bk-form-item label={this.$t('结束日期')}>
              <bk-date-picker
                class='repeat-end-date'
                ext-popover-cls='repeat-end-date-popover'
                clearable={false}
                placeholder={this.$t('永不结束')}
                format='yyyy-MM-dd HH:mm:ss'
                value={this.repeatFormData.endDate}
                onChange={val => (this.repeatFormData.endDate = dayjs.tz(val).format('YYYY-MM-DD 23:59:59'))}
              >
                <div
                  slot='footer'
                  class='repeat-end-date-footer'
                >
                  <bk-button
                    size='small'
                    class={['no-repeat-btn', { active: this.repeatFormData.endDateNoRepeat }]}
                    onClick={this.handleNoRepeatStatus}
                  >
                    {this.$t('永不结束')}
                  </bk-button>
                </div>
              </bk-date-picker>
            </bk-form-item>
          </bk-form>
          <CalendarInfo
            v-model={this.infoConfig.value}
            infoDesc={this.infoConfig.infoDesc}
            infoTitle={this.infoConfig.infoTitle}
            okText={this.infoConfig.okText}
            cancelText={this.infoConfig.cancelText}
            zIndex={this.infoConfig.zIndex}
            onConfirm={this.handleInfoConfirm}
            onCancel={this.handleInfoCancel}
          ></CalendarInfo>
        </bk-dialog>
      </bk-dialog>
    );
  }
}
