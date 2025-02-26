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
import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './timeseries-detail.scss';
import IndicatorTable from './indicator-table';

interface IMenuItem {
  name: string;
  id: string;
  checked: boolean;
}

interface IGroup {
  title: string;
  count: number;
}

@Component
export default class TimeseriesDetailNew extends tsc<any, any> {
  menuList: IMenuItem[] = [
    {
      name: window.i18n.tc('编辑'),
      checked: false,
      id: 'edit',
    },
    {
      name: window.i18n.tc('删除'),
      checked: false,
      id: 'delete',
    },
  ];
  /** 当前拖拽id */
  dragId = '';
  dragoverId = '';
  groupListMock: IGroup[] = [
    {
      title: '分组1',
      count: 23,
    },
    {
      title: '分组2',
      count: 2,
    },
    {
      title: '分组放大哈第三方和',
      count: 3,
    },
  ];
  isShowRightWindow = true; // 是否显示右侧帮助栏

  tabs = [
    {
      title: '指标',
      id: 'indicator',
    },
    {
      title: '维度',
      id: 'dimension',
    },
  ];
  activeTab = this.tabs[0].id;

  /** 分割线 ================================ */
  handleMenuClick(item) {
    // TODO
    console.log(item);
  }

  // 拖拽开始，记录当前拖拽的ID
  handleDragstart(index: number, e) {
    console.log('e', e.target.children);
    this.dragId = index.toString();
  }

  // 拖拽经过事件，设置当前拖拽ID
  handleDragover(index: number, e: DragEvent) {
    e.preventDefault();
    this.dragoverId = index.toString();
  }

  // 拖拽离开事件，清除当前拖拽的ID
  handleDragleave() {
    this.dragoverId = '';
  }

  // 拖拽完成时逻辑
  handleDrop() {
    if (this.dragId !== this.dragoverId) {
      const tab = Object.assign([], this.groupListMock);
      const dragIndex = Number.parseInt(this.dragId, 10);
      const dragoverIndex = Number.parseInt(this.dragoverId, 10);

      const draggedTab = this.groupListMock[dragIndex];
      tab.splice(dragIndex, 1);
      tab.splice(dragoverIndex, 0, draggedTab);
      this.dragId = '';
      this.dragoverId = '';
      this.groupListMock = tab;
    }
    this.dragoverId = '';
  }
  // 拖拽 end

  getCmpByActiveTab(activeTab: string) {
    const cmpMap = {
      /** 指标 */
      indicator: this.getIndicatorCmp,
      /** 维度 */
      dimension: this.getDimensionCmp,
    };
    return cmpMap[activeTab]();
  }

  getIndicatorCmp() {
    return (
      <div class='list-content'>
        {this.getIndicatorGroupList()}
        {this.getIndicatorList()}
      </div>
    );
  }

  getDimensionCmp() {
    return <div>{/* TOOD */}</div>;
  }

  getIndicatorGroupList() {
    return (
      <div class={{ left: true, active: this.isShowRightWindow }}>
        <div
          class={'right-button'}
          onClick={() => (this.isShowRightWindow = !this.isShowRightWindow)}
        >
          {this.isShowRightWindow ? (
            <i class='icon-monitor icon-arrow-left icon' />
          ) : (
            <i class='icon-monitor icon-arrow-right icon' />
          )}
        </div>
        <div class='group-list'>
          <div class='top-group'>
            <div class={{ group: true, 'group-selected': true }}>
              <div class='group-name'>
                <i class='icon-monitor icon-mc-all' />
                所有指标
              </div>
              <div class='group-count'>23</div>
            </div>
            <div class='group'>
              <div class='group-name'>
                <i class='icon-monitor icon-mc-full-folder' />
                未分组
              </div>
              <div class='group-count'>23</div>
            </div>
          </div>
          <div class='custom-group'>
            {this.groupListMock.length ? (
              this.groupListMock.map((group, index) => (
                <div
                  key={group.title}
                  class={['group', this.dragoverId === index.toString() ? 'is-dragover' : '']}
                  draggable={true}
                  onDragleave={this.handleDragleave}
                  onDragover={e => this.handleDragover(index, e)}
                  onDragstart={e => this.handleDragstart(index, e)}
                  onDrop={this.handleDrop}
                >
                  <i class='icon-monitor icon-mc-tuozhuai item-drag' />
                  <div class='group-name'>
                    <i class='icon-monitor icon-mc-full-folder' />
                    {group.title}
                  </div>
                  <div class='group-count'>{group.count || 0}</div>
                  <bk-popover
                    ref='menuPopover'
                    class='group-popover'
                    tippy-options={{
                      trigger: 'click',
                    }}
                    arrow={false}
                    offset={'0, 0'}
                    placement='bottom-start'
                    theme='light common-monitor'
                  >
                    <span class='more-operation'>
                      <i class='icon-monitor icon-mc-more' />
                    </span>
                    <div
                      class='home-chart-more-list'
                      slot='content'
                    >
                      {this.menuList.map(item => (
                        <span
                          key={item.id}
                          class={`more-list-item ${item.id}`}
                          on-click={() => this.handleMenuClick(item)}
                        >
                          {item.name}
                        </span>
                      ))}
                    </div>
                  </bk-popover>
                </div>
              ))
            ) : (
              <div>
                {/* TODO 空态 */}
                空的
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  getIndicatorList() {
    return (
      <div class='right'>
        <IndicatorTable />
      </div>
    );
  }

  render() {
    return (
      <div>
        <div class='list-header'>
          <div class='detail-information-title'>{this.$t('指标与维度')}</div>
          <div class='head'>
            <div class='tabs'>
              {this.tabs.map(({ title, id }) => (
                <span
                  key={id}
                  class={['tab', id === this.activeTab ? 'active' : '']}
                  onClick={() => (this.activeTab = id)}
                >
                  {title}
                </span>
              ))}
            </div>
            <div class='tools'>
              <span class='tool'>导入</span>
              <span class='tool'>导出</span>
            </div>
          </div>
        </div>
        {this.getCmpByActiveTab(this.activeTab)}
      </div>
    );
  }
}
