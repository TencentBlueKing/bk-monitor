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

import { type PropType, defineComponent, toRef } from 'vue';

import { Button, Dialog } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { useAsyncDialog } from '../../hooks/use-async-dialog';

import type { AsyncDialogConfirmEvent } from '../../hooks/use-async-dialog';
import type { IssueIdentifier } from '../../typing';

import './issues-resolve-dialog.scss';

export default defineComponent({
  name: 'IssuesResolveDialog',
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
    /** 提示内容 */
    tip: {
      type: String,
    },
  },
  emits: {
    confirm: (_event: AsyncDialogConfirmEvent) => _event != null,
    cancel: () => true,
    'update:isShow': (_val: boolean) => typeof _val === 'boolean',
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const {
      loading,
      handleConfirm: createConfirmEvent,
      handleCancel: internalCancel,
    } = useAsyncDialog({
      isShow: toRef(() => props.isShow),
      onShowChange: (val: boolean) => emit('update:isShow', val),
    });

    /**
     * @description 获取提示内容
     * @returns {string} 提示内容
     */
    const getTip = () => {
      if (props.tip) return props.tip;
      if (props.issuesData?.length > 1) return t('确认批量标记为"已解决"？');
      return t('确认标记为“已解决”？');
    };

    /**
     * @description 确认操作——通过 useAsyncDialog 创建 { resolve, reject } 事件对象并 emit 给调用方
     * @returns {void}
     */
    const handleConfirm = () => {
      const event = createConfirmEvent();
      emit('confirm', event);
    };

    /**
     * @description 取消操作
     * @returns {void}
     */
    const handleCancel = () => {
      if (!internalCancel()) return;
      emit('cancel');
    };

    return {
      t,
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
                  {this.t('确定')}
                </Button>
                <Button
                  disabled={this.loading}
                  onClick={this.handleCancel}
                >
                  {this.t('取消')}
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
