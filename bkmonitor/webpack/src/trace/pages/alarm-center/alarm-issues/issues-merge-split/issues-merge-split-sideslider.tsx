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

import { type PropType, defineComponent } from 'vue';

import { Sideslider } from 'bkui-vue';

import MergeContent from './components/merge-content';
import SplitContent from './components/split-content';

import type { IssueItem } from '../typing';

import './issues-merge-split-sideslider.scss';

/** 侧栏类型：合并或拆分 */
export type SidesliderType = 'merge' | 'split';

export default defineComponent({
  name: 'IssuesMergeSplitSideslider',
  props: {
    /** 是否显示侧栏 */
    show: {
      type: Boolean,
      default: true,
    },
    /** 侧栏类型：merge-合并，split-拆分 */
    type: {
      type: String as PropType<SidesliderType>,
      default: 'merge',
    },
    /** 已勾选的Issue */
    issues: {
      type: Array as PropType<IssueItem[]>,
      default: () => [],
    },
  },
  emits: ['update:show', 'mergeSuccess', 'splitSuccess'],
  setup(_, { emit }) {
    /** 处理侧栏显示状态变更 */
    const handleShowChange = (isShow: boolean) => {
      emit('update:show', isShow);
    };

    /** 处理合并成功 */
    const handleMergeSuccess = () => {
      emit('mergeSuccess');
    };

    /** 处理拆分成功 */
    const handleSplitSuccess = (memberIssueId: string) => {
      emit('splitSuccess', memberIssueId);
    };

    return {
      handleShowChange,
      handleMergeSuccess,
      handleSplitSuccess,
    };
  },
  render() {
    return (
      <Sideslider
        width={800}
        class='issues-merge-split-sideslider'
        isShow={this.show}
        render-directive='if'
        showMask={true}
        onUpdate:isShow={this.handleShowChange}
      >
        {{
          header: () => {
            if (this.type === 'merge') return <span class='header-title'>{this.$t('合并 Issue')}</span>;
            return (
              <div class='split-slider-header'>
                <span class='header-title'>{this.$t('合并明细')}</span>
                <span class='divider' />
                <span class='header-desc'>{this.issues[0]?.anomaly_message}</span>
              </div>
            );
          },
          default: () =>
            this.type === 'merge' ? (
              <MergeContent
                issues={this.issues}
                onClose={() => {
                  this.handleShowChange(false);
                }}
                onSuccess={this.handleMergeSuccess}
              />
            ) : (
              <SplitContent
                issues={this.issues}
                onSuccess={(memberIssueId: string) => {
                  this.handleShowChange(false);
                  this.handleSplitSuccess(memberIssueId);
                }}
              />
            ),
        }}
      </Sideslider>
    );
  },
});
