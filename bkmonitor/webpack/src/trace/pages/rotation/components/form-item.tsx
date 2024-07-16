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
import { type PropType, defineComponent } from 'vue';

import './form-item.scss';

export default defineComponent({
  name: 'RotationFormItem',
  props: {
    errMsg: {
      type: String,
      default: '',
    },
    label: {
      type: String as PropType<any>,
      default: '',
    },
    labelWidth: {
      type: Number,
      default: 135,
    },
    require: {
      type: Boolean,
      default: false,
    },
    hasColon: {
      type: Boolean,
      default: false,
    },
    contentCls: {
      type: String,
      default: '',
    },
  },
  setup(props, { slots }) {
    return () => (
      <div class='rotation-config-form-item'>
        <div
          style={{ minWidth: `${props.labelWidth}px` }}
          class={['form-item-label', { require: !!props.require }]}
        >
          {props.label}
          {props.hasColon ? ' : ' : undefined}
        </div>
        <div class={['form-item-content', props.contentCls]}>
          {slots?.default?.()}
          {!!props?.errMsg && <div class='form-item-errmsg'>{props.errMsg}</div>}
        </div>
      </div>
    );
  },
});
