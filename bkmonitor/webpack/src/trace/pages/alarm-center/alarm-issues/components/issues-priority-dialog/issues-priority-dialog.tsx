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

import { Button, Dialog, Message, Radio } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { IssuePriorityEnum, IssuesPriorityMap } from '../../constant';
import { mockUpdatePriority } from '../../issues-table/mock-data';

import type { IssuesBatchActionEnum } from '../../constant';
import type { IssuePriorityType, IssuesOperationDialogEvent, IssuesOperationDialogParams } from '../../typing';

import './issues-priority-dialog.scss';

/** 优先级选项列表 */
const PRIORITY_OPTIONS: IssuePriorityType[] = [IssuePriorityEnum.P0, IssuePriorityEnum.P1, IssuePriorityEnum.P2];

export default defineComponent({
  name: 'IssuesPriorityDialog',
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
    /** dialog 私有参数（用于回填当前优先级） */
    dialogParam: {
      type: Object as PropType<IssuesOperationDialogParams>,
    },
    /** 弹窗标题 */
    title: {
      type: String,
    },
  },
  emits: {
    success: (event: IssuesOperationDialogEvent<typeof IssuesBatchActionEnum.PRIORITY>) => event != null,
    cancel: () => true,
    'update:isShow': (val: boolean) => typeof val === 'boolean',
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    /** 当前选中的优先级 */
    const selectedPriority = shallowRef<'' | IssuePriorityType>('');
    /** 提交中 loading 状态 */
    const loading = shallowRef(false);

    /**
     * @description 获取弹窗标题
     * @returns { string } 弹窗标题
     */
    const getTitle = () => {
      if (props.title) return props.title;
      if (props.issuesIds?.length > 1) return window.i18n.t('批量修改优先级');
      return window.i18n.t('修改优先级');
    };

    /**
     * @description 确认修改优先级
     */
    const handleConfirm = async () => {
      if (!selectedPriority.value) return;
      loading.value = true;

      // TODO: 修改优先级请求接口及处理结果提示 待完善
      const res = await mockUpdatePriority({
        bk_biz_id: props.issuesBizId,
        issue_ids: props.issuesIds,
        priority: selectedPriority.value as IssuePriorityType,
      });

      let msg = {
        theme: 'success',
        message: t('修改成功'),
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
     * @description 取消修改优先级
     */
    const handleCancel = () => {
      if (loading.value) return;
      emit('cancel');
    };

    // 每次弹窗打开时，若 dialogParam 含 priority 则回填，否则重置
    watch(
      () => props.isShow,
      val => {
        if (val) {
          selectedPriority.value = props.dialogParam?.priority || '';
          loading.value = false;
        }
      }
    );

    return {
      selectedPriority,
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
        class='issues-priority-dialog'
        v-slots={{
          default: () => (
            <div class='issues-priority-dialog-content'>
              <div class='priority-field'>
                <span class='priority-label'>
                  {window.i18n.t('优先级')}
                  <span class='required'>*</span>
                </span>
                <Radio.Group
                  class='priority-radio-group'
                  modelValue={this.selectedPriority}
                  onChange={(val: IssuePriorityType) => {
                    this.selectedPriority = val;
                  }}
                >
                  {PRIORITY_OPTIONS.map(priority => {
                    const config = IssuesPriorityMap[priority];
                    return (
                      <Radio
                        key={priority}
                        label={priority}
                      >
                        <span
                          style={{
                            backgroundColor: config.bgColor,
                            color: config.color,
                          }}
                          class='priority-tag'
                        >
                          {config.alias}
                        </span>
                      </Radio>
                    );
                  })}
                </Radio.Group>
              </div>
            </div>
          ),
          footer: () => (
            <div class='issues-priority-dialog-footer'>
              <Button
                disabled={!this.selectedPriority || this.loading}
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
        header-position='left'
        isShow={this.isShow}
        title={this.getTitle()}
        onUpdate:isShow={(v: boolean) => {
          if (this.loading) return;
          this.$emit('update:isShow', v);
        }}
      />
    );
  },
});
