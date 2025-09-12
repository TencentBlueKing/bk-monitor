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

export default defineComponent({
  name: 'ValidateInput',
  props: {
    // 输入值
    value: {
      type: String,
      default: '',
    },
    // 占位符
    placeholder: {
      type: String,
      default: '',
    },
    // 校验函数
    validator: {
      type: Function,
      default: val => Boolean(val),
    },
    onChange: { type: Function },
  },
  emits: ['change'],

  setup(props, { emit }) {
    const isError = ref(false); // 是否显示错误状态

    // 处理输入变化
    const handleChange = (val: string) => {
      emit('change', val);
    };

    // 文本框失焦时校验
    const handleBlur = (val: string) => {
      const validator = props.validator as (newVal: string) => boolean;
      isError.value = !validator(val);
    };

    return () => (
      <div class='validate-input'>
        <bk-input
          class={isError.value ? 'is-error' : ''}
          placeholder={props.placeholder}
          value={props.value}
          onBlur={handleBlur}
          onChange={handleChange}
        />
      </div>
    );
  },
});
