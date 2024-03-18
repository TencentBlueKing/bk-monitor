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
import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './duty-preview.scss';
//

export interface IUserGroup {
  // 用户组 一维为行 二维为个
  users: {
    id: string;
    name: string;
  }[];
  color: string; // 颜色
  time: string; // 详细时间
  range: number[]; // 长度
}
interface IDateGroup {
  // 日期组
  dateStr: string | { name: string } | any; // 日期
  userGroups: IUserGroup[][];
}
interface IGroup {
  title: string;
  dateGroups: IDateGroup[];
}
interface IEvents {
  onCycleType?: 'right' | 'left';
}
export interface IPreviewValue {
  // 空闲期 例子 leisure: [ range: [[1,10],[50,100]], dateStr: '2-18' ]
  leisure: {
    col: { range: number[]; time: string }[];
    dateStr: string;
  }[];
  // 日期组 例子 dateStrArr：['2-18','2-19']
  dateStrArr: string[];
  // 轮值组
  groups: IGroup[];
  // 最大单元格长度
  max: number;
  // 跨天组
  crossDayGroups?: {
    // 轮值组
    groups: {
      // 用户组
      time: string;
      range: number[]; // max: 1440 * 7
      userGroup: IUserGroup;
    }[];
  }[];
}

interface IProps {
  value?: IPreviewValue;
}

@Component
export default class DutyPreview extends tsc<IProps, IEvents> {
  @Prop({
    default: () => ({
      leisure: [],
      dateStrArr: [],
      groups: [],
      max: 1440
    })
  })
  value: IPreviewValue;
  @Ref('userTip') userTipRef: HTMLDivElement;

  /* 预览数据 */
  previewData: IPreviewValue = {
    leisure: [],
    dateStrArr: [],
    groups: [],
    max: 1440,
    crossDayGroups: []
  };
  popoverInstance = null;
  popover = {
    users: [],
    time: ''
  };

  created() {
    this.previewData = this.value;
  }

  /* 左侧组列表 */
  getGroupNames() {
    return this.previewData?.groups.map(item => item.title) || [];
  }
  /* 每组的高度 */
  getGroupHeight(group: IGroup) {
    const arr = group.dateGroups.map(item => item?.userGroups.length || 0);
    const maxLen = Math.max(...arr);
    return 40 + maxLen * 22 + (maxLen - 1) * 10;
  }
  /* 点击切换周期 */
  @Emit('cycleType')
  handleLeftOrRightChange(type: 'right' | 'left') {
    return type;
  }
  /* 用户组样式 */
  getUserGroupStyle(color, range, row) {
    const { max } = this.previewData;
    return {
      width: `${((range[1] - range[0]) / max) * 100}%`,
      left: `${(range[0] / max) * 100}%`,
      top: `${20 + row * 32}px`,
      borderTop: `2px solid ${color}`,
      color
    };
  }
  /* 跨天用户组样式 */
  getCrossUserGroupStyle(color, range, row) {
    const max = 1440 * 7;
    return {
      width: `${((range[1] - range[0]) / max) * 100}%`,
      left: `${(range[0] / max) * 100}%`,
      top: `${20 + row * 32}px`,
      borderTop: `2px solid ${color}`,
      color
    };
  }
  /* 弹出提示框 */
  async handleMouseenter(e: Event, group: IUserGroup, isCross = false) {
    this.popover.time = group.time;
    this.popover.users = group.users;
    this.popoverInstance?.hide(100);
    this.popoverInstance?.destroy();
    this.popoverInstance = null;
    await this.$nextTick();
    this.popoverInstance = this.$bkPopover(e.target, {
      content: this.userTipRef,
      placement: 'top',
      width: isCross ? 200 : 160,
      boundary: 'window',
      theme: 'light',
      arrow: true,
      interactive: true
    });
    this.popoverInstance?.show(100);
  }

  /* 空闲时间段样式 */
  getLeisureiStyle(range) {
    let height = 0;
    this.previewData.groups.forEach(group => {
      const arr = group.dateGroups.map(item => item.userGroups.length);
      const maxLen = Math.max(...arr);
      height += 40 + maxLen * 22 + (maxLen - 1) * 10;
    });
    const { max } = this.previewData;
    return {
      display: range[1] - range[0] === 0 ? 'none' : 'block',
      width: `${((range[1] - range[0]) / max) * 100}%`,
      height: `${height - 40}px`,
      top: '20px',
      left: `${(range[0] / max) * 100}%`
    };
  }

  render() {
    return (
      <div class='duty-perview-component'>
        <div class='left'>
          <div class='top-title'>{this.$t('轮值预览')}</div>
          {/* 左侧组名列 */}
          <div class='title-items'>
            {this.previewData.groups.map(item => (
              <div
                class='title-item'
                style={{
                  height: `${this.getGroupHeight(item)}px`
                }}
              >
                {item.title}
              </div>
            ))}
          </div>
        </div>
        <div class='right-wrap'>
          {/* 头部切换按钮 */}
          <div class='btn-wrap'>
            <div
              class='left-btn'
              onClick={() => this.handleLeftOrRightChange('left')}
            >
              <span class='icon-monitor icon-arrow-left'></span>
            </div>
            <div
              class='right-btn'
              onClick={() => this.handleLeftOrRightChange('right')}
            >
              <span class='icon-monitor icon-arrow-right'></span>
            </div>
          </div>
          <div class='right'>
            {/* 头部日期行 */}
            <div class='header'>
              {this.previewData.dateStrArr.map(name => (
                <div class='header-item'>{name}</div>
              ))}
            </div>
            {/* 用户组表格 */}
            <div class='content'>
              <div class='leisure-wrap'>
                {this.previewData.leisure.map(item => (
                  <div class='leisure-col'>
                    {item.col.map(r => (
                      <div
                        class='leisure'
                        style={this.getLeisureiStyle(r.range)}
                        v-bk-tooltips={{
                          content: r.time,
                          theme: 'light',
                          placement: 'top',
                          extCls: 'duty-preview-component-leisure-tip',
                          allowHTML: false
                        }}
                      ></div>
                    ))}
                  </div>
                ))}
              </div>
              {this.previewData.groups.map((group, groupIndex) => (
                <div
                  class='row'
                  style={{
                    height: `${this.getGroupHeight(group)}px`
                  }}
                >
                  {group.dateGroups.map(g => (
                    <div class='col'>
                      {g?.userGroups.map((u, row) =>
                        u.map(item => (
                          <div
                            class='user-item'
                            style={this.getUserGroupStyle(item.color, item.range, row)}
                            onMouseenter={(event: Event) => this.handleMouseenter(event, item)}
                          >
                            {item.users.map(user => user.name || user.id).join(',')}
                          </div>
                        ))
                      )}
                    </div>
                  ))}
                  {this.previewData.crossDayGroups[groupIndex].groups.map(group => (
                    <div
                      class='user-item cross'
                      style={this.getCrossUserGroupStyle(group.userGroup.color, group.range, 0)}
                      onMouseenter={(event: Event) =>
                        this.handleMouseenter(event, { ...group.userGroup, time: group.time }, true)
                      }
                    >
                      {group.userGroup.users.map(user => user.name).join(',')}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
        <div style={{ display: 'none' }}>
          <div
            class='duty-preview-component-user-item-tip'
            ref='userTip'
          >
            <div class='time'>{this.popover.time}</div>
            <div class='users'>{this.popover.users.map(item => `${item.id} (${item.name})`).join(', ')}</div>
            {/* <div class="operate">
              <bk-button size="small" title="primary" text>{this.$t('临时换班')}</bk-button>
            </div> */}
          </div>
        </div>
      </div>
    );
  }
}
