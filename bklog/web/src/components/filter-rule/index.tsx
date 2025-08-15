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
import { defineComponent, ref, watch } from 'vue';
import ConfigRule from './config-rule';

import './index.scss';

interface FieldInfo {
  field_name: string;
  logic_operator: string;
  op: string;
  value: string[];
}

export default defineComponent({
  name: 'FilterRule',
  components: {
    ConfigRule,
  },
  props: {
    data: {
      type: Array<FieldInfo>,
      default: () => [],
    },
  },
  setup(props, { expose }) {
    const filterRules = ref<FieldInfo[]>([]);

    const comparedList = [
      { id: 'and', name: 'AND' },
      { id: 'or', name: 'OR' },
    ];

    watch(
      () => props.data,
      () => {
        filterRules.value = props.data;
      },
      {
        immediate: true,
      },
    );

    const handleDeleteItem = (index: number) => {
      filterRules.value.splice(index, 1);
    };

    const handleConfirmConfig = (rule: FieldInfo, index?: number) => {
      if (index !== undefined) {
        // 修改
        Object.assign(filterRules.value[index], rule);
        return;
      }
      // 新增
      filterRules.value.push({
        logic_operator: 'and',
        ...rule,
      });
    };

    const getValue = () => filterRules.value;

    expose({
      getValue,
    });

    return () => (
      <div class='filter-rule'>
        {filterRules.value.map((item, index) => (
          <div
            class='filter-rule-item'
            key={index}
          >
            {filterRules.value.length && index > 0 && (
              <bk-select
                class='icon-box'
                value={item.logic_operator}
                clearable={false}
                popover-width={100}
                on-change={value => (item.logic_operator = value)}
              >
                {comparedList.map(option => (
                  <bk-option
                    id={option.id}
                    name={option.name}
                  />
                ))}
              </bk-select>
            )}
            <config-rule
              data={item}
              is-create={false}
              on-confirm={rule => handleConfirmConfig(rule, index)}
              on-delete={() => handleDeleteItem(index)}
            />
          </div>
        ))}
        <config-rule on-confirm={handleConfirmConfig} />
      </div>
    );
  },
});
