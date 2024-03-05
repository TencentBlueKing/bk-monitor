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

import { IDragStatus, processColor } from '../uptime-check-data';

import './group-card.scss';

const logoIconStyle = (logo: string) => ({
  'background-image': logo ? `url(${logo})` : 'none',
  'background-color': logo ? '' : '#B6CAEC',
  'border-radius': logo ? '0' : '100%'
});

export type IOptionType = 'edit' | 'delete';

const options: { id: IOptionType; name: string }[] = [
  { id: 'edit', name: window.i18n.tc('编辑') },
  { id: 'delete', name: window.i18n.tc('解散任务组') }
];

export interface ITaskItem {
  available?: number;
  name?: string;
  status?: string;
  task_id?: number;
}
export interface IData {
  alarm_num?: number;
  all_tasks?: ITaskItem[];
  bk_biz_id?: number;
  id?: number;
  logo?: string;
  name?: string;
  protocol_num?: { name: string; val: number }[];
  top_three_tasks?: ITaskItem[];
}
interface IGroupCardProps {
  data?: IData;
  dragStatus?: IDragStatus;
}
interface IGroupCardEvents {
  onDropItem?: {
    groupId: number;
    taskId: number;
  };
  onOperate?: IOptionType;
  onCardClick?: number;
}
@Component({
  name: 'GroupCard'
})
export default class GroupCard extends tsc<IGroupCardProps, IGroupCardEvents> {
  @Inject('authority') authority;
  @Inject('authorityMap') authorityMap;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;

  // 卡片数据
  @Prop({
    default: () => ({
      alarm_num: 0,
      all_tasks: [{ available: 0, name: '', status: '', task_id: '' }],
      bk_biz_id: 0,
      id: 0,
      logo: '',
      name: '',
      protocol_num: [{ name: '', val: 0 }],
      top_three_tasks: [{ available: 0, name: '', status: '', task_id: '' }]
    }),
    type: Object
  })
  data: IData;
  // 拖拽状态
  @Prop({ default: () => ({ taskId: 0, dragging: false }), type: Object }) dragStatus: IDragStatus;

  @Ref('popoverContent') popoverContentRef: HTMLDivElement;

  popoverInstance = null;
  hover = false; // 当拖拽停留在当前的卡片时

  handlePopoverShow(e: Event) {
    e.stopPropagation();
    this.popoverInstance = this.$bkPopover(e.target, {
      content: this.popoverContentRef,
      arrow: false,
      trigger: 'click',
      placement: 'bottom',
      theme: 'light task-card',
      maxWidth: 520,
      duration: [200, 0],
      appendTo: () => this.$el
    });
    this.popoverInstance?.show(100);
  }
  handlePopoverHide() {
    this.popoverInstance?.hide(100);
    this.popoverInstance?.destroy();
    this.popoverInstance = null;
  }

  @Emit('operate')
  handleOptionsClick(e: Event, item) {
    e.stopPropagation();
    return item.id;
  }

  handleMouseleave() {
    this.handlePopoverHide();
  }
  handleDragOver(e: Event) {
    this.hover = true;
    e.preventDefault();
  }
  handleDrop() {
    this.hover = false;
    if (this.dragStatus.dragging && this.dragStatus.taskId) {
      this.handleDropItem({
        taskId: this.dragStatus.taskId,
        groupId: this.data.id
      });
    }
  }

  // 拖拽进入成功
  @Emit('dropItem')
  handleDropItem(params: IGroupCardEvents['onDropItem']) {
    return params;
  }

  // 点击卡片
  @Emit('cardClick')
  handleGroupClick() {
    return this.data.id;
  }

  render() {
    return (
      <div
        class={['uptime-check-group-card', { active: this.dragStatus.dragging && this.hover }]}
        onMouseleave={this.handleMouseleave}
        onDragover={(e: Event) => this.handleDragOver(e)}
        onDragenter={() => {
          this.hover = true;
        }}
        onDragleave={() => {
          this.hover = false;
        }}
        onDrop={this.handleDrop}
        onClick={this.handleGroupClick}
      >
        <div class='card-desc'>
          <span
            class='desc-icon'
            style={logoIconStyle(this.data.logo)}
          >
            {!this.data.logo ? this.data.name.slice(0, 1).toLocaleUpperCase() : ''}
          </span>
          <div class='desc-right'>
            <div
              class='desc-right-title'
              v-bk-overflow-tips
            >
              {this.data.name}
              {this.data.alarm_num ? <span class='alarm-label'>{this.data.alarm_num}</span> : undefined}
            </div>
            <div class='desc-right-label'>
              {this.data.protocol_num.map(item => (
                <span class='right-label'>{`${item.name}(${item.val})`}</span>
              ))}
              {!this.data.protocol_num?.length ? <span>{this.$t('空任务组')}</span> : undefined}
            </div>
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
            <i class='icon-monitor icon-mc-more'></i>
          </span>
        </div>
        {this.data.top_three_tasks?.length ? (
          <div class='card-list'>
            {this.data.top_three_tasks.map(item => (
              <div class='card-list-progress'>
                <div class='progress-desc'>
                  <span
                    class='desc-name'
                    v-bk-overflow-tips
                  >
                    {item.name}
                  </span>
                  <span class='desc-percent'>{item.available !== null ? `${item.available}%` : '--'}</span>
                </div>
                <bk-progress
                  class='progress-item'
                  percent={+(item.available * 0.01).toFixed(2) || 0}
                  showText={false}
                  color={processColor(item.available)}
                ></bk-progress>
              </div>
            ))}
          </div>
        ) : (
          <div class='card-list-empty'>
            <div class='empty-item'>{this.$t('暂无拨测任务')}</div>
            <div class='empty-item'>{this.$t('可以拖动拨测任务至此')}</div>
          </div>
        )}
        <div style={{ display: 'none' }}>
          <div
            class='popover-desc'
            ref='popoverContent'
          >
            {options.map(item => (
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
