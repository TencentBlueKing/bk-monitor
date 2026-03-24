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

import { type PropType, defineComponent, reactive, shallowRef, useTemplateRef } from 'vue';

import { Button, Loading, Message, Popover } from 'bkui-vue';
import dayjs from 'dayjs';
import { useI18n } from 'vue-i18n';

import UserSelector from '../../../../../../components/user-selector/user-selector';
import IssuesResolveDialog from '../../../components/issues-resolve-dialog/issues-resolve-dialog';
import { ImpactScopeResourceLabelMap, IssuesPriorityMap } from '../../../constant';
import { assignIssues, updateIssuesPriority } from '../../../services/issues-operations';
import BasicCard from '../basic-card/basic-card';

import type { ImpactScopeResource, ImpactScopeResourceKeyType, IssueDetail, IssuePriorityType } from '../../../typing';

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
    assigneeChange: (_users: string[]) => true,
    priorityChange: (_priority: IssuePriorityType) => true,
    resolved: () => true,
    impactScopeClick: (_resourceKey: ImpactScopeResourceKeyType, _resource: ImpactScopeResource) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const priorityPopoverShow = shallowRef(false);
    const priorityPopover = useTemplateRef<InstanceType<typeof Popover>>('priorityPopover');

    const showDialog = shallowRef(false);

    const userList = shallowRef<string[]>([]);

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
    const issuesPriorityList = Object.entries(IssuesPriorityMap).map(([key, value]) => ({
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
      priorityPopover.value?.hide();

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
        .then(() => {
          emit('priorityChange', id);
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
      console.log('handleResponsiblePersonChange', users);
      userList.value = users;
      if (users.length === 0) {
        Message({
          theme: 'error',
          message: t('最少选择一个负责人'),
        });
      }
    };

    const handleResponsiblePersonBlur = () => {
      if (!userList.value.length) return;
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
        .then(() => {
          emit('assigneeChange', userList.value);
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
     * 标记已解决
     */
    const handleConfirm = () => {
      handleDialogChange(false);
      emit('resolved');
    };

    /**
     * 弹窗展示
     */
    const handleDialogChange = (show: boolean) => {
      showDialog.value = show;
    };

    return {
      loadings,
      userList,
      issuesPriorityList,
      priorityPopoverShow,
      showDialog,
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
                    color: IssuesPriorityMap[this.detail.priority]?.color,
                    backgroundColor: IssuesPriorityMap[this.detail.priority]?.bgColor,
                  }}
                  class='priority-tag'
                >
                  {IssuesPriorityMap[this.detail.priority]?.alias}
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
                  <div class='label'>{ImpactScopeResourceLabelMap[resourceKey]}：</div>
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

          {!this.detail.is_resolved && (
            <Button
              class='confirm-btn'
              theme='primary'
              onClick={() => {
                this.handleDialogChange(true);
              }}
            >
              {this.$t('标记为已解决')}
            </Button>
          )}

          <IssuesResolveDialog
            issuesData={[
              {
                bk_biz_id: this.detail.bk_biz_id,
                issue_id: this.detail.id,
              },
            ]}
            isShow={this.showDialog}
            onCancel={() => {
              this.handleDialogChange(false);
            }}
            onSuccess={this.handleConfirm}
            onUpdate:isShow={this.handleDialogChange}
          />
        </div>
      </BasicCard>
    );
  },
});
