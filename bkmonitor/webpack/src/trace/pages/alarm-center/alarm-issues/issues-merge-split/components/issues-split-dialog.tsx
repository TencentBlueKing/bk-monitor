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

import { type PropType, defineComponent, shallowRef } from 'vue';

import { Button, Dialog, Message } from 'bkui-vue';
import dayjs from 'dayjs';
import { useI18n } from 'vue-i18n';

import { splitIssues } from '../../services/issues-operations';
import IssueInfoItem from './issue-info-item';
import ReasonSection from './reason-section';

import type { MergeSourceActiveMember } from '../../typing';

import './issues-split-dialog.scss';

export default defineComponent({
  name: 'IssuesSplitDialog',
  props: {
    bizId: {
      type: [Number, String],
      default: null,
    },
    /** 是否显示 */
    isShow: {
      type: Boolean,
      default: false,
    },
    /** 当前 Issue */
    issue: {
      type: Object as PropType<MergeSourceActiveMember>,
      default: () => null,
    },
  },
  emits: ['update:isShow', 'success'],
  setup(props, { emit }) {
    const { t } = useI18n();

    /** 拆分依据选项 */
    const splitReasonOptions = [
      t('误合并，根因不同'),
      t('影响范围不同'),
      t('责任 Owner 不同'),
      t('修复方案不同'),
      t('后续复盘需要独立跟踪'),
    ];

    const selectReason = shallowRef<string[]>([]);
    const inputReason = shallowRef('');

    const handleSelectReasonChange = (value: string[]) => {
      selectReason.value = value;
    };

    const handleInputReasonChange = (value: string) => {
      inputReason.value = value;
    };

    /** 获取 metric 列表 */
    const getMetricList = (issue: MergeSourceActiveMember) => issue.merge_reasons.map(reason => reason);

    const submitLoading = shallowRef(false);

    /** 处理确认拆分 */
    const handleConfirm = () => {
      submitLoading.value = true;
      const reasons = inputReason.value ? [...selectReason.value, inputReason.value] : selectReason.value;
      splitIssues({
        bk_biz_id: +props.bizId,
        member_issue_id: props.issue.member_issue_id,
        reasons,
      })
        .then(() => {
          Message({
            theme: 'success',
            message: t('已拆分为独立 Issue'),
          });
          handleShowChange(false);
          emit('success', props.issue.member_issue_id);
        })
        .finally(() => {
          submitLoading.value = false;
        });
    };

    const handleShowChange = (show: boolean) => {
      emit('update:isShow', show);
    };

    return {
      selectReason,
      inputReason,
      splitReasonOptions,
      submitLoading,
      getMetricList,
      handleSelectReasonChange,
      handleInputReasonChange,
      handleConfirm,
      handleShowChange,
    };
  },
  render() {
    return (
      <Dialog
        width={640}
        class='issues-split-dialog'
        isShow={this.isShow}
        title={this.$t('拆分为新 Issue')}
        onUpdate:isShow={this.handleShowChange}
      >
        {{
          default: () => (
            <div class='split-dialog-content'>
              {/* Issue 信息展示 */}
              {this.issue && (
                <div class='issue-preview-section'>
                  <IssueInfoItem
                    v-slots={{
                      suffix: () => (
                        <span class='operate-record'>{`${this.issue.merge_operator} · ${dayjs(this.issue.merge_time * 1000).format('YYYY-MM-DD HH:mm')}`}</span>
                      ),
                    }}
                    desc={this.issue.anomaly_message}
                    list={this.getMetricList(this.issue)}
                    name={this.issue.member_name}
                  />
                </div>
              )}

              {/* 拆分依据区域 */}
              <ReasonSection
                inputValue={this.inputReason}
                options={this.splitReasonOptions}
                placeholder={this.$t('自定义拆分依据，例如：同一蓝盾发布后集中出现')}
                selectValue={this.selectReason}
                tips={this.$t('选择或填写拆分依据后，再确认拆分为新 Issue。')}
                title={this.$t('拆分依据')}
                onInput={this.handleInputReasonChange}
                onSelectChange={this.handleSelectReasonChange}
              />
            </div>
          ),
          footer: () => (
            <div class='dialog-footer'>
              <Button
                class='confirm-btn'
                loading={this.submitLoading}
                theme='primary'
                onClick={this.handleConfirm}
              >
                {this.$t('确认拆分')}
              </Button>
              <Button
                onClick={() => {
                  this.handleShowChange(false);
                }}
              >
                {this.$t('取消')}
              </Button>
            </div>
          ),
        }}
      </Dialog>
    );
  },
});
