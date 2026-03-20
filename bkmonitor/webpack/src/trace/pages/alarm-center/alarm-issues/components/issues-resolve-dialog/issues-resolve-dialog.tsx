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

import { mockResolveIssues } from '../../issues-table/mock-data';

import type { IssuesBatchActionEnum } from '../../constant';
import type { IssuesOperationDialogEvent } from '../../typing';

import './issues-resolve-dialog.scss';

export default defineComponent({
  name: 'IssuesResolveDialog',
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
    /** 提示内容 */
    tip: {
      type: String,
    },
  },
  emits: {
    success: (event: IssuesOperationDialogEvent<typeof IssuesBatchActionEnum.RESOLVE>) => event != null,
    cancel: () => true,
    'update:isShow': (val: boolean) => typeof val === 'boolean',
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    /** 提交中 loading 状态 */
    const loading = shallowRef(false);

    /**
     * @description 获取提示内容
     * @returns { string } 提示内容
     */
    const getTip = () => {
      if (props.tip) return props.tip;
      if (props.issuesIds?.length > 1) return window.i18n.t('确认批量标记为"已解决"？');
      return window.i18n.t('确认标记为"已解决"？');
    };

    /**
     * @description 确认标记为已解决
     */
    const handleConfirm = async () => {
      loading.value = true;

      // TODO: 标记已解决请求接口及处理结果提示 待完善
      const res = await mockResolveIssues({
        bk_biz_id: props.issuesBizId,
        issue_ids: props.issuesIds,
      });

      let msg = {
        theme: 'success',
        message: t('标记成功'),
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
     * @description 取消操作
     */
    const handleCancel = () => {
      if (loading.value) return;
      emit('cancel');
    };

    // 每次弹窗打开时重置 loading
    watch(
      () => props.isShow,
      val => {
        if (val) {
          loading.value = false;
        }
      }
    );

    return {
      loading,
      getTip,
      handleConfirm,
      handleCancel,
    };
  },
  render() {
    return (
      <Dialog
        width={400}
        class='issues-resolve-dialog'
        v-slots={{
          default: () => (
            <div class='issues-resolve-dialog-content'>
              <div class='resolve-icon-wrapper'>
                <span class='resolve-icon'>!</span>
              </div>
              <div class='resolve-message'>{this.getTip()}</div>
              <div class='resolve-operations'>
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
