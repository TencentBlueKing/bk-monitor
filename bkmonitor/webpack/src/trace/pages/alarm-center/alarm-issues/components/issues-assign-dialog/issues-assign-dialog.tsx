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

import { defineComponent, shallowRef, watch } from 'vue';

import { Button, Dialog, Input } from 'bkui-vue';

import './issues-assign-dialog.scss';

export default defineComponent({
  name: 'IssuesAssignDialog',
  props: {
    /** 弹窗是否显示 */
    isShow: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    confirm: (assignee: string[]) => Array.isArray(assignee),
    cancel: () => true,
    'update:isShow': (val: boolean) => typeof val === 'boolean',
  },
  setup(props, { emit }) {
    /** 指派负责人输入值 */
    const assignInputValue = shallowRef('');

    // 每次弹窗打开时清空输入值
    watch(
      () => props.isShow,
      val => {
        if (val) {
          assignInputValue.value = '';
        }
      }
    );

    /**
     * @description 确认指派
     */
    const handleConfirm = () => {
      const value = assignInputValue.value?.trim();
      if (!value) return;
      const assignees = value
        .split(',')
        .map(s => s.trim())
        .filter(Boolean);
      if (!assignees.length) return;
      emit('confirm', assignees);
    };

    /**
     * @description 取消指派
     */
    const handleCancel = () => {
      emit('cancel');
    };

    return {
      assignInputValue,
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
            <div class='issues-assign-dialog-content'>
              <div class='assign-field'>
                <span class='assign-label'>
                  {window.i18n.t('负责人')}
                  <span class='required'>*</span>
                </span>
                <Input
                  v-model={this.assignInputValue}
                  placeholder={window.i18n.t('请输入')}
                />
              </div>
            </div>
          ),
          footer: () => (
            <div class='issues-assign-dialog-footer'>
              <Button
                style='margin-right: 8px'
                disabled={!this.assignInputValue?.trim()}
                theme='primary'
                onClick={this.handleConfirm}
              >
                {window.i18n.t('确定')}
              </Button>
              <Button onClick={this.handleCancel}>{window.i18n.t('取消')}</Button>
            </div>
          ),
        }}
        header-position='left'
        isShow={this.isShow}
        title={window.i18n.t('指派负责人')}
        onUpdate:isShow={(v: boolean) => {
          this.$emit('update:isShow', v);
        }}
      />
    );
  },
});
