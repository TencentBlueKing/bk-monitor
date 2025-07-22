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
import { type PropType, defineComponent, reactive, watch, shallowRef } from 'vue';
import { useI18n } from 'vue-i18n';

import { DatePicker, Radio, Select, TimePicker } from 'bkui-vue';
import dayjs from 'dayjs';

import { EShieldCycle, type INoticeDate } from '../typing';
import DayPicker from './day-picker';
import FormItem from './form-item';

import './scope-date-config.scss';

export default defineComponent({
  name: 'ScopeDateConfig',
  props: {
    value: {
      type: Object as PropType<INoticeDate>,
      default: () => null,
    },
    onChange: {
      type: Function as PropType<(v: INoticeDate) => void>,
      default: () => {},
    },
  },
  setup(props) {
    const { t } = useI18n();
    const datePick = {
      options: {
        disabledDate(date) {
          return date && (date.valueOf() < Date.now() - 8.64e7 || date.valueOf() > Date.now() + 8.64e7 * 181);
        },
      },
    };
    const shieldCycleList = [
      { label: t('单次'), value: 'single' },
      { label: t('每天'), value: 'day' },
      { label: t('每周'), value: 'week' },
      { label: t('每月'), value: 'month' },
    ];
    const weekList = [
      { name: t('星期一'), id: 1 },
      { name: t('星期二'), id: 2 },
      { name: t('星期三'), id: 3 },
      { name: t('星期四'), id: 4 },
      { name: t('星期五'), id: 5 },
      { name: t('星期六'), id: 6 },
      { name: t('星期日'), id: 7 },
    ];
    /* 屏蔽时间范围 */
    const noticeDate = reactive<INoticeDate>({
      shieldCycle: EShieldCycle.single,
      dateRange: [],
      [EShieldCycle.single]: {
        list: [],
        range: [],
      },
      [EShieldCycle.day]: {
        list: [],
        range: ['00:00:00', '23:59:59'],
      },
      [EShieldCycle.week]: {
        list: [],
        range: ['00:00:00', '23:59:59'],
      },
      [EShieldCycle.month]: {
        list: [],
        range: ['00:00:00', '23:59:59'],
      },
    });
    /* 是否正在操作时分秒，用于处理组件库datepicker第一个时间默认为23:59:59的bug */
    const isHandleHMSTime = shallowRef(false);

    const errMsg = reactive({
      singleRange: '',
      dayRange: '',
      dateRange: '',
      weekList: '',
      weekRange: '',
      monthList: '',
      monthRange: '',
    });

    watch(
      () => props.value.key,
      key => {
        if (key === noticeDate?.key) {
          return;
        }
        Object.keys(props.value).forEach(key => {
          noticeDate[key] = props.value[key];
        });
      },
      {
        immediate: true,
      }
    );

    function handleChangeShieldCycle(v: EShieldCycle) {
      isHandleHMSTime.value = false;
      noticeDate.shieldCycle = v;
      clearErrMsg();
      handleChange();
    }
    function clearErrMsg() {
      Object.keys(errMsg).forEach(key => {
        errMsg[key] = '';
      });
    }
    /**
     * @description 日期校验
     * @param val
     */
    function validateDateRange(val) {
      return !!val.join('');
    }
    /**
     * @description 校验
     */
    function validate() {
      const dateRangevalidate = () => {
        if (!validateDateRange(noticeDate.dateRange)) {
          errMsg.dateRange = t('选择日期范围');
        }
        return true;
      };
      if (noticeDate.shieldCycle === EShieldCycle.single) {
        if (!validateDateRange(noticeDate.single.range)) {
          errMsg.singleRange = t('选择时间范围');
        }
      } else if (noticeDate.shieldCycle === EShieldCycle.day) {
        if (!validateDateRange(noticeDate.day.range)) {
          errMsg.dayRange = t('选择时间范围');
        }
        dateRangevalidate();
      } else if (noticeDate.shieldCycle === EShieldCycle.week) {
        if (!validateDateRange(noticeDate.week.list)) {
          errMsg.weekList = t('选择每星期范围');
        }
        if (!validateDateRange(noticeDate.week.range)) {
          errMsg.weekRange = t('选择时间范围');
        }
        dateRangevalidate();
      } else if (noticeDate.shieldCycle === EShieldCycle.month) {
        if (!validateDateRange(noticeDate.month.list)) {
          errMsg.monthList = t('选择每月时间范围');
        }
        if (!validateDateRange(noticeDate.month.range)) {
          errMsg.monthRange = t('选择时间范围');
        }
        dateRangevalidate();
      }
      return !Object.keys(errMsg).some(key => !!errMsg[key]);
    }
    /**
     * @description 数据更新
     * @param v
     */
    function handleSingleRangeChange(v) {
      // noticeDate.single.range = v;
      noticeDate.single.range = isHandleHMSTime.value ? v : [dayjs.tz(v[0]).format('YYYY-MM-DD 00:00:00'), v[1]];
      isHandleHMSTime.value = false;
      errMsg.singleRange = '';
      handleChange();
    }
    function handleDayRangeChange(v) {
      noticeDate.day.range = v;
      errMsg.dayRange = '';
      handleChange();
    }
    function handleDateRangeChange(v) {
      // noticeDate.dateRange = v;
      noticeDate.dateRange = isHandleHMSTime.value ? v : [dayjs.tz(v[0]).format('YYYY-MM-DD 00:00:00'), v[1]];
      isHandleHMSTime.value = false;
      errMsg.dateRange = '';
      handleChange();
    }
    function handleWeekListChange(v) {
      noticeDate.week.list = v;
      errMsg.weekList = '';
      handleChange();
    }
    function handleWeekRangeChange(v) {
      noticeDate.week.range = v;
      errMsg.weekRange = '';
      handleChange();
    }
    function handleMonthListChange(v) {
      noticeDate.month.list = v;
      errMsg.monthList = '';
      handleChange();
    }
    function handleMonthRangeChange(v) {
      noticeDate.month.range = v;
      errMsg.monthRange = '';
      handleChange();
    }
    function handleChange() {
      props.onChange(noticeDate);
    }

    // 判断第一次点击/滑动 是否在操作时分秒
    function handleFirstTime(v) {
      // 如果点击的是日期，V是一个时间字符串；如果是滑动时分秒，V是一个数组
      isHandleHMSTime.value = Array.isArray(v);
    }

    // input输入修改时间 逻辑同操作时分秒
    function handleInputTime(e: KeyboardEvent) {
      const isValid = /^[0-9:-]$/.test(e.key);
      if (isValid) {
        isHandleHMSTime.value = true;
      }
    }

    return {
      validate,
      noticeDate,
      errMsg,
      t,
      handleChangeShieldCycle,
      shieldCycleList,
      datePick,
      weekList,
      handleSingleRangeChange,
      handleDayRangeChange,
      handleWeekListChange,
      handleWeekRangeChange,
      handleMonthListChange,
      handleMonthRangeChange,
      handleDateRangeChange,
      handleFirstTime,
      handleInputTime,
    };
  },
  render() {
    return (
      <div class='alarm-shield-config-scope-date-config-component'>
        <FormItem
          class='mt24'
          label={this.t('屏蔽周期')}
          require={true}
        >
          <div class='mt8'>
            <Radio.Group
              modelValue={this.noticeDate.shieldCycle}
              size='small'
              onUpdate:modelValue={v => this.handleChangeShieldCycle(v)}
            >
              {this.shieldCycleList.map(item => (
                <Radio label={item.value}>{item.label}</Radio>
              ))}
            </Radio.Group>
          </div>
        </FormItem>
        {(() => {
          if (this.noticeDate.shieldCycle === EShieldCycle.single) {
            return (
              <FormItem
                class='mt24'
                errMsg={this.errMsg.singleRange}
                label={this.t('时间范围')}
                require={true}
              >
                <DatePicker
                  class='width-413'
                  appendToBody={true}
                  clearable={false}
                  disabledDate={this.datePick.options.disabledDate}
                  format='yyyy-MM-dd HH:mm:ss'
                  modelValue={this.noticeDate.single.range as any}
                  placement={'bottom-start'}
                  type='datetimerange'
                  onChange={v => this.handleSingleRangeChange(v)}
                  onKeyup={this.handleInputTime}
                  onPick-first={v => this.handleFirstTime(v)}
                />
                {!this.errMsg.singleRange && <div class='datetimerange-tip'>{this.t('注意：最大值为6个月')}</div>}
              </FormItem>
            );
          }
          if (this.noticeDate.shieldCycle === EShieldCycle.day) {
            return (
              <>
                <FormItem
                  class='mt24'
                  errMsg={this.errMsg.dayRange}
                  label={this.t('时间范围')}
                  require={true}
                >
                  <TimePicker
                    class='width-413'
                    appendToBody={true}
                    clearable={false}
                    modelValue={this.noticeDate.day.range}
                    placeholder={this.t('选择时间范围')}
                    type='timerange'
                    allowCrossDay
                    onUpdate:modelValue={v => this.handleDayRangeChange(v)}
                  />
                </FormItem>
              </>
            );
          }
          if (this.noticeDate.shieldCycle === EShieldCycle.week) {
            return (
              <>
                <FormItem
                  class='mt24'
                  errMsg={this.errMsg.weekList || this.errMsg.weekRange}
                  label={this.t('时间范围')}
                  require={true}
                >
                  <div class='week-data-time-range'>
                    <Select
                      class='mr10 width-413'
                      modelValue={this.noticeDate.week.list}
                      multiple={true}
                      placeholder={this.t('选择星期范围')}
                      onUpdate:modelValue={v => this.handleWeekListChange(v)}
                    >
                      {this.weekList.map(item => (
                        <Select.Option
                          id={item.id}
                          key={item.id}
                          name={item.name}
                        />
                      ))}
                    </Select>
                    <TimePicker
                      class='width-413'
                      allowCrossDay={true}
                      appendToBody={true}
                      clearable={false}
                      modelValue={this.noticeDate.week.range}
                      placeholder={this.t('选择时间范围')}
                      type='timerange'
                      onUpdate:modelValue={v => this.handleWeekRangeChange(v)}
                    />
                  </div>
                </FormItem>
              </>
            );
          }
          if (this.noticeDate.shieldCycle === EShieldCycle.month) {
            return (
              <FormItem
                class='mt24'
                errMsg={this.errMsg.monthList || this.errMsg.monthRange}
                label={this.t('时间范围')}
                require={true}
              >
                <div class='week-data-time-range'>
                  <DayPicker
                    value={this.noticeDate.month.list as any}
                    onChange={v => this.handleMonthListChange(v)}
                  />
                  <TimePicker
                    class='width-413'
                    allowCrossDay={true}
                    appendToBody={true}
                    clearable={false}
                    modelValue={this.noticeDate.month.range}
                    placeholder={this.t('选择时间范围')}
                    type='timerange'
                    onUpdate:modelValue={v => this.handleMonthRangeChange(v)}
                  />
                </div>
              </FormItem>
            );
          }
          return undefined;
        })()}
        {(() => {
          if (this.noticeDate.shieldCycle !== EShieldCycle.single) {
            return (
              <FormItem
                class='mt24'
                errMsg={this.errMsg.dateRange}
                label={this.t('日期范围')}
                require={true}
              >
                <DatePicker
                  class='width-413'
                  appendToBody={true}
                  clearable={false}
                  disabledDate={this.datePick.options.disabledDate}
                  format='yyyy-MM-dd HH:mm:ss'
                  modelValue={this.noticeDate.dateRange as any}
                  placement={'bottom-start'}
                  type='daterange'
                  onChange={v => this.handleDateRangeChange(v)}
                  onKeyup={this.handleInputTime}
                  onPick-first={v => this.handleFirstTime(v)}
                />
                {!this.errMsg.dateRange && <div class='datetimerange-tip'>{this.t('注意：最大值为6个月')}</div>}
              </FormItem>
            );
          }
          return undefined;
        })()}
      </div>
    );
  },
});
