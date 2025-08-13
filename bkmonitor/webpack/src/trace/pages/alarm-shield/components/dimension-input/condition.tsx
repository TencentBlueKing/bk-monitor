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
import { type PropType, defineComponent, ref } from 'vue';

import { Popover } from 'bkui-vue';
import { CONDITION } from 'monitor-pc/constant/constant';

export default defineComponent({
  name: 'ConditionCondition',
  props: {
    item: {
      type: Object,
      default: () => null,
    },
    onChange: {
      type: Function as PropType<(v: string) => void>,
      default: _v => {},
    },
  },
  setup(props) {
    const popoverRef = ref(null);
    const conditionList = ref(CONDITION);

    function handleSelect(item) {
      popoverRef.value?.hide();
      props.onChange(item.id);
    }
    return () => (
      <Popover
        ref={popoverRef}
        extCls='dimension-condition-input-condition-condition-component-pop'
        arrow={false}
        placement='bottom-start'
        theme='light'
        trigger='click'
      >
        {{
          default: () => (
            <input
              style={{ display: props.item.condition ? 'block' : 'none' }}
              class='condition-item condition-item-condition mb-8'
              value={props.item.condition.toLocaleUpperCase()}
              readonly
            />
          ),
          content: () => (
            <div>
              <ul class='list-wrap'>
                {conditionList.value.map((item, index) => (
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
