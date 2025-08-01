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
import { type PropType, computed, defineComponent, ref, watch } from 'vue';

import { Popover } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { generateTimeSlots } from '../utils';

import './data-time-select.scss';

type ShowType = 'calendar' | 'week';

export default defineComponent({
  name: 'DataTimeSelect',
  props: {
    /** 名称 */
    label: { type: String, default: '' },
    /** 名称宽度 */
    labelWidth: { type: Number, default: 52 },
    modelValue: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    type: {
      type: String as PropType<ShowType>,
      default: 'week',
    },
  },
  emits: ['update:modelValue', 'change'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const oldValue = ref([]);
    const localValue = ref([]);
    const isChange = computed(() => {
      if (localValue.value.length !== oldValue.value.length) return true;
      return oldValue.value.some((item, ind) => item !== localValue.value[ind]);
    });

    const localText = computed(() => {
      if (props.type === 'week') {
        const date = weekList.find(item => item.id === localValue.value[0])?.label || '';
        return `${date} ${localValue.value[1] || ''}`.trim();
      }

      const dateStr = localValue.value[0] ? `${localValue.value[0]}${t('日')}` : '';
      return `${dateStr} ${localValue.value[1] || ''}`.trim();
    });

    watch(
      () => props.modelValue,
      val => {
        localValue.value = [...val];
      },
      {
        immediate: true,
      }
    );

    // ---------popover弹窗控制------------
    /** 控制弹窗显示隐藏 */
    const show = ref(false);
    /** 显示下拉框 */
    function handleAfterShow() {
      show.value = true;
      oldValue.value = [...localValue.value];
    }
    /** 隐藏下拉框 */
    function handleAfterHidden({ isShow }) {
      show.value = isShow;
      if (localValue.value.every(item => !!item)) {
        handleEmitData();
      }
    }

    // ------------日历和时间选择------------
    const calendarList = new Array(31).fill(0).map((item, ind) => {
      const val = ind + 1;
      return {
        label: val,
        value: val < 10 ? `0${val}` : String(val),
      };
    });
    const timeList = generateTimeSlots();
    const weekList = [
      { id: '01', label: t('周一') },
      { id: '02', label: t('周二') },
      { id: '03', label: t('周三') },
      { id: '04', label: t('周四') },
      { id: '05', label: t('周五') },
      { id: '06', label: t('周六') },
      { id: '07', label: t('周日') },
    ];
    /** 当前日期 */
    const currentDate = new Date().getDate();
    function handleSelect(val: string, type: 'date' | 'time') {
      if (type === 'date') {
        localValue.value[0] = val;
      } else {
        localValue.value[1] = val;
      }
    }

    function handleEmitData() {
      if (isChange.value) {
        emit('update:modelValue', localValue.value);
        emit('change', localValue.value);
      }
    }

    return {
      t,
      localValue,
      localText,
      show,
      handleAfterShow,
      handleAfterHidden,
      calendarList,
      currentDate,
      timeList,
      weekList,
      handleSelect,
    };
  },
  render() {
    return (
      <div class='data-time-select-component'>
        {this.label && (
          <div
            style={{ width: `${this.labelWidth}px` }}
            class='label'
          >
            {this.label}
          </div>
        )}
        <div class={['data-time-select-wrapper', this.show && 'active']}>
          <Popover
            extCls='data-time-select-popover component'
            arrow={false}
            is-show={this.show}
            placement='bottom-start'
            theme='light'
            trigger='click'
            onAfterHidden={this.handleAfterHidden}
            onAfterShow={this.handleAfterShow}
          >
            {{
              content: () => (
                <div class='popover-wrapper'>
                  <div class='left-data-panel panel'>
                    <div class='title'>{this.t('日期选择')}</div>
                    {this.type === 'week' ? (
                      <div class='week-list'>
                        {this.weekList.map(date => (
                          <div
                            class={['list-item date', date.id === this.localValue[0] && 'selected']}
                            onClick={() => this.handleSelect(date.id, 'date')}
                          >
                            {date.label}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div class='data-list'>
                        {this.calendarList.map(item => (
                          <div
                            class={[
                              'list-item',
                              this.currentDate === Number(item.value) && 'current',
                              item.value === this.localValue[0] && 'selected',
                            ]}
                            onClick={() => this.handleSelect(item.value, 'date')}
                          >
                            {item.label}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  <div class='right-time-panel panel'>
                    <div class='title'>{this.t('时间选择')}</div>
                    <div class='content'>
                      {this.timeList.map(time => (
                        <div
                          class={['item time', time === this.localValue[1] && 'selected']}
                          onClick={() => this.handleSelect(time, 'time')}
                        >
                          {time}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ),
              default: () => (
                <div class={['content-wrapper', !this.localText && 'placeholder']}>
                  {this.localText || this.t('选择')}
                </div>
              ),
            }}
          </Popover>
        </div>
      </div>
    );
  },
});
