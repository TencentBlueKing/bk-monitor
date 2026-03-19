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
import { defineComponent, nextTick, shallowRef, useTemplateRef } from 'vue';

import { Button, Dialog, Input } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import MarkdownEditor from '../../../../../../components/markdown-editor/editor';
import MarkdownViewer from '../../../../../../components/markdown-editor/viewer';
import { IssueActiveNodeTypeEnum, IssuesActiveNodeIconMap } from '../../../constant';
import BasicCard from '../basic-card/basic-card';

import './issues-activity.scss';

export default defineComponent({
  name: 'IssuesActivity',
  setup() {
    const { t } = useI18n();

    const commonInput = useTemplateRef<InstanceType<typeof Input>>('commonInput');
    const activeNodeMap = IssuesActiveNodeIconMap;

    /** 评论输入框是否聚焦 */
    const isCommentInputFocus = shallowRef(false);
    /** 评论内容 */
    const commentContent = shallowRef('');
    /** 富文本编辑弹窗显示 */
    const isMarkdownDialogShow = shallowRef(false);
    const isEditMarkdown = shallowRef(false);
    /** 富文本内容 */
    const markdownContent = shallowRef('');

    /** 处理评论输入框聚焦 */
    const handleCommentInputFocus = () => {
      isCommentInputFocus.value = true;
      nextTick(() => {
        commonInput.value?.focus();
      });
    };

    /** 处理评论输入框失焦 */
    const handleCommentInputBlur = () => {
      // 延迟失焦，以便点击工具栏按钮
      setTimeout(() => {
        if (!commentContent.value) {
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
      console.log('发送评论:', commentContent.value);
      commentContent.value = '';
      isCommentInputFocus.value = false;
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
                    <i class='icon-monitor icon-switch1' />
                    <span>{t('富文本编辑')}</span>
                  </div>
                  <Button
                    class='send-btn'
                    disabled={!commentContent.value}
                    theme='primary'
                    onClick={handleSendComment}
                  >
                    <i class='icon-monitor icon-published' />
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
          title={t('输入评论')}
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
     * 渲染 Issue 拆分
     */
    const renderSplitActivity = () => {
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
              v-bk-tooltips={{ content: '2025-08-01 00:00:00' }}
            >
              8months ago
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
     * 渲染 Issue 合并
     */
    const renderMergeActivity = () => {
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
              v-bk-tooltips={{ content: '2025-08-01 00:00:00' }}
            >
              8months ago
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
    const commentTextRef = useTemplateRef<HTMLSpanElement | null>('commentTextRef');
    const isCommentClamped = shallowRef(false);

    // 检测评论是否超过 3 行
    const checkCommentOverflow = () => {
      nextTick(() => {
        if (commentTextRef.value) {
          const lineHeight = 20; // 行高
          const maxLines = 3;
          const maxHeight = lineHeight * maxLines;
          isCommentClamped.value = commentTextRef.value.offsetHeight > maxHeight;
        }
      });
    };

    // 初始化检测
    checkCommentOverflow();

    const renderCommentActivity = () => {
      const commentText = `我是评论相关的信息嘻嘻，我是评论相关的信息嘻嘻，这里最多显示就是 3 行，超出 3
        行的话，就需要用...来省略，并且有一个阅读全文的弹窗哈来省略，并且有一个阅读全文的弹窗哈来省略，并且有一个阅读全文的弹窗哈`;

      return renderActivityItem({
        icon: <i class='icon-monitor icon-a-useryonghu' />,
        title: (
          <div class='title-row'>
            <span class='user'>lililiu(刘莉莉)</span>
            <span
              class='time'
              v-bk-tooltips={{ content: '2025-08-01 00:00:00' }}
            >
              8months ago
            </span>
          </div>
        ),
        content: (
          <div class='comment-content'>
            <span
              ref='commentTextRef'
              class={{ 'comment-text': true, 'is-clamped': isCommentClamped.value }}
            >
              {commentText}
            </span>
            <i
              class='icon-monitor icon-xiangqing1 comment-icon'
              onClick={() => handleViewComment(commentText)}
            />
          </div>
        ),
      });
    };

    /**
     * 渲染状态流转
     */
    const renderStatusActivity = () => {
      const statusNode = activeNodeMap[IssueActiveNodeTypeEnum.STATUS];
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
              {statusNode.alias}
              {t('未解决')}
            </span>
            <span
              class='time'
              v-bk-tooltips={{ content: '2025-08-01 00:00:00' }}
            >
              8months ago
            </span>
          </div>
        ),
      });
    };

    /**
     * 渲染指派负责人
     */
    const renderDispatchActivity = () => {
      const dispatchNode = activeNodeMap[IssueActiveNodeTypeEnum.DISPATCH];
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
            <span class='action'>{dispatchNode.alias}carrielu、edwinwu</span>
            <span
              class='time'
              v-bk-tooltips={{ content: '2025-08-01 00:00:00' }}
            >
              8months ago
            </span>
          </div>
        ),
      });
    };

    /**
     * 渲染首次出现
     */
    const renderFirstActivity = () => {
      const firstNode = activeNodeMap[IssueActiveNodeTypeEnum.FIRST];
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
              v-bk-tooltips={{ content: '2025-08-01 00:00:00' }}
            >
              8months ago
            </span>
          </div>
        ),
        showLine: false,
      });
    };

    return {
      renderCommentInput,
      renderMarkdownDialog,
      renderSplitActivity,
      renderMergeActivity,
      renderCommentActivity,
      renderStatusActivity,
      renderDispatchActivity,
      renderFirstActivity,
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
          {this.renderSplitActivity()}
          {this.renderMergeActivity()}
          {this.renderCommentActivity()}
          {this.renderStatusActivity()}
          {this.renderDispatchActivity()}
          {this.renderFirstActivity()}
        </div>
        {this.renderMarkdownDialog()}
      </BasicCard>
    );
  },
});
