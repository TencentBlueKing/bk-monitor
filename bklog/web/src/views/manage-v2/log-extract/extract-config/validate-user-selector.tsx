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

import { defineComponent, ref } from 'vue';

import BkUserSelector from '@blueking/user-selector';

import './validate-user-selector.scss';

export default defineComponent({
  name: 'ValidateUserSelector',
  components: {
    BkUserSelector,
  },
  props: {
    // 输入值
    value: {
      type: Array,
      default: () => [],
    },
    // 占位符
    placeholder: {
      type: String,
      default: '',
    },
    // API 地址
    api: {
      type: String,
      default: '',
    },
    // 是否禁用
    disabled: {
      type: Boolean,
      default: false,
    },
    onChange: { type: Function },
  },
  emits: ['change', 'update'],

  setup(props, { emit }) {
    const isError = ref(false); // 是否显示错误状态

    // 处理选择变化
    const handleChange = (val: any[]) => {
      const realVal = val.filter(item => item !== undefined);
      isError.value = !realVal.length;
      emit('change', realVal);
      emit('update', realVal);
    };

    // 失焦时校验
    const handleBlur = () => {
      isError.value = !props.value.length;
    };

    return () => (
      <div class='validate-user-selector'>
        <BkUserSelector
          style='width: 400px'
          class={isError.value ? 'is-error' : ''}
          api={props.api}
          disabled={props.disabled}
          empty-text='无匹配人员'
          placeholder={props.placeholder}
          value={props.value}
          onBlur={handleBlur}
          onChange={handleChange}
        />
      </div>
    );
  },
});
