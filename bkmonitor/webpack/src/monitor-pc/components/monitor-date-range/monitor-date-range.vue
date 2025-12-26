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
  <div :class="['monitor-date-range-container', offset === 'left' ? 'offset-left' : 'offset-right']">
    <div class="monitor-date-range">
      <div
        ref="monitorDateRange"
        :class="['date', { 'is-focus': isFoucs }]"
        tabindex="0"
        @click="handleFocus"
        @blur="handleBlur"
      >
        <span
          v-if="icon"
          :class="[icon, 'icon-monitor', 'left-icon', { mr5: showName }]"
        />
        <span
          v-show="showName"
          class="text"
          >{{ dateName }}</span
        >
        <span class="bk-select-angle bk-icon icon-angle-down" />
      </div>
      <transition name="fade">
        <div
          v-show="showDropdown"
          class="date-panel"
          :style="{ minWidth: hasCustomDate ? '290px' : dropdownWidth + 'px', zIndex }"
        >
          <ul class="option-list">
            <li
              v-for="(option, index) in options"
              :key="index"
              class="item"
              :class="{ 'item-active': date === option.name }"
              @click="handleSelect(option)"
            >
              {{ option.name }}
            </li>
          </ul>
          <div
            class="option-footer"
            @mousedown.stop.prevent="handleCustom"
          >
            {{ $t('自定义') }}
          </div>
        </div>
      </transition>
    </div>
    <bk-date-picker
      ref="bkDateRange"
      :style="{ zIndex }"
      class="monitor-date"
      :split-panels="false"
      :value="initDateTimeRange"
      :placeholder="$t('选择日期时间范围')"
      :type="'datetimerange'"
      @change="handleDateChange"
      @pick-success="handleConfirm"
    />
  </div>
</template>
<script>
import dayjs from 'dayjs';

export default {
  name: 'MonitorDateRange',
  model: {
    prop: 'value',
    event: 'change',
  },
  props: {
    offset: {
      type: String,
      default: 'left',
    },
    options: {
      type: Array,
      default: () => [],
    },
    icon: {
      type: String,
      default: '',
    },
    showName: {
      type: Boolean,
      default: true,
    },
    dropdownWidth: {
      type: [Number, String],
      default: '84',
    },
    value: [Number, String, Array],
    zIndex: {
      type: Number,
      default: 10,
    },
  },
  data() {
    return {
      date: '',
      isFoucs: false,
      showDropdown: false,
      initDateTimeRange: [dayjs.tz().subtract(1, 'hours').format(), dayjs.tz().format()],
    };
  },
  computed: {
    hasCustomDate() {
      return this.options.some(set => set.name === set.value);
    },
    dateName() {
      if (Array.isArray(this.value)) {
        return `${this.value[0]} -- ${this.value[1]}`;
      }
      const name = this.options.find(item => item.value === this.value)?.name;
      return name;
    },
  },
  watch: {
    value() {
      this.handleSetDate();
    },
  },
  mounted() {
    if (this.value) {
      this.handleSetDate();
    }
  },
  methods: {
    handleSetDate() {
      const value = Array.isArray(this.value) ? `${this.value[0]} -- ${this.value[1]}` : this.value;
      this.date = value;
      this.options.forEach(item => {
        if (item.value === value) {
          this.date = item.name;
        }
      });
      Array.isArray(this.value) && (this.initDateTimeRange = this.value);
    },
    handleFocus() {
      this.isFoucs = !this.isFoucs;
      this.showDropdown = !this.showDropdown;
    },
    handleBlur() {
      this.showDropdown = false;
      this.isFoucs = false;
      this.$refs.bkDateRange.visible = false;
    },
    // 点击自定义
    handleCustom() {
      setTimeout(() => {
        this.$refs.bkDateRange.visible = true;
      });
    },
    handleSelect(v) {
      this.date = v.name;
      this.$emit('change', v.value);
    },
    handleDateChange(v) {
      this.initDateTimeRange = v;
    },
    handleConfirm() {
      this.date = `${dayjs.tz(this.initDateTimeRange[0]).format('YYYY-MM-DD HH:mm:ssZZ')} -- ${dayjs.tz(this.initDateTimeRange[1]).format('YYYY-MM-DD HH:mm:ssZZ')}`;
      if (!this.options.some(set => set.value === this.date)) {
        // 重复的不新增
        this.$emit('add-option', { name: this.date, value: this.date });
      }
      this.$refs.bkDateRange.visible = false;
      this.$refs.monitorDateRange?.blur?.();
      this.$emit('change', this.initDateTimeRange);
    },
  },
};
</script>
<style lang="scss" scoped>
.monitor-date-range-container {
  position: relative;

  .monitor-date-range {
    position: relative;

    .date-icon {
      font-size: 14px;
    }

    .date {
      position: relative;
      display: flex;
      align-items: center;
      height: 32px;
      padding: 0 36px 0 10px;
      line-height: 32px;
      color: #63656e;
      cursor: pointer;
      background: #fff;
      border: 1px solid #c4c6cc;
      border-radius: 2px;

      .date-icon {
        margin-right: 5px;
      }

      .left-icon {
        font-size: 14px;
      }

      .mr5 {
        margin-right: 5px;
      }

      &.is-focus {
        border-color: #3a84ff;
        box-shadow: 0 0 4px rgb(58 132 255 / 40%);
      }

      .icon-angle-down {
        position: absolute;
        top: 5px;
        right: 12px;
        font-size: 20px;
      }
    }

    .date-panel {
      position: absolute;
      top: 30px;
      right: 0;
      z-index: 10;
      overflow: hidden;
      line-height: 32px;
      color: #63656e;
      background: #fff;
      border: 1px solid #dcdee5;
      border-radius: 2px;

      .option-list {
        display: flex;
        flex-direction: column;
        max-height: 230px;
        padding: 6px 0;
        overflow: auto;

        .item {
          padding: 0 16px;

          &:hover {
            color: #3a84ff;
            cursor: pointer;
            background-color: #f4f6fa;
          }

          &.item-active {
            color: #3a84ff;
            background-color: #f4f6fa;
          }
        }
      }

      .option-footer {
        display: flex;
        align-items: center;
        height: 32px;
        padding: 0 16px;
        cursor: pointer;
        background-color: #fafbfd;
        border-top: 1px solid #dcdee5;
      }
    }
  }

  .fade-enter-active,
  .fade-leave-active {
    transition: height 0.6s;
  }

  .date-enter,
  .date-leave {
    opacity: 0;
    transition: 0.6s cubic-bezier(0.4, 0, 0.2, 1);
  }
}

.offset-left {
  :deep(.bk-date-picker.monitor-date) {
    position: absolute;
    right: 0;
    width: 0;

    .bk-date-picker-dropdown {
      /* stylelint-disable-next-line declaration-no-important */
      top: 20px !important;

      /* stylelint-disable-next-line declaration-no-important */
      right: 0 !important;

      /* stylelint-disable-next-line declaration-no-important */
      left: inherit !important;
      padding-bottom: 0;
    }

    .bk-date-picker-rel {
      display: none;
    }

    .bk-date-picker-dropdown {
      /* stylelint-disable-next-line declaration-no-important */
      top: 20px !important;

      /* stylelint-disable-next-line declaration-no-important */
      right: 0 !important;

      /* stylelint-disable-next-line declaration-no-important */
      left: inherit !important;
    }
  }
}

.offset-right {
  :deep(.bk-date-picker.monitor-date) {
    position: absolute;
    left: 0;
    width: 0;

    .bk-date-picker-dropdown {
      /* stylelint-disable-next-line declaration-no-important */
      top: 20px !important;

      /* stylelint-disable-next-line declaration-no-important */
      left: 0 !important;

      /* stylelint-disable-next-line declaration-no-important */
      left: inherit !important;
      padding-bottom: 0;
    }

    .bk-date-picker-rel {
      display: none;
    }

    .bk-date-picker-dropdown {
      /* stylelint-disable-next-line declaration-no-important */
      top: 20px !important;

      /* stylelint-disable-next-line declaration-no-important */
      left: 0 !important;

      /* stylelint-disable-next-line declaration-no-important */
      left: inherit !important;
    }
  }
}
</style>
