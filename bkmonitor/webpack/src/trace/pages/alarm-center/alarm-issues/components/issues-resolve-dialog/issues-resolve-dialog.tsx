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

import './issues-resolve-dialog.scss';

export default defineComponent({
  name: 'IssuesResolveDialog',
  props: {
    /** 弹窗是否显示 */
    isShow: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    confirm: () => true,
    cancel: () => true,
    'update:isShow': (val: boolean) => typeof val === 'boolean',
  },
  setup(_props, { emit }) {
    /**
     * @description 确认标记为已解决
     */
    const handleConfirm = () => {
      emit('confirm');
    };

    /**
     * @description 取消操作
     */
    const handleCancel = () => {
      emit('cancel');
    };

    return {
      handleConfirm,
      handleCancel,
    };
  },
  render() {
    return (
      <Dialog
        width={400}
        v-slots={{
          default: () => (
            <div class='issues-resolve-dialog-content'>
              <div class='resolve-icon-wrapper'>
                <i class='icon-monitor icon-tishi resolve-warning-icon' />
              </div>
              <div class='resolve-message'>{window.i18n.t('确认批量标记为"已解决"？')}</div>
            </div>
          ),
          footer: () => (
            <div class='issues-resolve-dialog-footer'>
              <Button
                style='margin-right: 8px'
                theme='primary'
                onClick={this.handleConfirm}
              >
                {window.i18n.t('确定')}
              </Button>
              <Button onClick={this.handleCancel}>{window.i18n.t('取消')}</Button>
            </div>
          ),
        }}
        headerPosition='left'
        isShow={this.isShow}
        showHead={false}
        onUpdate:isShow={(v: boolean) => {
          this.$emit('update:isShow', v);
        }}
      />
    );
  },
});
