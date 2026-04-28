/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { Button, Dialog } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import './double-confirm-dialog.scss';

export default defineComponent({
  name: 'DoubleConfirmDialog',
  props: {
    /** 弹窗是否显示 */
    isShow: {
      type: Boolean,
      default: false,
    },
    /** 提示内容 */
    tip: {
      type: String,
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    confirm: () => true,
    cancel: () => true,
    'update:isShow': (val: boolean) => typeof val === 'boolean',
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    /**
     * @description 获取提示内容
     * @returns { string } 提示内容
     */
    const getTip = () => {
      if (props.tip) return props.tip;
      return t('是否确认进行该操作');
    };

    /**
     * @description 确认标记为已解决
     */
    const handleConfirm = async () => {
      if (props.loading) return;
      emit('confirm');
    };

    /**
     * @description 取消操作
     */
    const handleCancel = () => {
      if (props.loading) return;
      emit('cancel');
    };

    return {
      getTip,
      handleConfirm,
      handleCancel,
    };
  },
  render() {
    return (
      <Dialog
        width={400}
        class='double-confirm-dialog'
        v-slots={{
          default: () => (
            <div class='double-confirm-dialog-content'>
              <div class='tips-icon-wrapper'>
                <span class='tips-icon'>!</span>
              </div>
              <div class='tips-message'>{this.getTip()}</div>
              <div class='tips-operations'>
                <Button
                  loading={this.loading}
                  theme='primary'
                  onClick={this.handleConfirm}
                >
                  {window.i18n.t('确定')}
                </Button>
                <Button
                  disabled={this.loading}
                  onClick={this.handleCancel}
                >
                  {window.i18n.t('取消')}
                </Button>
              </div>
            </div>
          ),
        }}
        dialogType='show'
        isShow={this.isShow}
        onUpdate:isShow={(v: boolean) => {
          if (this.loading) return;
          this.$emit('update:isShow', v);
        }}
      />
    );
  },
});
