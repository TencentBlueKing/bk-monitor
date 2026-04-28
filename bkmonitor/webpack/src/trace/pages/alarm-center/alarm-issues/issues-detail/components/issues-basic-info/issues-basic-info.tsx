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

import { type PropType, computed, defineComponent, reactive, shallowRef, useTemplateRef, watch } from 'vue';

import { Button, Loading, Message, Popover } from 'bkui-vue';
import dayjs from 'dayjs';
import { useI18n } from 'vue-i18n';

import UserSelector from '../../../../../../components/user-selector/user-selector';
import { IssueActionEnum, ISSUES_PRIORITY_MAP, IssueStatusEnum } from '../../../constant';
import {
  archiveIssues,
  assignIssues,
  resolveIssues,
  unArchiveIssues,
  unResolveIssues,
  updateIssuesPriority,
} from '../../../services/issues-operations';
import BasicCard from '../basic-card/basic-card';
import DoubleConfirmDialog from '@/components/double-confirm-dialog/double-confirm-dialog';

import type {
  ImpactScopeResource,
  ImpactScopeResourceKeyType,
  IssueActionType,
  IssueActivityItem,
  IssueDetail,
  IssuePriorityType,
  IssueStatusType,
} from '../../../typing';

import './issues-basic-info.scss';

export default defineComponent({
  name: 'IssuesBasicInfo',
  props: {
    detail: {
      type: Object as PropType<IssueDetail>,
      default: () => ({}),
    },
  },
  emits: {
    assigneeChange: (_users: string[], _activities: IssueActivityItem[]) => true,
    priorityChange: (_priority: IssuePriorityType, _activities: IssueActivityItem[]) => true,
    confirm: (_type: IssueStatusType, _activities: IssueActivityItem[]) => true,
    impactScopeClick: (_resourceKey: ImpactScopeResourceKeyType, _resource: ImpactScopeResource) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    /** 优先级 弹窗显示状态 */
    const priorityPopoverShow = shallowRef(false);
    /** 优先级 弹窗实例*/
    const priorityPopover = useTemplateRef<InstanceType<typeof Popover>>('priorityPopover');
    /** 弹窗展示 */
    const showDialog = shallowRef(false);
    /** 弹窗加载状态 */
    const dialogLoading = shallowRef(false);
    /** 操作类型 */
    const actionType = shallowRef<IssueActionType>(IssueActionEnum.RESOLVED);
    /** 弹窗确认提示 */
    const dialogConfirmTip = computed(() => {
      if (actionType.value === IssueActionEnum.RESOLVED) {
        return t('确认标记为“已解决”？');
      }
      if (actionType.value === IssueActionEnum.UNRESOLVED) {
        return t('确认重新打开？');
      }
      if (actionType.value === IssueActionEnum.ARCHIVED) {
        return t('确认归档？');
      }
      if (actionType.value === IssueActionEnum.UN_ARCHIVED) {
        return t('确认恢复？');
      }
      return '';
    });

    const actionApi = {
      [IssueActionEnum.RESOLVED]: resolveIssues,
      [IssueActionEnum.UNRESOLVED]: unResolveIssues,
      [IssueActionEnum.ARCHIVED]: archiveIssues,
      [IssueActionEnum.UN_ARCHIVED]: unArchiveIssues,
    };

    /** 负责人列表 */
    const userList = shallowRef<string[]>([]);

    watch(
      () => props.detail,
      val => {
        userList.value = val?.assignee || [];
      },
      {
        immediate: true,
      }
    );

    const loadings = reactive({
      priority: false,
      assignee: false,
    });

    /**
     * 计算距离当前时间的时间差
     * @param time 时间戳
     * @returns 时间差
     */
    const getTimeDiff = (time: number) => {
      if (!time) return '';
      return dayjs(time * 1000).fromNow();
    };

    /**
     * issues 优先级列表
     */
    const issuesPriorityList = Object.entries(ISSUES_PRIORITY_MAP).map(([key, value]) => ({
      ...value,
      id: key as IssuePriorityType,
    }));

    /** 优先级弹窗显示状态 */
    const handlePopoverChange = (show: boolean) => {
      priorityPopoverShow.value = show;
    };

    /**
     * 修改优先级
     * @param id 优先级id
     */
    const handlePriorityClick = (id: IssuePriorityType) => {
      loadings.priority = true;
      updateIssuesPriority({
        issues: [
          {
            bk_biz_id: props.detail.bk_biz_id,
            issue_id: props.detail.id,
          },
        ],
        priority: id,
      })
        .then(({ succeeded, failed }) => {
          const activeItem = succeeded.find(item => item.issue_id === props.detail?.id);
          if (activeItem) {
            priorityPopover.value?.hide();
            emit('priorityChange', id, activeItem.activities);
          }
          Message({
            theme: activeItem ? 'success' : 'error',
            message: activeItem ? t('操作成功') : failed[0]?.message,
          });
        })
        .finally(() => {
          loadings.priority = false;
        });
    };

    /**
     * 修改负责人
     * @param users 负责人列表
     */
    const handleResponsiblePersonChange = (users: string[]) => {
      userList.value = users;
      if (users.length === 0) {
        Message({
          theme: 'error',
          message: t('最少选择一个负责人'),
        });
      }
    };

    const handleResponsiblePersonBlur = () => {
      if (!userList.value.length || JSON.stringify(props.detail.assignee) === JSON.stringify(userList.value)) return;
      loadings.assignee = true;
      assignIssues({
        issues: [
          {
            bk_biz_id: props.detail.bk_biz_id,
            issue_id: props.detail.id,
          },
        ],
        assignee: userList.value,
      })
        .then(({ succeeded, failed }) => {
          const activeItem = succeeded.find(item => item.issue_id === props.detail?.id);
          if (activeItem) {
            emit('assigneeChange', userList.value, activeItem.activities);
          }
          Message({
            theme: activeItem ? 'success' : 'error',
            message: activeItem ? t('操作成功') : failed[0]?.message,
          });
        })
        .finally(() => {
          loadings.assignee = false;
        });
    };

    /**
     * 处理影响范围点击
     * @param resourceKey 影响范围资源key
     * @param resource 影响范围资源
     */
    const handleImpactScopeClick = (resourceKey: ImpactScopeResourceKeyType, resource: ImpactScopeResource) => {
      emit('impactScopeClick', resourceKey, resource);
    };

    /**
     * issues 操作
     */
    const handleConfirm = () => {
      dialogLoading.value = true;
      actionApi[actionType.value]({
        issues: [
          {
            issue_id: props.detail.id,
            bk_biz_id: props.detail.bk_biz_id,
          },
        ],
      })
        .then(({ succeeded, failed }) => {
          const activeItem = succeeded.find(item => item.issue_id === props.detail?.id);
          if (activeItem) {
            handleDialogChange(false);
            emit('confirm', activeItem.status, activeItem.activities);
          }
          Message({
            theme: activeItem ? 'success' : 'error',
            message: activeItem ? t('操作成功') : failed[0]?.message,
          });
        })
        .finally(() => {
          dialogLoading.value = false;
        });
    };

    /**
     * 弹窗展示
     */
    const handleDialogChange = (show: boolean, type: IssueActionType = IssueActionEnum.RESOLVED) => {
      showDialog.value = show;
      actionType.value = type;
    };

    return {
      loadings,
      userList,
      issuesPriorityList,
      priorityPopoverShow,
      showDialog,
      dialogLoading,
      dialogConfirmTip,
      handlePopoverChange,
      handlePriorityClick,
      handleResponsiblePersonChange,
      handleResponsiblePersonBlur,
      handleImpactScopeClick,
      handleConfirm,
      handleDialogChange,
      getTimeDiff,
    };
  },
  render() {
    const isResolved = this.detail.status === IssueStatusEnum.RESOLVED;
    const isArchived = this.detail.status === IssueStatusEnum.ARCHIVED;

    return (
      <BasicCard
        class='issues-basic-info'
        title={this.$t('基础信息')}
      >
        <div class='basic-info-wrapper'>
          <div class='basic-info-item priority'>
            <div class='basic-info-label'>
              <i class='icon-monitor label-icon icon-priority' />
              <span class='title'>{this.$t('优先级')}</span>
            </div>
            <Popover
              ref='priorityPopover'
              v-slots={{
                content: () => (
                  <Loading
                    loading={this.loadings.priority}
                    mode='spin'
                    size='small'
                    theme='primary'
                  >
                    <div class='priority-select-wrap'>
                      {this.issuesPriorityList.map(item => (
                        <div
                          key={item.id}
                          class='priority-item'
                          onClick={() => this.handlePriorityClick(item.id)}
                        >
                          <div
                            style={{ color: item.color, backgroundColor: item.bgColor }}
                            class='priority-tag'
                          >
                            {item.alias}
                          </div>
                        </div>
                      ))}
                    </div>
                  </Loading>
                ),
              }}
              arrow={false}
              placement='bottom-start'
              theme='light priority-select-popover'
              trigger='click'
              onAfterHidden={() => this.handlePopoverChange(false)}
              onAfterShow={() => this.handlePopoverChange(true)}
            >
              <div class={['basic-info-value', { 'is-active': this.priorityPopoverShow }]}>
                <div
                  style={{
                    color: ISSUES_PRIORITY_MAP[this.detail.priority]?.color,
                    backgroundColor: ISSUES_PRIORITY_MAP[this.detail.priority]?.bgColor,
                  }}
                  class='priority-tag'
                >
                  {ISSUES_PRIORITY_MAP[this.detail.priority]?.alias}
                </div>
              </div>
            </Popover>
          </div>
          <div class='basic-info-item user'>
            <div class='basic-info-label'>
              <i class='icon-monitor label-icon icon-user' />
              <span class='title'>{this.$t('负责人')}</span>
            </div>
            <div class='basic-info-value'>
              <UserSelector
                modelValue={this.userList}
                placeholder={this.$t('请选择负责人')}
                onBlur={this.handleResponsiblePersonBlur}
                onUpdate:modelValue={this.handleResponsiblePersonChange}
              />
            </div>
          </div>
          <div class='basic-info-item influence'>
            <div class='basic-info-label'>
              <i class='icon-monitor label-icon icon-influence' />
              <span class='title'>{this.$t('影响范围')}</span>
            </div>
            <div class='basic-info-value'>
              {Object.entries(this.detail.impact_scope ?? {}).length === 0 && this.$t('无')}
              {Object.entries(this.detail.impact_scope ?? {}).map(([resourceKey, resource]) => (
                <div
                  key={resourceKey}
                  class='influence-item'
                  onClick={() =>
                    this.handleImpactScopeClick(
                      resourceKey as ImpactScopeResourceKeyType,
                      resource as ImpactScopeResource
                    )
                  }
                >
                  <div class='label'>{resource.display_name}：</div>
                  <div class='value'>{resource.count}</div>
                </div>
              ))}
            </div>
          </div>
          <div class='basic-info-item'>
            <div class='basic-info-label'>
              <i class='icon-monitor label-icon icon-mc-time-shift' />
              <span class='title'>{this.$t('最后出现时间')}</span>
            </div>
            <div class='basic-info-value'>{this.getTimeDiff(this.detail.last_alert_time)}</div>
          </div>
          <div class='basic-info-item'>
            <div class='basic-info-label'>
              <i class='icon-monitor label-icon icon-mc-time-shift' />
              <span class='title'>{this.$t('最早发生时间')}</span>
            </div>
            <div class='basic-info-value'>{this.getTimeDiff(this.detail.first_alert_time)}</div>
          </div>
          <div class='confirm-btns'>
            {this.detail.status !== IssueStatusEnum.ARCHIVED && (
              <Button
                class='confirm-btn'
                {...(!isResolved && {
                  theme: 'primary',
                })}
                onClick={() => {
                  this.handleDialogChange(true, isResolved ? IssueActionEnum.UNRESOLVED : IssueActionEnum.RESOLVED);
                }}
              >
                {this.$t(isResolved ? '重新打开' : '标记为已解决')}
              </Button>
            )}

            {this.detail.status !== IssueStatusEnum.RESOLVED && (
              <Button
                class='confirm-btn'
                onClick={() => {
                  this.handleDialogChange(true, isArchived ? IssueActionEnum.UN_ARCHIVED : IssueActionEnum.ARCHIVED);
                }}
              >
                {this.$t(isArchived ? '恢复' : '归档')}
              </Button>
            )}
          </div>

          <DoubleConfirmDialog
            isShow={this.showDialog}
            loading={this.dialogLoading}
            tip={this.dialogConfirmTip}
            onCancel={() => {
              this.handleDialogChange(false);
            }}
            onConfirm={this.handleConfirm}
            onUpdate:isShow={this.handleDialogChange}
          />
        </div>
      </BasicCard>
    );
  },
});
