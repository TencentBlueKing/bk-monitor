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
import { NUMBER_CONDITION_METHOD_LIST, STRING_CONDITION_METHOD_LIST } from 'monitor-pc/constant/constant';

export default defineComponent({
  name: 'ConditionMethod',
  props: {
    value: {
      type: String,
      default: '',
    },
    dimensionKey: {
      type: String,
      default: '',
    },
    dimensionList: {
      type: Array as PropType<any[]>,
      default: () => [],
    },
    onChange: {
      type: Function as PropType<(v: string) => void>,
      default: () => {},
    },
  },
  setup(props) {
    const popoverRef = ref(null);
    const methodList = ref([]);

    const show = ref(false);

    watch(
      () => props.dimensionKey,
      key => {
        const { type } = props.dimensionList.find(item => item.id === key) || { type: 'string' };
        methodList.value = handleGetMethodList(type);
      },
      {
        immediate: true,
      }
    );

    function getMethodNameById(id: string) {
      return NUMBER_CONDITION_METHOD_LIST.find(item => item.id === id)?.name || '';
    }
    function handleGetMethodList(type: 'number' | 'string') {
      if (type === 'number') {
        return NUMBER_CONDITION_METHOD_LIST;
      }
      return STRING_CONDITION_METHOD_LIST;
    }

    function handleSelect(item) {
      popoverRef.value?.hide();
      props.onChange(item.id);
    }

    return () => (
      <Popover
        ref={popoverRef}
        extCls='dimension-condition-input-condition-method-component-pop'
        arrow={false}
        placement='bottom-start'
        theme='light'
        trigger='click'
        onAfterHidden={() => (show.value = false)}
        onAfterShow={() => (show.value = true)}
      >
        {{
          default: () => (
            <span
              class={[
                'condition-item condition-item-method mb-8',
                {
                  active: show.value,
                },
              ]}
            >
              {getMethodNameById(props.value)}
            </span>
          ),
          content: () => (
            <div>
              <ul class='list-wrap'>
                {methodList.value.map((item, index) => (
                  <li
                    key={index}
                    onClick={() => handleSelect(item)}
                  >
                    {item.name}
                  </li>
                ))}
              </ul>
            </div>
          ),
        }}
      </Popover>
    );
  },
});
