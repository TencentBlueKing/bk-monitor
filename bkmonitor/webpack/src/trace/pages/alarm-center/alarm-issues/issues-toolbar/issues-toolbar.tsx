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

import { type PropType, computed, defineComponent, shallowRef } from 'vue';

import BkButton from 'bkui-vue/lib/button';
import BkDropdown, { BkDropdownItem, BkDropdownMenu } from 'bkui-vue/lib/dropdown';
import { useI18n } from 'vue-i18n';

import { IssuesBatchActionEnum } from '../constant';

import type { IssuesBatchActionType } from '../typing';

import './issues-toolbar.scss';

export default defineComponent({
  name: 'IssuesToolbar',
  props: {
    /** 选中行的 issues Id 数组*/
    issuesIds: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    /** 批量操作回调，返回 false 表示操作失败被拦截（如校验失败），此时不关闭 dropdown */
    batchAction: {
      type: Function as PropType<(action: IssuesBatchActionType) => boolean | undefined>,
    },
    /* 导出异步回调，返回 Promise 以便内部自动管理 loading 状态 */
    /* onExport: {
      type: Function as PropType<() => Promise<void>>,
    }, */
  },
  setup(props) {
    const { t } = useI18n();

    /** 批量操作下拉菜单是否展开 */
    const dropdownShow = shallowRef(false);

    /* 导出按钮 loading 状态 */
    /* const exportLoading = shallowRef(false); */

    /** 是否有选中行 */
    const hasSelection = computed(() => props.issuesIds.length > 0);

    /** 批量操作下拉菜单项 */
    const batchActions = computed(() => [
      {
        id: IssuesBatchActionEnum.ASSIGN,
        label: t('指派负责人'),
      },
      {
        id: IssuesBatchActionEnum.RESOLVE,
        label: t('标记为已解决'),
      },
      {
        id: IssuesBatchActionEnum.PRIORITY,
        label: t('修改优先级'),
      },
      {
        id: IssuesBatchActionEnum.FOLLOW_UP,
        label: t('添加跟进信息'),
      },
    ]);

    /**
     * @description 处理批量操作下拉选择，调用回调后根据返回值决定是否关闭 dropdown
     * @param {IssuesBatchActionType} action - 选中的批量操作类型
     */
    const handleBatchAction = (action: IssuesBatchActionType) => {
      const execStatus = props.batchAction?.(action);
      if (typeof execStatus === 'boolean' && execStatus !== false) {
        dropdownShow.value = false;
      }
    };

    /**
     * @description 处理导出按钮点击，内部管理 loading 状态，通过 prop callback 将业务逻辑委托给父组件
     * @returns {Promise<void>}
     */
    /* const handleExport = async () => {
      if (exportLoading.value) return;
      exportLoading.value = true;
      try {
        await props.onExport?.();
      } finally {
        exportLoading.value = false;
      }
    }; */

    return {
      dropdownShow,
      /* exportLoading, */
      hasSelection,
      batchActions,
      handleBatchAction,
      /* handleExport, */
    };
  },
  render() {
    return (
      <div class='issues-toolbar'>
        {/* 顶部工具栏 */}
        <div class='issues-toolbar-bar'>
          <BkDropdown
            isShow={this.dropdownShow}
            trigger='click'
            onHide={() => {
              this.dropdownShow = false;
            }}
            onShow={() => {
              this.dropdownShow = true;
            }}
          >
            {{
              default: () => (
                <BkButton
                  class='issues-toolbar-batch-btn'
                  disabled={!this.hasSelection}
                  theme='primary'
                >
                  <div class='issues-toolbar-batch-btn-wrap'>
                    <span class='issues-toolbar-batch-btn-text'>{this.$t('批量操作')}</span>
                    <i class={['icon-monitor icon-arrow-down toolbar-btn-icon', { 'is-active': this.dropdownShow }]} />
                  </div>
                </BkButton>
              ),
              content: () => (
                <BkDropdownMenu>
                  {this.batchActions.map(action => (
                    <BkDropdownItem
                      key={action.id}
                      onClick={() => this.handleBatchAction(action.id)}
                    >
                      {action.label}
                    </BkDropdownItem>
                  ))}
                </BkDropdownMenu>
              ),
            }}
          </BkDropdown>
          {/* <BkButton
            class='issues-toolbar-export-btn'
            disabled={!this.hasSelection}
            loading={this.exportLoading}
            onClick={this.handleExport}
          >
            <span class='toolbar-btn-text'>{this.$t('导出')}</span>
          </BkButton> */}
        </div>

        {/* 表格区域：通过 default slot 注入 */}
        <div class='issues-toolbar-content'>{this.$slots.default?.()}</div>
      </div>
    );
  },
});
