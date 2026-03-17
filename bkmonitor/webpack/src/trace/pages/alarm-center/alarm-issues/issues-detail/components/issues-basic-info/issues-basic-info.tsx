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
import { defineComponent, shallowRef, useTemplateRef } from 'vue';

import { Button, Message, Popover } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import UserSelector from '../../../../../../components/user-selector/user-selector';
import { IssuesPriorityMap } from '../../../constant';
import BasicCard from '../basic-card/basic-card';

import './issues-basic-info.scss';

export default defineComponent({
  name: 'IssuesBasicInfo',
  setup() {
    const { t } = useI18n();
    const priorityPopoverShow = shallowRef(false);
    const priorityPopover = useTemplateRef<InstanceType<typeof Popover>>('priorityPopover');

    /** 负责人 */
    const userList = shallowRef<string[]>([]);

    /**
     * issues 优先级列表
     */
    const issuesPriorityList = Object.entries(IssuesPriorityMap).map(([key, value]) => ({
      ...value,
      id: key,
    }));

    /** 优先级弹窗显示状态 */
    const handlePopoverChange = (show: boolean) => {
      priorityPopoverShow.value = show;
    };

    /**
     * 修改优先级
     * @param id 优先级id
     */
    const handlePriorityClick = (id: string) => {
      console.log(id);
      priorityPopover.value?.hide();
    };

    const handleResponsiblePersonChange = (users: string[]) => {
      console.log(users);
      userList.value = users;
      if (users.length === 0) {
        Message({
          theme: 'error',
          message: t('最少选择一个负责人'),
        });
      }
    };

    const handleConfirm = () => {
      console.log('handleConfirm');
    };

    return {
      issuesPriorityList,
      priorityPopoverShow,
      userList,
      handlePopoverChange,
      handlePriorityClick,
      handleResponsiblePersonChange,
      handleConfirm,
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
                  style={{ color: IssuesPriorityMap.P0.color, backgroundColor: IssuesPriorityMap.P0.bgColor }}
                  class='priority-tag'
                >
                  {IssuesPriorityMap.P0.alias}
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
              <div class='influence-item'>
                <div class='label'>{this.$t('集群')}：</div>
                <div class='value'>BCS-K8s-5234</div>
              </div>
              <div class='influence-item'>
                <div class='label'>Pod：</div>
                <div class='value'>lobby-7534534532323lfse345</div>
              </div>
              <div class='influence-item'>
                <div class='label'>{this.$t('容器')}：</div>
                <div class='value'>30</div>
              </div>
            </div>
          </div>
          <div class='basic-info-item'>
            <div class='basic-info-label'>
              <i class='icon-monitor label-icon icon-mc-time-shift' />
              <span class='title'>{this.$t('最后出现时间')}</span>
            </div>
            <div class='basic-info-value'>15s ago</div>
          </div>
          <div class='basic-info-item'>
            <div class='basic-info-label'>
              <i class='icon-monitor label-icon icon-mc-time-shift' />
              <span class='title'>{this.$t('最早发生时间')}</span>
            </div>
            <div class='basic-info-value'>8months ago</div>
          </div>
          <Button
            class='confirm-btn'
            theme='primary'
            onClick={this.handleConfirm}
          >
            {this.$t('标记为已解决')}
          </Button>
        </div>
      </BasicCard>
    );
  },
});
