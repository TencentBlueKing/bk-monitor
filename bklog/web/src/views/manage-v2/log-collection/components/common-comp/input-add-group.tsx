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

import { defineComponent } from 'vue';

import './input-add-group.scss';

export default defineComponent({
  name: 'InputAddGroup',
  props: {
    valueList: {
      type: Array,
      default: () => [''],
    },
  },

  emits: ['update'],

  setup(props, { emit }) {
    const handleAdd = () => {
      emit('update', [...props.valueList, '']);
    };
    /**
     * 新增
     */
    const handleChange = (index: number, val: any) => {
      const nextList = [...props.valueList];
      nextList[index] = String(val);
      emit('update', nextList);
    };
    /**
     * 删除（删到只有 1 行时，此时是清空 input 的交互）
     */
    const handleDel = (index: number) => {
      const nextList = [...props.valueList];
      if (nextList.length > 1) {
        nextList.splice(index, 1);
      } else {
        nextList[0] = '';
      }
      emit('update', nextList);
    };
    const renderInputItem = (item: string, index: number) => (
      <div class='input-add-group-item'>
        <bk-input
          value={item}
          onInput={(val: any) => handleChange(index, val)}
        />
        <span
          class='bk-icon icon-plus-circle-shape icons'
          on-Click={handleAdd}
        />
        <span
          class='bk-icon icon-minus-circle-shape icons'
          on-Click={() => handleDel(index)}
        />
      </div>
    );
    return () => (
      <div class='input-add-group-main'>
        {props.valueList.map((item: string, index: number) => renderInputItem(item, index))}
      </div>
    );
  },
});
