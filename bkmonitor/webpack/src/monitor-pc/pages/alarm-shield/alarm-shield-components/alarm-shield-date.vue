<!--
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
-->
<template>
  <div class="date-notice-component">
    <div class="set-shield-config-item">
      <div class="item-label item-required">
        {{ $t('屏蔽周期') }}
      </div>
      <div class="item-container">
        <bk-radio-group v-model="shieldCycle.value">
          <bk-radio
            v-for="(item, index) in shieldCycle.list"
            :key="index"
            :value="item.value"
            >{{ item.label }}</bk-radio
          >
        </bk-radio-group>
      </div>
    </div>
    <div
      class="set-shield-config-item"
      :class="{ 'verify-show': dataVerify }"
    >
      <div class="item-label item-required">
        {{ $t('时间范围') }}
      </div>
      <div class="item-container">
        <!-- 单次 -->
        <template v-if="shieldCycle.value === 'single'">
          <div class="date-wrapper">
            <bk-date-picker
              v-model="noticeDate.single.range"
              :editable="true"
              :options="datePicker.options"
              type="datetimerange"
              format="yyyy-MM-dd HH:mm:ss"
              :clearable="false"
              :placeholder="$t('选择时间范围')"
              @change="validateDateRange"
            />
            <span
              v-if="shieldCycle.value === 'single' && !hasDateRange"
              class="error-message"
              >{{ $t('选择时间范围') }}</span
            >
            <span
              v-else
              class="date-scope-desc"
              >{{ $t('注意：最大值为6个月') }}</span
            >
          </div>
        </template>
        <!-- 每天 -->
        <template v-else-if="shieldCycle.value === 'day'">
          <div class="date-wrapper">
            <bk-time-picker
              v-model="noticeDate.day.range"
              type="timerange"
              :placeholder="$t('选择时间范围')"
              allow-cross-day
              :clearable="false"
              @change="validateScope"
            />
            <span
              v-show="shieldCycle.value !== 'single' && !hasTimeRange"
              class="error-message"
            >
              {{ $t('选择时间范围') }}
            </span>
          </div>
        </template>
        <!-- 每周 -->
        <template v-else-if="shieldCycle.value === 'week'">
          <div class="date-wrapper">
            <bk-select
              :multiple="true"
              :value="noticeDate.week.list"
              :placeholder="$t('选择星期范围')"
              :clearable="false"
              @change="handleSelectWeek"
            >
              <bk-option
                v-for="(item, index) in week.list"
                :id="item.id"
                :key="index"
                :name="item.name"
              />
            </bk-select>
            <span
              v-show="!hasWeekList"
              class="error-message"
            >
              {{ $t('选择每星期范围') }}
            </span>
          </div>
          <div class="date-wrapper">
            <bk-time-picker
              v-model="noticeDate.week.range"
              class="time-picker"
              type="timerange"
              :placeholder="$t('选择时间范围')"
              allow-cross-day
              @change="validateScope"
            />
            <span
              v-show="!hasTimeRange"
              class="error-message"
            >
              {{ $t('选择时间范围') }}
            </span>
          </div>
        </template>
        <!-- 每月 -->
        <template v-else-if="shieldCycle.value === 'month'">
          <div class="date-wrapper">
            <div
              ref="dayList"
              class="day-picker"
              @click="handlePopover($event)"
            >
              <span
                v-if="noticeDate.month.list.length"
                class="list"
                >{{ noticeDate.month.list.join('、') }}</span
              >
              <span
                v-else
                class="list placeholder"
              >
                {{ $t('选择每月时间范围') }}
              </span>
              <i
                class="bk-icon icon-angle-down"
                :class="{ 'up-arrow': !!popoverInstances }"
              />
              <i
                v-if="noticeDate.month.list.length"
                class="bk-select-clear bk-icon icon-close"
                @click="handleClearMonthList"
              />
            </div>
            <span
              v-show="!hasMonthList"
              class="error-message"
            >
              {{ $t('选择每月时间范围') }}
            </span>
          </div>
          <div class="date-wrapper">
            <bk-time-picker
              v-model="noticeDate.month.range"
              type="timerange"
              :placeholder="$t('选择时间范围')"
              allow-cross-day
              @change="validateScope"
            />
            <span
              v-show="!hasTimeRange"
              class="error-message"
            >
              {{ $t('选择时间范围') }}
            </span>
          </div>
        </template>
      </div>
    </div>
    <div
      v-if="shieldCycle.value !== 'single'"
      class="set-shield-config-item date-range verify-show"
    >
      <div class="item-label item-required">
        {{ $t('日期范围') }}
      </div>
      <div class="item-container">
        <bk-date-picker
          :key="shieldCycle.value"
          v-model="commonDateData.dateRange"
          :options="datePicker.options"
          type="daterange"
          format="yyyy-MM-dd"
          :clearable="false"
          :placeholder="$t('选择日期范围')"
          @change="validateDateRange"
        />
        <span
          v-if="!hasDateRange"
          class="error-message"
        >
          {{ $t('选择日期范围') }}
        </span>
        <span
          v-else
          class="date-scope-desc"
        >
          {{ $t('注意：最大值为6个月') }}
        </span>
      </div>
    </div>
    <!-- popover -->
    <div v-show="false">
      <ul
        ref="dayPicker"
        class="date-list-wrapper"
      >
        <li
          v-for="(item, index) in datePicker.list"
          :key="index"
          class="item"
          :class="{ active: item.active }"
          @click.stop="handleSelectDate(item)"
        >
          <span>{{ item.value }}</span>
        </li>
      </ul>
    </div>
  </div>
</template>
<script>
import dayjs from 'dayjs';

export default {
  name: 'AlarmShieldDate',
  model: {
    prop: 'commonDateData',
    event: 'changeCommonDateData',
  },
  props: {
    isClone: {
      type: Boolean,
      default: false,
    },
    // 公共的时间数据，双向绑定至父组件，为确保每次切换tab栏后时间数据共享
    commonDateData: {
      type: Object,
      default: () => ({}),
    },
  },
  data() {
    const defaultData = this.generationDefaultData();
    return {
      ...defaultData,
      popoverInstances: null,
      week: {
        list: [
          { name: this.$t('星期一'), id: 1 },
          { name: this.$t('星期二'), id: 2 },
          { name: this.$t('星期三'), id: 3 },
          { name: this.$t('星期四'), id: 4 },
          { name: this.$t('星期五'), id: 5 },
          { name: this.$t('星期六'), id: 6 },
          { name: this.$t('星期日'), id: 7 },
        ],
      },
    };
  },

  computed: {
    dataVerify() {
      return !this.hasTimeRange || !this.hasDateRange || !this.hasWeekList || !this.hasMonthList;
    },

    noticeDate() {
      return this.commonDateData.noticeDate;
    },

    shieldCycle() {
      return this.commonDateData.shieldCycle;
    },

    hasTimeRange() {
      return this.commonDateData.hasTimeRange;
    },
    hasDateRange() {
      return this.commonDateData.hasDateRange;
    },
    hasWeekList() {
      return this.commonDateData.hasWeekList;
    },
    hasMonthList() {
      return this.commonDateData.hasMonthList;
    },
  },
  watch: {
    shieldCycle: {
      handler() {
        this.commonDateData.hasTimeRange = true;
        this.commonDateData.hasDateRange = true;
        this.commonDateData.hasWeekList = true;
        this.commonDateData.hasMonthList = true;
      },
      deep: true,
    },
  },
  activated() {
    this.handleSetDefaultData();
    for (let i = 1; i < 32; i++) {
      this.datePicker.list.push({ value: i, active: false });
    }
  },
  methods: {
    // 初始化起始日期
    handleInitStartDate(type) {
      const { dateRange } = this.commonDateData;
      const startDate = new Date(dayjs.tz(dateRange[0]).format('YYYY-MM-DD'));
      const endDate = new Date(dayjs.tz(dateRange[1]).format('YYYY-MM-DD'));
      const nowDate = new Date(dayjs.tz().format('YYYY-MM-DD'));
      switch (type) {
        case 'single':
          if (new Date() > new Date(this.noticeDate.single.range[0])) this.noticeDate.single.range[0] = new Date();
          if (new Date() > new Date(this.noticeDate.single.range[1])) this.noticeDate.single.range = [];
          break;
        default:
          if (nowDate > startDate) this.commonDateData.dateRange[0] = dayjs.tz().format();
          if (nowDate > endDate) this.commonDateData.dateRange = [];
          break;
      }
    },
    generationDefaultData() {
      return {
        datePicker: {
          list: [],
          values: new Set(),
          options: {
            disabledDate(date) {
              return date && (date.valueOf() < Date.now() - 8.64e7 || date.valueOf() > Date.now() + 8.64e7 * 181);
            },
          },
        },
      };
    },
    handlePopover() {
      this.$nextTick(() => {
        this.popoverInstances = this.$bkPopover(this.$refs.dayList, {
          content: this.$refs.dayPicker,
          trigger: 'manual',
          arrow: false,
          placement: 'bottom-start',
          theme: 'light common-monitor',
          maxWidth: 280,
          distance: 5,
          duration: [275, 0],
          interactive: true,
          followCursor: false,
          flip: true,
          flipBehavior: ['bottom', 'top'],
          flipOnUpdate: true,
          onHidden: () => {
            this.popoverInstances.hide(0);
            this.popoverInstances.destroy();
            this.popoverInstances = null;
          },
        });
        this.popoverInstances.show();
      });
    },
    handleClearMonthList() {
      this.noticeDate.month.list = [];
      this.datePicker.values = new Set();
      this.datePicker.list.forEach(item => {
        item.active = false;
      });
    },
    // 选择每周的时候触发，勾选的值会按升序排列
    handleSelectWeek(v) {
      this.noticeDate.week.list = JSON.parse(JSON.stringify(v)).sort((a, b) => a - b);
      this.validateList('week');
    },
    // 选择每月的时候触发，勾选的值会按升序排列
    handleSelectDate(item) {
      item.active = !item.active;
      if (this.datePicker.values.has(item.value)) {
        this.datePicker.values.delete(item.value);
      } else {
        this.datePicker.values.add(item.value);
      }
      this.noticeDate.month.list = Array.from(this.datePicker.values).sort((a, b) => a - b);
      this.validateList('month');
    },
    // 初始化数据
    handleSetDefaultData() {
      const defaultData = this.generationDefaultData();
      Object.keys(defaultData).forEach(key => {
        this[key] = defaultData[key];
      });
    },
    validateDateRange(val) {
      this.commonDateData.hasDateRange = !!val.join('');
      const startTime = dayjs.tz(this.noticeDate.single.range[0]).format('YYYY-MM-DD HH:mm:ssZZ');
      const endTime = dayjs.tz(this.noticeDate.single.range[1]).format('YYYY-MM-DD HH:mm:ssZZ');
      if (startTime.includes('00:00:00') && endTime.includes('00:00:00')) {
        this.noticeDate.single.range[1].setHours(23, 59, 59);
        this.noticeDate.single.range = [this.noticeDate.single.range[0], this.noticeDate.single.range[1]];
      }
    },
    // 时间范围的校验
    validateScope() {
      const type = this.shieldCycle.value;
      this.commonDateData.hasTimeRange = this.commonDateData.noticeDate[type].range.join('');
    },
    // 每周和每月的校验 type: week month
    validateList(type) {
      if (type === 'week') {
        this.commonDateData.hasWeekList = this.noticeDate.week.list.join('');
      } else {
        this.commonDateData.hasMonthList = this.noticeDate.month.list.join('');
      }
    },
    validateValue() {
      const type = this.shieldCycle.value;
      const result = this.noticeDate[type];
      if (type === 'single') {
        this.commonDateData.hasTimeRange = true;
        this.commonDateData.hasDateRange = !!result.range.join('');
      } else {
        this.commonDateData.hasDateRange = !!this.commonDateData.dateRange.join('');
        this.validateScope();
      }
      if (type === 'week') {
        this.validateList('week');
        return this.hasDateRange && this.hasTimeRange && this.hasWeekList;
      }
      if (type === 'month') {
        this.validateList('month');
        return this.hasDateRange && this.hasTimeRange && this.hasMonthList;
      }
      return this.hasDateRange && this.hasTimeRange;
    },
    /**
     * @description 获取组件的值
     */
    getDateData() {
      if (!this.validateValue()) return false;
      const cycleMap = { single: 1, day: 2, week: 3, month: 4 };
      const params = {
        dateRange: [],
        type: cycleMap[this.shieldCycle.value],
        typeEn: this.shieldCycle.value,
        ...this.noticeDate,
      };
      if (this.shieldCycle.value !== 'single') {
        params.dateRange[0] = `${dayjs.tz(this.commonDateData.dateRange[0]).format('YYYY-MM-DD')} 00:00:00`;
        params.dateRange[1] = `${dayjs.tz(this.commonDateData.dateRange[1]).format('YYYY-MM-DD')} 23:59:59`;
      }
      Object.keys(this.noticeDate).forEach(key => {
        if (key === 'single') {
          this.noticeDate[key].range = this.noticeDate[key].range.map(item =>
            dayjs.tz(item).format('YYYY-MM-DD HH:mm:ssZZ')
          );
        }
      });
      return params;
    },
    /**
     * @description 设置组件的值
     */
    setDate(v) {
      const type = v.typeEn;
      this.shieldCycle.value = type;
      this.noticeDate[type] = v[type];
      if (type !== 'single') {
        this.commonDateData.dateRange = v.dateRange;
      }
      if (type === 'month') {
        const { list } = v[type];
        this.datePicker.list.forEach(item => {
          if (list.includes(item.value)) {
            item.active = true;
            this.datePicker.values.add(item.value);
          }
        });
      }

      // 如果是克隆操作则根据当前时间初始化起始和结束时间
      this.isClone && this.handleInitStartDate(type);
    },
  },
};
</script>
<style lang="scss" scoped>
.date-notice-component {
  .verify-show {
    /* stylelint-disable-next-line declaration-no-important */
    margin-bottom: 32px !important;
  }

  .set-shield-config-item {
    display: flex;
    flex-direction: row;
    align-items: center;
    margin-bottom: 20px;
    font-size: 14px;
    color: #63656e;

    &.date-range {
      margin-bottom: 20px;
    }

    .item-label {
      position: relative;
      flex: 0 0;
      min-width: 110px;
      margin-right: 24px;
      text-align: right;
    }

    .item-required::after {
      position: absolute;
      top: 2px;
      right: -9px;
      color: red;
      content: '*';
    }

    .item-container {
      position: relative;
      display: flex;

      .scope-item {
        width: 168px;
      }

      .date-wrapper {
        position: relative;
      }

      .bk-form-radio {
        margin-right: 32px;

        :deep(input[type='radio']) {
          margin-right: 8px;
        }
      }

      .bk-date-picker {
        width: 413px;
        margin-right: 10px;

        // :deep(.bk-date-picker-editor) {
        //     padding-left: 12px;
        // }
      }

      .day-picker {
        position: relative;
        display: flex;
        width: 413px;
        height: 32px;
        padding: 0 16px 0 12px;
        margin-right: 10px;
        font-size: 12px;
        line-height: 30px;
        color: #63656e;
        cursor: pointer;
        border: 1px solid #c4c6cc;
        border-radius: 2px;

        .bk-icon {
          position: absolute;
          top: 8px;
          right: 12px;
          transition:
            transform 0.3s cubic-bezier(0.4, 0, 0.2, 1),
            -webkit-transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .bk-select-clear {
          position: absolute;
          top: 8px;
          right: 11px;
          z-index: 100;
          display: none;
          width: 14px;
          height: 14px;
          font-size: 12px;
          line-height: 14px;
          color: #fff;
          text-align: center;
          background-color: #c4c6cc;
          border-radius: 50%;

          &::before {
            display: block;
            transform: scale(0.7);
          }

          &:hover {
            background-color: #979ba5;
          }
        }

        .up-arrow {
          transform: rotate(-180deg);
        }

        .placeholder {
          font-size: 12px;
          color: #c4c6cc;
        }

        .list {
          overflow: hidden;
        }

        &:hover {
          .bk-select-clear {
            display: inline-block;
          }
        }
      }

      .date-scope-desc {
        position: absolute;
        top: 36px;
        left: 0;
        font-size: 12px;
        color: #c4c6cc;
      }

      .error-message {
        position: absolute;
        top: 36px;
        left: 0;
        font-size: 12px;
        color: #ea3636;
      }
    }

    .bk-select {
      width: 413px;
      margin-right: 10px;
    }
  }
}

.date-list-wrapper {
  box-sizing: border-box;
  display: flex;
  flex-wrap: wrap;
  width: 254px;
  padding: 10px 16px 15px 12px;
  margin: 0;
  border: 1px solid #c4c6cc;
  border-radius: 2px;

  .item {
    display: inline-block;
    width: 32px;
    height: 32px;
    font-size: 12px;
    line-height: 32px;
    color: #63656e;
    text-align: center;
    cursor: pointer;
    list-style: none;

    &:hover {
      background: #f0f1f5;
    }
  }

  .active {
    span {
      display: inline-block;
      width: 100%;
      height: 100%;
      color: #fff;
      background-color: #3a84ff;
    }
  }
}

:deep(.bk-date-picker-rel .clear-action) {
  display: none;
}
</style>
