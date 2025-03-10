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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import emptyImageSrc from '../../../static/images/png/empty.png';
import AddGroupDialog from './add-group-dialog';
import { ALL_LABEL, NULL_LABEL } from './custom-escalation-detail';
import CustomGroupingList from './custom-grouping-list';
import IndicatorTable from './metric-table';

import './metric-tab-detail.scss';

interface IGroup {
  id: string;
  name: string;
  icon: string;
}
@Component
export default class MetricTabDetail extends tsc<any, any> {
  // @Prop({ default: [] }) metricTable;
  @Prop({ default: [] }) unitList;
  @Prop({ default: '' }) selectedLabel;
  @Prop({ default: () => [] }) customGroups;
  @Prop({ default: 0 }) nonGroupNum;
  @Prop({ default: 0 }) metricNum;
  showAddGroupDialog = false;
  /** 当前拖拽id */
  dragId = '';
  dragoverId = '';
  topGroupList: IGroup[] = [
    { id: ALL_LABEL, name: this.$t('全部') as string, icon: 'icon-mc-all' },
    { id: NULL_LABEL, name: this.$t('未分组') as string, icon: 'icon-mc-full-folder' },
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

  created() { }

  getCountByType(type: string) {
    const countMap = {
      [ALL_LABEL]: this.metricNum,
      [NULL_LABEL]: this.nonGroupNum,
    };
    return countMap[type];
  }

  /** 分割线 ================================ */
  handleMenuClick(item) {
    // TODO
    console.log(item);
  }

  getDimensionCmp() {
    return <div>{/* TOOD */}</div>;
  }

  handleAddGroup() {
    // TODO
    this.showAddGroupDialog = true;
  }
  @Emit('handleClickSlider')
  handleClickSlider(v: boolean): boolean {
    return v;
  }
  // @Emit('changeGroup')
  changeSelectedLabel(id: string) {
    if (id === this.selectedLabel) return;
    this.$emit('changeGroup', id);
  }

  render() {
    return (
      <div class='metric-list-content'>
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
              {/* <div class={{ group: true, 'group-selected': true }}>
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
              </div> */}
              {this.topGroupList.map(group => (
                <div
                  key={group.id}
                  class={['group', this.selectedLabel === group.id ? 'group-selected' : '']}
                  onClick={() => this.changeSelectedLabel(group.id)}
                >
                  <div class='group-name'>
                    <i class={`icon-monitor ${group.icon}`} />
                    {group.name}
                  </div>
                  <div class='group-count'>{this.getCountByType(group.id)}</div>
                </div>
              ))}
            </div>
            <div class='custom-group-set'>
              <div
                class='add-group icon-monitor icon-a-1jiahao icon-arrow-left'
                onClick={this.handleAddGroup}
              />
              <bk-input
                ext-cls='search-group'
                placeholder={window.i18n.tc('搜索 自定义分组名称')}
                right-icon='icon-monitor icon-mc-search'
              />
            </div>
            {this.customGroups.length ? (
              <CustomGroupingList
                groupList={this.customGroups}
                selectedLabel={this.selectedLabel}
                onChangeGroup={this.changeSelectedLabel}
                {...{
                  on: {
                    ...this.$listeners,
                  },
                }}
              />
            ) : (
              <div class='empty-group'>
                <div class='empty-img'>
                  <img
                    alt=''
                    src={emptyImageSrc}
                  />
                </div>
                <div class='empty-text'>{this.$t('暂无自定义分组')}</div>
                <div
                  class='add-group'
                  onClick={this.handleAddGroup}
                >
                  {this.$t('新建')}
                </div>
              </div>
            )}
            {
              <AddGroupDialog
                show={this.showAddGroupDialog}
                onShow={v => (this.showAddGroupDialog = v)}
              />
            }
          </div>
        </div>
        <div class='right'>
          <IndicatorTable
            // metricTable={this.metricTable}
            showAutoDiscover={this.selectedLabel === ALL_LABEL}
            unitList={this.unitList}
            onHandleClickSlider={this.handleClickSlider}
            // onUpdateAllSelection={}
            {...{
              props: this.$attrs,
              on: {
                ...this.$listeners,
              },
            }}
          />
        </div>
      </div>
    );
  }
}
