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

import { Button, Checkbox, Input } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { ISSUES_REGRESSION_MAP } from '../../constant';
import MergeStrategyTips from './merge-strategy-tips';
import MainIssueIcon from '@/static/img/main-Issue.svg';
import MergedIssueIcon from '@/static/img/merged-Issue.svg';

import type { IssueItem } from '../../typing';

import './merge-content.scss';

export default defineComponent({
  name: 'MergeContent',
  props: {
    defaultMainIssue: {
      type: Object as PropType<IssueItem>,
      default: () => null,
    },
    issues: {
      type: Array as PropType<IssueItem[]>,
      default: () => [],
    },
  },
  emits: ['close'],
  setup(props, { emit }) {
    const { t } = useI18n();

    /** 自定义主 Issue ID */
    const customMainIssueId = shallowRef('');
    /** 主 Issue */
    const mainIssue = computed(() => {
      /** 有默认主 Issue时，直接返回 */
      if (props.defaultMainIssue) return props.defaultMainIssue;
      /** 没有默认主 Issue时，根据自定义主 Issue ID 返回 */
      if (customMainIssueId.value) return props.issues.find(issue => issue.id === customMainIssueId.value);
      /** 没有自定义主 Issue ID时，返回第一个 Issue */
      return props.issues[0];
    });
    /** 被合并 Issue 列表 */
    const targetIssues = computed(() => {
      return props.issues.filter(issue => issue.id !== mainIssue.value.id);
    });

    /** 自定义合并依据 */
    const customReason = shallowRef('');

    /** 选中的合并依据 */
    const selectedReasons = shallowRef<string[]>([]);

    /** 合并依据选项列表 */
    const mergeReasonOptions = [
      { id: 'anomaly_type', label: t('异常类型 / 日志模块相近') },
      { id: 'message_similar', label: t('message 高度相似') },
      { id: 'stack_top', label: t('堆栈顶帧一致') },
      { id: 'service_related', label: t('服务或链路维度相关') },
      { id: 'time_near', label: t('时间窗口接近') },
      { id: 'log_cluster', label: t('日志聚类一致') },
      { id: 'manual_confirm', label: t('人工确认同根因') },
    ];

    const renderIssueItem = (issue: IssueItem, isMain: boolean) => {
      if (!issue) return null;
      const icon = ISSUES_REGRESSION_MAP[String(issue.is_regression)];
      return (
        <div class='issue-item'>
          <div class='issue-info-row'>
            <div class='issue-info'>
              <div
                style={{ color: icon.color, backgroundColor: icon.bgColor }}
                class='level-tag'
              >
                <i class={['icon-monitor', 'sign-icon', icon.icon]} />
              </div>
              <span class='issue-name'>{issue.name}</span>
              <span class='divider' />
              <span
                class='issue-desc'
                v-overflow-tips
              >
                {issue.anomaly_message}
              </span>
            </div>
            {/* 没有默认主 Issue且属于被合并issue 时，可以自定义设置主 Issue*/}
            {!isMain && !props.defaultMainIssue && (
              <Button
                size='small'
                theme='primary'
                outline
                onClick={() => {
                  customMainIssueId.value = issue.id;
                }}
              >
                {t('设为主 Issue')}
              </Button>
            )}
          </div>
          <div class='issue-metrics-row'>
            <span class='tag-item issues-alert-count'>
              <i class='icon-monitor icon-alert-line' />
              <span class='issues-alert-count-number'>{issue.alert_count}</span>
            </span>
            {Object.entries(issue.impact_scope ?? {}).map(([resourceKey, resource]) => (
              <div
                key={resourceKey}
                class='tag-item metric-item'
              >
                <div class='label'>{resource.display_name}</div>
                <div class='value'>{resource.count}</div>
              </div>
            ))}
          </div>
        </div>
      );
    };

    /** 处理确认 */
    const handleConfirm = () => {
      console.log('confirm');
      emit('close');
    };

    const handleClose = () => {
      console.log('cancel');
      emit('close');
    };

    return {
      mainIssue,
      targetIssues,
      customReason,
      selectedReasons,
      mergeReasonOptions,
      renderIssueItem,
      handleConfirm,
      handleClose,
    };
  },
  render() {
    return (
      <div class='merge-content'>
        {/* 合并策略提示 */}

        <div class='strategy-section'>
          <MergeStrategyTips hasMainIssue={Boolean(this.defaultMainIssue)} />
        </div>

        {/* 合并设置区域 */}
        <div class='settings-section'>
          <div class='section-title'>{this.$t('合并设置')}</div>
          <div class='issue-list'>
            <div class='issue-group main-issue'>
              <div class='issue-header'>
                <div class='group-icon'>
                  <img
                    alt={this.$t('主 Issue')}
                    src={MainIssueIcon}
                  />
                </div>
                <span class='issue-group-name'>{this.$t('主 Issue')}</span>
                <span class='divider' />
                <span class='issue-group-tips'>{this.$t('合并后保留')}</span>
              </div>
              <div class='issue-content'>{this.renderIssueItem(this.mainIssue, true)}</div>
            </div>

            {/* 被合并 Issue 列表 */}
            <div class='issue-group target-issue'>
              <div class='issue-header'>
                <div class='group-icon'>
                  <img
                    alt={this.$t('被合并 Issue')}
                    src={MergedIssueIcon}
                  />
                </div>
                <span class='issue-group-name'>{this.$t('被合并 Issue')}</span>
                <span class='divider' />
                <span class='issue-group-tips'>{this.$t('合并后隐藏')}</span>
              </div>
              <div class='issue-content'>{this.targetIssues.map(issue => this.renderIssueItem(issue, false))}</div>
            </div>
          </div>
        </div>

        {/* 合并依据区域 */}
        <div class='reason-section'>
          <div class='reason-section-header'>
            <div class='section-title'>{this.$t('合并依据')}</div>
            <span class='reason-tips'>
              <i class='icon-monitor icon-hint' />
              <span>{this.$t('由执行合并的用户指定，合并后会沉淀到主 Issue 的合并来源种，便于后续复盘。')}</span>
            </span>
          </div>
          <Checkbox.Group
            class='reason-checkbox-group'
            v-model={this.selectedReasons}
          >
            {this.mergeReasonOptions.map(option => (
              <Checkbox
                key={option.id}
                label={option.id}
              >
                {option.label}
              </Checkbox>
            ))}
          </Checkbox.Group>
          <Input
            class='custom-reason-input'
            v-model={this.customReason}
            placeholder={this.$t('自定义说明合并依据，例如：同一漏派发布后集中出现')}
          />
        </div>

        {/* 底部按钮区域 */}
        <div class='footer-section'>
          <Button
            theme='primary'
            onClick={this.handleConfirm}
          >
            {this.$t('确认合并')}
          </Button>
          <Button onClick={this.handleClose}>{this.$t('取消')}</Button>
        </div>
      </div>
    );
  },
});
