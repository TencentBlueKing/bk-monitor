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

import { defineComponent, type PropType, ref } from 'vue';

import './input-add-group.scss';

export default defineComponent({
  name: 'InputAddGroup',
  props: {
    valueList: {
      type: Array as PropType<{ value: string }[] | string[]>,
      default: () => [{ value: '' }],
    },
  },

  emits: ['update'],

  setup(props, { emit, expose }) {
    // 存储错误状态的索引数组（使用数组而不是 Set，以便 Vue 能追踪变化）
    const errorIndexes = ref<number[]>([]);

    // 规范化数据格式：将字符串数组转换为对象数组
    const normalizeValueList = (list: { value: string }[] | string[]): { value: string }[] => {
      return list.map(item => (typeof item === 'string' ? { value: item } : item));
    };

    const handleAdd = () => {
      const normalizedList = normalizeValueList(props.valueList);
      emit('update', [...normalizedList, { value: '' }]);
      // 清除新增项的错误状态（新增项在最后，不需要处理）
    };
    /**
     * 新增
     */
    const handleChange = (index: number, val: string) => {
      const normalizedList = normalizeValueList(props.valueList);
      const nextList = [...normalizedList];
      nextList[index].value = String(val);
      emit('update', nextList);
      // 如果输入了值，清除该索引的错误状态
      if (val && String(val).trim()) {
        errorIndexes.value = errorIndexes.value.filter(i => i !== index);
      }
    };
    /**
     * 删除（删到只有 1 行时，此时是清空 input 的交互）
     */
    const handleDel = (index: number) => {
      const normalizedList = normalizeValueList(props.valueList);
      const nextList = [...normalizedList];
      if (nextList.length > 1) {
        nextList.splice(index, 1);
        // 更新错误索引（删除后索引会变化）
        errorIndexes.value = errorIndexes.value
          .filter(errorIndex => errorIndex !== index)
          .map(errorIndex => (errorIndex > index ? errorIndex - 1 : errorIndex));
      } else {
        nextList[0].value = '';
        errorIndexes.value = [];
      }
      emit('update', nextList);
    };

    /**
     * 校验方法
     * @returns {boolean} 校验是否通过
     */
    const validate = (): boolean => {
      // 清除之前的错误状态
      errorIndexes.value = [];

      const normalizedList = normalizeValueList(props.valueList);

      // 检查长度是否为0
      if (normalizedList.length === 0) {
        return false;
      }

      // 检查是否有空值
      const emptyIndexes: number[] = [];
      normalizedList.forEach((item, index) => {
        const isEmpty = !item.value || !item.value.trim();
        if (isEmpty) {
          emptyIndexes.push(index);
        }
      });

      // 更新错误索引
      errorIndexes.value = emptyIndexes;

      return emptyIndexes.length === 0;
    };

    // 暴露校验方法给父组件
    expose({
      validate,
    });

    const renderInputItem = (item: { value: string }, index: number) => {
      const isError = errorIndexes.value.includes(index);
      return (
        <div class='input-add-group-item'>
          <bk-input
            value={item.value}
            class={isError ? 'input-error' : ''}
            onInput={(val: string) => handleChange(index, val)}
          />
          <span
            class='bk-icon icon-plus-circle-shape icons'
            on-Click={handleAdd}
          />
          <span
            class={{
              'bk-icon icon-minus-circle-shape icons': true,
              disabled: props.valueList.length === 1,
            }}
            on-Click={() => handleDel(index)}
          />
        </div>
      );
    };
    return () => {
      const normalizedList = normalizeValueList(props.valueList);
      return (
        <div class='input-add-group-main'>
          {normalizedList.map((item: { value: string }, index: number) => renderInputItem(item, index))}
        </div>
      );
    };
  },
});
