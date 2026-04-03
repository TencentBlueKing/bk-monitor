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

import { type PropType, defineComponent, shallowRef, toRef, watch } from 'vue';

import { Button, Dialog } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import UserSelector from '../../../../../components/user-selector/user-selector';
import { useAsyncDialog } from '../../hooks/use-async-dialog';

import type { AsyncDialogConfirmEvent } from '../../hooks/use-async-dialog';
import type { IssueIdentifier } from '../../typing';

import './issues-assign-dialog.scss';

export default defineComponent({
  name: 'IssuesAssignDialog',
  props: {
    /** 弹窗是否显示 */
    isShow: {
      type: Boolean,
      default: false,
    },
    /** 跨业务批量操作 Issue 标识数据 */
    issuesData: {
      type: Array as PropType<IssueIdentifier[]>,
      default: () => [],
    },
    /** 弹窗标题 */
    title: {
      type: String,
    },
  },
  emits: {
    confirm: (_event: AsyncDialogConfirmEvent<{ assignee: string[] }>) => _event != null,
    cancel: () => true,
    'update:isShow': (_val: boolean) => typeof _val === 'boolean',
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    /** 指派负责人选中值 */
    const assignInputValue = shallowRef<string[]>([]);

    const {
      loading,
      handleConfirm: createConfirmEvent,
      handleCancel: internalCancel,
    } = useAsyncDialog({
      isShow: toRef(() => props.isShow),
      onShowChange: (val: boolean) => emit('update:isShow', val),
    });

    /**
     * @description 获取弹窗标题
     * @returns {string} 弹窗标题
     */
    const getTitle = () => {
      if (props.title) return props.title;
      if (props.issuesData?.length > 1) return t('批量指派负责人');
      return t('指派负责人');
    };

    /**
     * @description 确认指派——通过 useAsyncDialog 创建 { resolve, reject } 事件对象并 emit 给调用方
     * @returns {void}
     */
    const handleConfirm = () => {
      const assignees = assignInputValue.value;
      if (!assignees?.length) return;
      const event = createConfirmEvent({ assignee: assignees });
      emit('confirm', event);
    };

    /**
     * @description 取消指派
     * @returns {void}
     */
    const handleCancel = () => {
      if (!internalCancel()) return;
      emit('cancel');
    };

    // 每次弹窗打开时清空输入值
    watch(
      () => props.isShow,
      val => {
        if (val) {
          assignInputValue.value = [];
        }
      }
    );

    return {
      t,
      assignInputValue,
      loading,
      getTitle,
      handleConfirm,
      handleCancel,
    };
  },
  render() {
    return (
      <Dialog
        width={480}
        class='issues-assign-dialog'
        v-slots={{
          header: () => (
            <div class='issues-assign-dialog-header'>
              <span class='issues-assign-dialog-title'>{this.getTitle()}</span>
            </div>
          ),
          default: () => (
            <div class='issues-assign-dialog-content'>
              <div class='assign-field'>
                <span class='assign-label'>
                  {this.t('负责人')}
                  <span class='required'>*</span>
                </span>
                <UserSelector
                  disabled={this.loading}
                  modelValue={this.assignInputValue}
                  placeholder={this.t('请输入')}
                  onUpdate:modelValue={(val: string[]) => {
                    this.assignInputValue = val;
                  }}
                />
              </div>
            </div>
          ),
          footer: () => (
            <div class='issues-assign-dialog-footer'>
              <Button
                disabled={!this.assignInputValue?.length || this.loading}
                loading={this.loading}
                theme='primary'
                onClick={this.handleConfirm}
              >
                {this.t('确定')}
              </Button>
              <Button
                disabled={this.loading}
                onClick={this.handleCancel}
              >
                {this.t('取消')}
              </Button>
            </div>
          ),
        }}
        isShow={this.isShow}
        onUpdate:isShow={(v: boolean) => {
          if (this.loading) return;
          this.$emit('update:isShow', v);
        }}
      />
    );
  },
});
