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

import './confirm-action-bar.scss';

export default defineComponent({
  name: 'ConfirmActionBar',
  props: {
    /** 取消按钮回调 */
    onCancel: {
      type: Function as PropType<() => void>,
    },
    /** 确认按钮回调 */
    onConfirm: {
      type: Function as PropType<() => void>,
      required: true,
    },
    /** 二次确认弹窗标题 */
    title: {
      type: String,
      required: true,
    },
  },
  emits: {
    close: () => true,
  },
  setup(props, { emit }) {
    /**
     * @description 处理确认按钮点击
     * @returns {void}
     */
    const handleConfirm = () => {
      props.onConfirm();
      emit('close');
    };

    /**
     * @description 处理取消按钮点击
     * @returns {void}
     */
    const handleCancel = () => {
      props.onCancel?.();
      emit('close');
    };

    return { handleCancel, handleConfirm };
  },
  render() {
    return (
      <div class='confirm-action-bar'>
        <div class='confirm-action-bar-title'>{this.title}</div>
        <div class='confirm-action-bar-actions'>
          <button
            class='bk-button bk-button-primary bk-button-small'
            type='button'
            onClick={this.handleConfirm}
          >
            {window.i18n.t('确定')}
          </button>
          <button
            class='bk-button bk-button-small'
            type='button'
            onClick={this.handleCancel}
          >
            {window.i18n.t('取消')}
          </button>
        </div>
      </div>
    );
  },
});
