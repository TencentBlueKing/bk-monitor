/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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
import { Component, Emit, Inject, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { type IDragStatus, filterTaskAlarmColor, isTaskDisable } from '../uptime-check-data';

import './task-card.scss';

export type IOptionTypes = 'clone' | 'delete' | 'edit' | 'enable' | 'stop';
const options: { id: IOptionTypes; name: string }[] = [
  { id: 'edit', name: window.i18n.tc('编辑') },
  { id: 'delete', name: window.i18n.tc('删除') },
  { id: 'clone', name: window.i18n.tc('克隆') },
  { id: 'stop', name: window.i18n.tc('停用') },
  { id: 'enable', name: window.i18n.tc('启用') },
];

const contentItem = [
  { id: 'available', alarmId: 'available_alarm', unit: '%', name: window.i18n.t('可用率') },
  { id: 'task_duration', alarmId: 'task_duration_alarm', unit: 'ms', name: window.i18n.t('平均响应时长') },
];

export interface IData {
  available?: number; // 可用率
  available_alarm?: boolean; // 数字颜色是否变为红色
  bk_biz_id?: number;
  create_user?: string;
  groups?: { id: number; name: string }[];
  id?: number;
  name?: string;
  nodes?: { name?: string }[];
  status?: string; // 状态
  task_duration?: number; // 平均响应时长
  task_duration_alarm?: boolean; // 数字颜色是否变为红色
  url?: string[];
}
interface ITaskCardEvents {
  onCardClick?: number;
  onDragStatus?: IDragStatus;
  onOperate?: IOptionTypes;
}

interface ITaskCardProps {
  data?: IData;
}
@Component({
  name: 'TaskCard',
})
export default class TaskCard extends tsc<ITaskCardProps, ITaskCardEvents> {
  @Inject('authority') authority;
  @Inject('authorityMap') authorityMap;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;

  @Prop({
    type: Object,
    default: () => ({
      id: 0,
      name: '',
      url: '',
      available: 0,
      available_alarm: false,
      task_duration: 0,
      task_duration_alarm: false,
      status: '',
    }),
  })
  data: IData;

  @Ref('popoverContent') popoverContentRef: HTMLDivElement;

  popoverInstance = null;
  handleDragStart() {
    const status = {
      taskId: this.data.id,
      dragging: true,
    };
    this.handleDragStatus(status);
  }
  handleDragEnd() {
    this.handleDragStatus({
      taskId: 0,
      dragging: false,
    });
  }
  handleMouseleave() {
    this.handlePopoverHide();
  }
  @Emit('operate')
  handleOptionsClick(e: Event, item) {
    e.stopPropagation();
    return item.id;
  }
  handlePopoverShow(e: Event) {
    this.popoverInstance = this.$bkPopover(e.target, {
      content: this.popoverContentRef,
      arrow: false,
      trigger: 'click',
      placement: 'bottom',
      theme: 'light task-card',
      maxWidth: 520,
      duration: [200, 0],
      appendTo: () => this.$el,
    });
    this.popoverInstance?.show(100);
  }
  handlePopoverHide() {
    this.popoverInstance?.hide(100);
    this.popoverInstance?.destroy();
    this.popoverInstance = null;
  }

  // 返回拖拽状态
  @Emit('dragStatus')
  handleDragStatus(v: IDragStatus) {
    return v;
  }
  // 点击卡片时
  @Emit('cardClick')
  handleCardClick() {
    return this.data.id;
  }

  render() {
    return (
      <div
        class='uptime-check-task-card'
        draggable
        on-click={this.handleCardClick}
        on-dragend={this.handleDragEnd}
        on-dragstart={this.handleDragStart}
        on-mouseleave={this.handleMouseleave}
      >
        <div class='card-title'>
          <div class={['title-name', { disabled: isTaskDisable(this.data.status) }]}>
            <span
              class='name-text'
              v-bk-overflow-tips
            >
              {this.data.name}
            </span>
            {isTaskDisable(this.data.status) && <span class='title-status'>{this.$t('已停用')}</span>}
            {/* <span class="title-tip icon-monitor icon-hint"></span> */}
          </div>
          <div
            class='title-url'
            v-bk-overflow-tips
          >
            {this.data.url.join(',')}
          </div>
          <span
            class='title-icon'
            v-authority={{ active: !this.authority.MANAGE_AUTH }}
            onClick={(e: Event) => {
              e.stopPropagation();
              if (this.authority.MANAGE_AUTH) {
                this.handlePopoverShow(e);
              } else {
                this.handleShowAuthorityDetail(this.authorityMap.MANAGE_AUTH);
              }
            }}
          >
            <i class='icon-monitor icon-mc-more' />
          </span>
        </div>
        <div class='card-content'>
          {contentItem.map(item => (
            <div class='label-item'>
              {isTaskDisable(this.data.status) ? (
                <div class='top-nodata'>--</div>
              ) : !(item.id === 'task_duration' && this.data.task_duration === null) ? (
                <div class='top'>
                  <span
                    style={{ color: filterTaskAlarmColor(this.data[item.id], this.data[item.alarmId]) }}
                    class='num'
                  >
                    {this.data[item.id]}
                  </span>
                  <span class='unit'>{item.unit}</span>
                </div>
              ) : (
                <span class='icon-monitor icon-remind' />
              )}
              <div class='bottom'>{item.name}</div>
            </div>
          ))}
        </div>
        <div style={{ display: 'none' }}>
          <div
            ref='popoverContent'
            class='popover-desc'
          >
            {options
              .filter(item => (isTaskDisable(this.data.status) ? item.id !== 'stop' : item.id !== 'enable'))
              .map(item => (
                <div
                  class='popover-desc-btn'
                  onClick={(e: Event) => this.handleOptionsClick(e, item)}
                >
                  {item.name}
                </div>
              ))}
          </div>
        </div>
      </div>
    );
  }
}
