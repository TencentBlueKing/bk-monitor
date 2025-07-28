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
import { type PropType, defineComponent, ref, watch } from 'vue';

import { Popover } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import './day-picker.scss';

export default defineComponent({
  name: 'DayPicker',
  props: {
    value: {
      type: Array as PropType<(number | string)[]>,
      default: () => [],
    },
    onChange: {
      type: Function as PropType<(v: number[]) => void>,
      default: () => {},
    },
  },
  setup(props) {
    const { t } = useI18n();
    const localValue = ref(props.value || []);
    let days = [];
    for (let i = 1; i <= 31; i++) {
      days.push({ value: i, active: props.value.map(v => String(v)).indexOf(String(i)) >= 0 });
    }
    const localList = ref(days);
    days = [];

    watch(
      () => props.value,
      v => {
        localValue.value = v;
      },
      {
        immediate: true,
      }
    );

    function handleShow() {
      //
    }
    function handleSelectItem(item, index) {
      localList.value[index].active = !item.active;
      localValue.value = localList.value
        .filter(l => l.active)
        .map(l => l.value)
        .sort((a, b) => a - b);
      props.onChange(localValue.value);
    }

    function renderFn() {
      return (
        <Popover
          extCls='alarm-shield-day-picker-component-pop-wrap'
          arrow={false}
          placement='bottom-start'
          theme='light'
          trigger='click'
          onShow={handleShow}
        >
          {{
            default: () => (
              <div class='alarm-shield-day-picker-component'>
                {localValue.value.length ? (
                  localValue.value.join('、')
                ) : (
                  <span class='placeholder'>{t('选择每月时间范围')}</span>
                )}
              </div>
            ),
            content: () => (
              <div class='list-wrap'>
                {localList.value.map((item, index) => (
                  <div
                    key={item.value}
                    class={['list-item', { active: item.active }]}
                    onClick={() => handleSelectItem(item, index)}
                  >
                    <span>{item.value}</span>
                  </div>
                ))}
              </div>
            ),
          }}
        </Popover>
      );
    }
    return {
      renderFn,
    };
  },
  render() {
    return this.renderFn();
  },
});
