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
import { type PropType, computed, defineComponent, onMounted, reactive, ref, watch } from 'vue';

import { Popover } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import './calendar-select.scss';

export default defineComponent({
  name: 'CalendarSelect',
  props: {
    /** 名称 */
    label: { type: String, default: '' },
    /** 名称宽度 */
    labelWidth: { type: Number, default: 52 },
    modelValue: {
      type: Array as PropType<number[]>,
      default: () => [],
    },
    /** 需要起始日功能 */
    hasStart: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['update:modelValue', 'change', 'selectEnd'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const oldValue = ref<number[]>([]);
    /** 已选择的数据 */
    const localValue = ref<number[]>([]);
    /** 起始日 */
    const startDate = ref<number>();
    /** 根据起始日进行排序后的数据 */
    const sortLocalValue = computed(() => {
      const val = [...localValue.value].sort((a, b) => a - b);
      if (!props.hasStart) return val;
      let ind = val.findIndex(item => item >= startDate.value);
      if (ind === -1) ind = 0;
      return [...val.splice(ind, val.length), ...val];
    });
    const isChange = computed(() => {
      if (oldValue.value.length !== sortLocalValue.value.length) return true;
      return oldValue.value.some((val, ind) => sortLocalValue.value[ind] !== val);
    });

    watch(
      () => props.modelValue,
      val => {
        localValue.value = [...val];
        startDate.value = val[0];
      },
      {
        immediate: true,
      }
    );

    const contentTextRef = ref();
    watch(
      () => sortLocalValue.value,
      val => {
        contentTextRef.value.innerText = val.length ? val.join('、') : t('选择');
      }
    );

    function handleBlur(e: Event) {
      const keys = (e.target as HTMLDivElement).textContent.trim().split('、');
      let val = [];
      keys.forEach(key => {
        if (!/^(\d+|(\d+-\d+))$/.test(key)) return;
        const [start, end] = key.split('-');
        if (!end) {
          Number(start) >= 1 && Number(start) <= 31 && val.push(Number(start));
        } else {
          const max = Math.max(Number(start), Number(end));
          const min = Math.min(Number(start), Number(end));
          for (let i = min < 1 ? 1 : min; i <= (max > 31 ? 31 : max); i++) val.push(i);
        }
      });
      val = Array.from(new Set(val)).sort((a, b) => a - b);
      let ind = val.findIndex(item => item >= startDate.value);
      if (ind === -1) ind = 0;
      startDate.value = val[ind];
      localValue.value = [...val];
      handleEmitData();
      emitSelectEnd();
    }

    // ---------popover弹窗控制------------
    /** 控制弹窗显示隐藏 */
    const show = ref(false);
    const calendarList = new Array(31).fill(0).map((item, ind) => ind + 1);
    const currentDate = new Date().getDate();
    const hoverVal = ref(0);
    /**
     * 校验日期的选中状态，用于确定样式
     * @param item 日期
     * @returns 'selected-middle'：过渡 selected:首尾选中
     */
    function validSelected(item: number) {
      let isSelected = false;
      const res = localValue.value.filter(val => {
        if (val === item) isSelected = true;
        return val >= item - 1 && val <= item + 1;
      });
      if (res.length === 3) return 'selected-middle';
      if (item > temporarySelect.start && item < temporarySelect.end) return 'selected-middle';
      if (item === temporarySelect.start || item === temporarySelect.end) isSelected = true;
      return isSelected ? 'selected' : '';
    }
    /** 暂时选中的日期， 用于判断用户需要新增哪些日期 */
    const temporarySelect = reactive({
      start: undefined,
      end: undefined,
    });
    /**
     * 点击日期事件
     * @param val 点击的日期
     */
    function handleDateClick(val: number) {
      const dateIndex = localValue.value.findIndex(item => item === val);
      // 删除日期
      if (dateIndex !== -1) {
        localValue.value.splice(dateIndex, 1);
        if (val === startDate.value) {
          // 删除起始日
          const max = localValue.value.find(item => item > val);
          startDate.value = max ? max : localValue.value[0];
        }
        return;
      }

      if (!temporarySelect.start) {
        temporarySelect.start = val;
        return;
      }
      temporarySelect.end = val;

      // 新增日期
      const min = Math.min(temporarySelect.start, temporarySelect.end);
      const max = temporarySelect.start + temporarySelect.end - min;
      const arr = new Array(max - min + 1).fill(0).map((item, ind) => ind + min);
      localValue.value = Array.from(new Set([...localValue.value, ...arr]));
      temporarySelect.start = undefined;
      temporarySelect.end = undefined;
    }
    /**
     * 设置日期为起始日
     * @param val 日期
     */
    function handleStartChange(e: Event, val: number) {
      e.stopPropagation();
      if (startDate.value === val) return;
      startDate.value = val;
      localValue.value = Array.from(new Set([...localValue.value, val]));
      handleEmitData();
    }

    /** 显示下拉框 */
    function handleShowSelect() {
      show.value = true;
      oldValue.value = [...localValue.value];
    }
    /** 隐藏下拉框 */
    function handleAfterHidden({ isShow }) {
      show.value = isShow;
      hoverVal.value = 0;
      handleEmitData();
      emitSelectEnd();
    }

    function handleEmitData() {
      if (isChange.value) {
        emit('update:modelValue', sortLocalValue.value);
        emit('change', sortLocalValue.value);
      }
    }

    function emitSelectEnd() {
      if (isChange.value) {
        emit('selectEnd', sortLocalValue.value);
      }
    }

    onMounted(() => {
      contentTextRef.value.innerText = sortLocalValue.value.length ? sortLocalValue.value.join('、') : t('选择');
    });

    return {
      t,
      localValue,
      startDate,
      sortLocalValue,
      contentTextRef,
      handleBlur,
      show,
      calendarList,
      currentDate,
      hoverVal,
      handleStartChange,
      validSelected,
      handleDateClick,
      handleShowSelect,
      handleAfterHidden,
    };
  },
  render() {
    return (
      <div class='calendar-select-component'>
        {this.label && (
          <div
            style={{ width: `${this.labelWidth}px` }}
            class='label'
          >
            {this.label}
          </div>
        )}
        <div
          class='calendar-select-wrapper'
          onClick={this.handleShowSelect}
        >
          <i class={['icon-monitor', 'arrow', 'icon-arrow-down', this.show && 'active']} />
          <Popover
            width='250'
            extCls='calendar-select-popover component'
            arrow={false}
            is-show={this.show}
            placement='bottom-start'
            theme='light'
            trigger='click'
            onAfterHidden={this.handleAfterHidden}
          >
            {{
              content: () => (
                <div
                  class='calendar-list'
                  onMouseleave={() => (this.hoverVal = 0)}
                >
                  {this.calendarList.map(item => (
                    <div
                      class={[
                        'item',
                        this.currentDate === item && 'current',
                        this.validSelected(item),
                        this.startDate === item && 'start',
                      ]}
                      onClick={() => this.handleDateClick(item)}
                      onMouseenter={() => (this.hoverVal = item)}
                    >
                      {this.hoverVal === item && this.hasStart && (
                        <div
                          class='tooltip-popover'
                          onClick={e => this.handleStartChange(e, item)}
                        >
                          <span class={{ 'setting-btn': item !== this.startDate }}>
                            {item === this.startDate ? this.t('起始日') : this.t('设为起始日')}
                          </span>
                          <div class='popover-arrow' />
                        </div>
                      )}
                      {item}
                    </div>
                  ))}
                </div>
              ),
              default: () => (
                <div
                  ref='contentTextRef'
                  class={['content-wrapper', !this.sortLocalValue.length && 'placeholder']}
                  contenteditable
                  onBlur={this.handleBlur}
                />
              ),
            }}
          </Popover>
        </div>
      </div>
    );
  },
});
