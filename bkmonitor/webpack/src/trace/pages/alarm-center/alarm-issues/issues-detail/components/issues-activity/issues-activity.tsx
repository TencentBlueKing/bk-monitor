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
import { type PropType, defineComponent, nextTick, shallowRef, useTemplateRef, watch } from 'vue';

import { Button, Dialog, Input, Message } from 'bkui-vue';
import dayjs from 'dayjs';
import { listIssueActivities } from 'monitor-api/modules/issue';
import { useI18n } from 'vue-i18n';

import MarkdownEditor from '../../../../../../components/markdown-editor/editor';
import MarkdownViewer from '../../../../../../components/markdown-editor/viewer';
import {
  IssueActiveNodeTypeEnum,
  ISSUES_ACTIVE_NODE_ICON_MAP,
  ISSUES_PRIORITY_MAP,
  ISSUES_STATUS_MAP,
} from '../../../constant';
import { followUpIssues } from '../../../services/issues-operations';
import BasicCard from '../basic-card/basic-card';
import ClampText from './clamp-text';

import type { IssueActivityItem, IssueDetail } from '../../../typing';

import './issues-activity.scss';

/** 评论内容最大显示行数 */
const MAX_COMMENT_LINES = 3;

export default defineComponent({
  name: 'IssuesActivity',
  props: {
    detail: {
      type: Object as PropType<IssueDetail>,
      default: () => ({}),
    },
  },
  setup(props) {
    const { t } = useI18n();

    const commonInput = useTemplateRef<InstanceType<typeof Input>>('commonInput');
    const activeNodeMap = ISSUES_ACTIVE_NODE_ICON_MAP;

    /** 评论输入框是否聚焦 */
    const isCommentInputFocus = shallowRef(false);
    /** 评论内容 */
    const commentContent = shallowRef('');
    /** 富文本编辑弹窗显示 */
    const isMarkdownDialogShow = shallowRef(false);
    const isEditMarkdown = shallowRef(false);
    /** 富文本内容 */
    const markdownContent = shallowRef('');
    /** 评论loading */
    const commentLoading = shallowRef(false);

    const loading = shallowRef(false);
    const activeList = shallowRef<IssueActivityItem[]>([]);
    const getActiveList = () => {
      loading.value = true;
      listIssueActivities({
        bk_biz_id: props.detail?.bk_biz_id,
        id: props.detail?.id,
      }).then(data => {
        activeList.value = data;
      });
      loading.value = false;
    };
    watch(
      () => props.detail,
      detail => {
        if (detail) {
          getActiveList();
        }
      }
    );

    /** 处理评论输入框聚焦 */
    const handleCommentInputFocus = () => {
      isCommentInputFocus.value = true;
      nextTick(() => {
        console.log('commonInput', commonInput.value);
        commonInput.value?.focus?.();
      });
    };

    /** 处理评论输入框失焦 */
    const handleCommentInputBlur = () => {
      // 延迟失焦，以便点击工具栏按钮
      setTimeout(() => {
        if (!commentContent.value && !isMarkdownDialogShow.value) {
          isCommentInputFocus.value = false;
        }
      }, 200);
    };

    /** 处理评论内容变化 */
    const handleCommentInputChange = (value: string) => {
      commentContent.value = value;
    };

    /** 创建评论 */
    const handleCreateComment = () => {
      handleOpenMarkdownDialog(commentContent.value);
    };

    /** 查看评论 */
    const handleViewComment = (content: string) => {
      handleOpenMarkdownDialog(content, false);
    };

    /** 打开富文本编辑弹窗 */
    const handleOpenMarkdownDialog = (content: string, isEdit = true) => {
      isMarkdownDialogShow.value = true;
      markdownContent.value = content;
      isEditMarkdown.value = isEdit;
    };

    /** 关闭富文本编辑弹窗 */
    const handleCloseMarkdownDialog = () => {
      isMarkdownDialogShow.value = false;
    };

    /** 确认富文本编辑 */
    const handleConfirmMarkdown = () => {
      if (isEditMarkdown.value) {
        commentContent.value = markdownContent.value;
      }
      isMarkdownDialogShow.value = false;
    };

    /** 发送评论 */
    const handleSendComment = () => {
      commentLoading.value = true;
      followUpIssues({
        issues: [
          {
            issue_id: props.detail?.id,
            bk_biz_id: props.detail?.bk_biz_id,
          },
        ],
        content: commentContent.value,
      })
        .then(({ succeeded }) => {
          const activeItem = succeeded.find(item => item.issue_id === props.detail?.id);
          if (activeItem) {
            commentContent.value = '';
            isCommentInputFocus.value = false;
            activeList.value = [
              {
                ...activeItem,
                from_value: null,
                to_value: null,
              },
              ...activeList.value,
            ];
          }

          Message({
            message: t(activeItem ? '评论发送成功' : '评论发送失败'),
            theme: activeItem ? 'success' : 'error',
          });
        })
        .finally(() => {
          commentLoading.value = false;
        });
    };

    /**
     * 渲染评论输入框
     */
    const renderCommentInput = () => {
      return renderActivityItem({
        icon: <i class='icon-monitor icon-a-useryonghu' />,
        title: (
          <div class='comment-input-wrapper'>
            {isCommentInputFocus.value ? (
              <div class='comment-input-expanded'>
                <Input
                  ref='commonInput'
                  class='comment-textarea'
                  v-model={commentContent.value}
                  autosize={{ minRows: 3, maxRows: 7 }}
                  placeholder={t('我要评论...')}
                  resize={false}
                  type='textarea'
                  onBlur={handleCommentInputBlur}
                  onInput={handleCommentInputChange}
                />
                <div class='comment-input-toolbar'>
                  <div
                    class='rich-text-btn'
                    onClick={handleCreateComment}
                  >
                    <i class='icon-monitor icon-switch1 switch-icon' />
                    <span>{t('button-富文本编辑')}</span>
                  </div>
                  <Button
                    class='send-btn'
                    disabled={!commentContent.value}
                    loading={commentLoading.value}
                    theme='primary'
                    onClick={handleSendComment}
                  >
                    <i class='icon-monitor icon-published send-icon' />
                  </Button>
                </div>
              </div>
            ) : (
              <div
                class='comment-input-collapsed'
                onClick={handleCommentInputFocus}
              >
                <span class='placeholder'>{t('我要评论...')}</span>
              </div>
            )}
          </div>
        ),
      });
    };

    /**
     * 渲染富文本编辑弹窗
     */
    const renderMarkdownDialog = () => {
      return (
        <Dialog
          width={800}
          class='comment-markdown-dialog'
          v-model:isShow={isMarkdownDialogShow.value}
          title={t(isEditMarkdown.value ? '输入评论' : '查看完整评论')}
          onClosed={handleCloseMarkdownDialog}
        >
          {{
            default: () => (
              <div class='markdown-editor-wrapper'>
                {isEditMarkdown.value ? (
                  <MarkdownEditor
                    height='420px'
                    value={markdownContent.value}
                    onInput={val => {
                      markdownContent.value = val;
                    }}
                  />
                ) : (
                  <MarkdownViewer
                    height='420px'
                    class='view-markdown-wrapper'
                    value={markdownContent.value}
                  />
                )}
              </div>
            ),
            footer: () => (
              <div class='dialog-footer'>
                <Button
                  theme='primary'
                  onClick={handleConfirmMarkdown}
                >
                  {t('确定')}
                </Button>
                <Button onClick={handleCloseMarkdownDialog}>{t('取消')}</Button>
              </div>
            ),
          }}
        </Dialog>
      );
    };

    /**
     * 渲染活动项
     */
    const renderActivityItem = (config: {
      content?: JSX.Element | string;
      icon: JSX.Element;
      showLine?: boolean;
      title: JSX.Element | string;
    }) => {
      return (
        <div class='activity-item'>
          <div class='activity-item-line'>
            <div class='line-icon'>{config.icon}</div>
            {config.showLine !== false && <div class='line' />}
          </div>
          <div class='activity-item-content'>
            <div class='content-header'>{config.title}</div>
            {config.content && <div class='content-body'>{config.content}</div>}
          </div>
        </div>
      );
    };

    /**
     * 渲染 Issue 拆分（二期功能）
     */
    const renderSplitActivity = (item: IssueActivityItem) => {
      const splitNode = activeNodeMap[IssueActiveNodeTypeEnum.SPLIT];
      return renderActivityItem({
        icon: (
          <img
            class='activity-icon'
            alt=''
            src={splitNode.icon}
          />
        ),
        title: (
          <div class='title-row'>
            <span class='action'>{splitNode.alias}</span>
            <span
              class='time'
              v-bk-tooltips={{ content: dayjs(item.time * 1000).format('YYYY-MM-DD HH:mm:ss') }}
            >
              {dayjs(item.time).fromNow()}
            </span>
          </div>
        ),
        content: (
          <div class='split-content'>
            <div class='desc'>{t('拆分为 {0} 个 Issue:', [2])}</div>
            <ul class='issue-list'>
              <li class='issue-item'>
                <span class='link'>异常登录日志告警</span>
              </li>
              <li class='issue-item'>
                <span class='link'>异常登录日志告警2222</span>
              </li>
            </ul>
          </div>
        ),
      });
    };

    /**
     * 渲染 Issue 合并（二期功能）
     */
    const renderMergeActivity = (item: IssueActivityItem) => {
      const mergeNode = activeNodeMap[IssueActiveNodeTypeEnum.MERGE];
      return renderActivityItem({
        icon: (
          <img
            class='activity-icon'
            alt=''
            src={mergeNode.icon}
          />
        ),
        title: (
          <div class='title-row'>
            <span class='action'>{mergeNode.alias}</span>
            <span
              class='time'
              v-bk-tooltips={{ content: dayjs(item.time * 1000).format('YYYY-MM-DD HH:mm:ss') }}
            >
              {dayjs(item.time).fromNow()}
            </span>
          </div>
        ),
        content: (
          <div class='merge-content'>
            <span class='desc'>{t('合并进 Issue:')}</span>
            <span class='link'>异常登录日志告警</span>
          </div>
        ),
      });
    };

    /**
     * 渲染评论
     */
    const renderCommentActivity = (item: IssueActivityItem) => {
      return renderActivityItem({
        icon: <i class='icon-monitor icon-a-useryonghu' />,
        title: (
          <div class='title-row'>
            <span class='user'>{item.operator}</span>
            <span
              class='time'
              v-bk-tooltips={{ content: dayjs(item.time * 1000).format('YYYY-MM-DD HH:mm:ss') }}
            >
              {dayjs(item.time * 1000).fromNow()}
            </span>
          </div>
        ),
        content: (
          <div class='comment-content'>
            <ClampText
              content={item.content}
              maxLines={MAX_COMMENT_LINES}
              onExpand={handleViewComment}
            />
          </div>
        ),
      });
    };

    /**
     * 渲染状态流转
     */
    const renderStatusActivity = (item: IssueActivityItem) => {
      const statusNode = activeNodeMap[IssueActiveNodeTypeEnum.STATUS_CHANGE];
      return renderActivityItem({
        icon: (
          <img
            class='activity-icon'
            alt=''
            src={statusNode.icon}
          />
        ),
        title: (
          <div class='title-row'>
            <span class='action'>
              {statusNode.alias}：{ISSUES_STATUS_MAP[item.to_value]?.alias}
            </span>
            <span
              class='time'
              v-bk-tooltips={{ content: dayjs(item.time * 1000).format('YYYY-MM-DD HH:mm:ss') }}
            >
              {dayjs(item.time * 1000).fromNow()}
            </span>
          </div>
        ),
      });
    };

    /**
     * 渲染指派负责人
     */
    const renderDispatchActivity = (item: IssueActivityItem) => {
      const dispatchNode = activeNodeMap[IssueActiveNodeTypeEnum.ASSIGNEE_CHANGE];
      return renderActivityItem({
        icon: (
          <img
            class='activity-icon'
            alt=''
            src={dispatchNode.icon}
          />
        ),
        title: (
          <div class='title-row'>
            <span class='action'>
              {dispatchNode.alias}：{item.to_value}
            </span>
            <span
              class='time'
              v-bk-tooltips={{ content: dayjs(item.time * 1000).format('YYYY-MM-DD HH:mm:ss') }}
            >
              {dayjs(item.time * 1000).fromNow()}
            </span>
          </div>
        ),
      });
    };

    /**
     * 渲染优先级变更
     */
    const renderPriorityActivity = (item: IssueActivityItem) => {
      const priorityNode = activeNodeMap[IssueActiveNodeTypeEnum.PRIORITY_CHANGE];
      return renderActivityItem({
        icon: (
          <img
            class='activity-icon'
            alt=''
            src={priorityNode.icon}
          />
        ),
        title: (
          <div class='title-row'>
            <span class='action'>
              {priorityNode.alias}：{ISSUES_PRIORITY_MAP[item.to_value]?.alias}
            </span>
            <span
              class='time'
              v-bk-tooltips={{ content: dayjs(item.time * 1000).format('YYYY-MM-DD HH:mm:ss') }}
            >
              {dayjs(item.time * 1000).fromNow()}
            </span>
          </div>
        ),
      });
    };

    /**
     * 渲染首次出现
     */
    const renderFirstActivity = (item: IssueActivityItem) => {
      const firstNode = activeNodeMap[IssueActiveNodeTypeEnum.CREATE];
      return renderActivityItem({
        icon: (
          <img
            class='activity-icon'
            alt=''
            src={firstNode.icon}
          />
        ),
        title: (
          <div class='title-row'>
            <span class='action'>{firstNode.alias}</span>
            <span
              class='time'
              v-bk-tooltips={{ content: dayjs(item.time * 1000).format('YYYY-MM-DD HH:mm:ss') }}
            >
              {dayjs(item.time * 1000).fromNow()}
            </span>
          </div>
        ),
        showLine: false,
      });
    };

    /**
     * 根据不同的活动类型渲染不同的内容
     */
    const renderActivityContent = (item: IssueActivityItem) => {
      switch (item.activity_type) {
        case IssueActiveNodeTypeEnum.COMMENT:
          return renderCommentActivity(item);
        case IssueActiveNodeTypeEnum.STATUS_CHANGE:
          return renderStatusActivity(item);
        case IssueActiveNodeTypeEnum.ASSIGNEE_CHANGE:
          return renderDispatchActivity(item);
        case IssueActiveNodeTypeEnum.PRIORITY_CHANGE:
          return renderPriorityActivity(item);
        case IssueActiveNodeTypeEnum.CREATE:
          return renderFirstActivity(item);
        // TODO: 合并和拆分是二期功能
        case IssueActiveNodeTypeEnum.SPLIT:
          return renderSplitActivity(item);
        case IssueActiveNodeTypeEnum.MERGE:
          return renderMergeActivity(item);
        default:
          return null;
      }
    };

    const renderSkeleton = () => {
      return (
        <div class='skeleton-wrapper'>
          {new Array(5).fill(0).map(() =>
            renderActivityItem({
              title: <div class='skeleton-element title-skeleton' />,
              icon: <div class='skeleton-element icon-skeleton' />,
            })
          )}
        </div>
      );
    };

    return {
      loading,
      activeList,
      renderCommentInput,
      renderMarkdownDialog,
      renderActivityContent,
      renderSkeleton,
    };
  },
  render() {
    return (
      <BasicCard
        class='issues-activity'
        title={this.$t('问题活动')}
      >
        {this.renderCommentInput()}
        <div class='activity-list'>
          {this.loading ? this.renderSkeleton() : this.activeList.map(item => this.renderActivityContent(item))}
        </div>
        {this.renderMarkdownDialog()}
      </BasicCard>
    );
  },
});
