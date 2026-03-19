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

import { type PropType, defineComponent, shallowRef, watch } from 'vue';

import { Button, Dialog, Message } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import UserSelector from '../../../../../components/user-selector/user-selector';
import { mockAssignIssues } from '../../issues-table/mock-data';

import type { IssuesBatchActionEnum } from '../../constant';
import type { IssuesOperationDialogEvent } from '../../typing';

import './issues-assign-dialog.scss';

export default defineComponent({
  name: 'IssuesAssignDialog',
  props: {
    /** 弹窗是否显示 */
    isShow: {
      type: Boolean,
      default: false,
    },
    /** 空间业务id */
    issuesBizId: {
      type: Number,
    },
    /** 当前操作的 Issues ID 列表 */
    issuesIds: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    /** 弹窗标题 */
    title: {
      type: String,
    },
  },
  emits: {
    success: (event: IssuesOperationDialogEvent<typeof IssuesBatchActionEnum.ASSIGN>) => event != null,
    cancel: () => true,
    'update:isShow': (val: boolean) => typeof val === 'boolean',
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    /** 指派负责人选中值 */
    const assignInputValue = shallowRef<string[]>([]);
    /** 提交中 loading 状态 */
    const loading = shallowRef(false);

    /**
     * @description 获取弹窗标题
     * @returns { string } 弹窗标题
     */
    const getTitle = () => {
      if (props.title) return props.title;
      if (props.issuesIds?.length > 1) return window.i18n.t('批量指派负责人');
      return window.i18n.t('指派负责人');
    };

    /**
     * @description 确认指派
     */
    const handleConfirm = async () => {
      const assignees = assignInputValue.value;
      if (!assignees?.length) return;
      loading.value = true;

      // TODO: 指派责任人请求接口及处理结果提示 待完善
      const res = await mockAssignIssues({
        bk_biz_id: props.issuesBizId,
        issue_ids: props.issuesIds,
        assignee: assignees,
      });

      let msg = {
        theme: 'success',
        message: t('指派责任人成功'),
      };
      if (res.failed?.length) {
        msg = {
          theme: 'error',
          message: res.failed?.[0]?.message,
        };
      }

      emit('success', res);
      Message(msg);
    };

    /**
     * @description 取消指派
     */
    const handleCancel = () => {
      if (loading.value) return;
      emit('cancel');
    };

    // 每次弹窗打开时清空输入值
    watch(
      () => props.isShow,
      val => {
        if (val) {
          assignInputValue.value = [];
          loading.value = false;
        }
      }
    );

    return {
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
                  {window.i18n.t('负责人')}
                  <span class='required'>*</span>
                </span>
                <UserSelector
                  disabled={this.loading}
                  modelValue={this.assignInputValue}
                  placeholder={window.i18n.t('请输入')}
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
                {window.i18n.t('确定')}
              </Button>
              <Button
                disabled={this.loading}
                onClick={this.handleCancel}
              >
                {window.i18n.t('取消')}
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
