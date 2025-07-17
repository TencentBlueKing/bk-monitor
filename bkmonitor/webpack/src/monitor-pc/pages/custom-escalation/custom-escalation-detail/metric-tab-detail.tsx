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

import AddGroupDialog from './add-group-dialog';
import CustomGroupingList from './custom-grouping-list';
import IndicatorTable from './metric-table';
import { ALL_LABEL, NULL_LABEL } from './type';

import './metric-tab-detail.scss';

interface IGroup {
  id: string;
  name: string;
  icon: string;
}
@Component({
  inheritAttrs: false,
})
export default class MetricTabDetail extends tsc<any, any> {
  @Prop({ default: '' }) selectedLabel;
  @Prop({ default: () => [] }) customGroups;
  @Prop({ default: 0 }) nonGroupNum;
  @Prop({ default: 0 }) metricNum;

  searchGroupKeyword = ''; // 搜索关键词

  /** 控制新增模态框 */
  showAddGroupDialog = false;
  /** 控制删除模态框 */
  showDelDialog = false;

  currentGroupInfo = {
    name: '',
    rules: '',
    manualList: [],
  };
  isEdit = false;
  /** 当前拖拽id */
  dragId = '';
  dragoverId = '';
  topGroupList: IGroup[] = [
    { id: ALL_LABEL, name: this.$t('全部') as string, icon: 'icon-all' },
    { id: NULL_LABEL, name: this.$t('未分组') as string, icon: 'icon-FileFold-Close' },
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
  isSearchMode: boolean;
  delGroupName = '';

  created() {}

  // 过滤后的自定义分组
  get filteredCustomGroups() {
    this.isSearchMode = Boolean(this.searchGroupKeyword);
    if (!this.searchGroupKeyword) return this.customGroups;
    const keyword = this.searchGroupKeyword.toLowerCase();
    return this.customGroups.filter(group => group.name.toLowerCase().includes(keyword));
  }

  /**
   * 获取分组名称列表
   */
  get groupNameList(): string[] {
    return this.customGroups.map(item => item.name);
  }

  // 搜索处理函数
  handleSearchInput(val: string) {
    this.searchGroupKeyword = val;
  }

  getCountByType(type: string) {
    const countMap = {
      [ALL_LABEL]: this.metricNum,
      [NULL_LABEL]: this.nonGroupNum,
    };
    return countMap[type];
  }

  /** 分割线 ================================ */
  handleMenuClick(type: 'delete' | 'edit', groupName) {
    const operationList = {
      /** 删除操作 */
      delete: () => {
        this.showDelDialog = true;
        this.delGroupName = groupName;
      },
      /** 编辑操作 */
      edit: () => {
        const currentGroupInfo = this.customGroups.filter(item => item.name === groupName)[0];
        if (currentGroupInfo) {
          this.currentGroupInfo.name = currentGroupInfo.name;
          this.currentGroupInfo.manualList = currentGroupInfo.manualList || [];
          this.currentGroupInfo.rules = currentGroupInfo.matchRules[0] || '';
          this.isEdit = true;
          this.showAddGroupDialog = true;
        }
      },
    };
    operationList[type]();
  }

  handleClearSearch() {
    this.searchGroupKeyword = '';
  }

  handleAddGroup() {
    // TODO
    this.showAddGroupDialog = true;
  }

  // @Emit('changeGroup')
  changeSelectedLabel(id: string) {
    if (id === this.selectedLabel) return;
    this.$emit('changeGroup', id);
  }

  handleCancel(v: boolean) {
    this.showAddGroupDialog = v;
    this.currentGroupInfo = {
      name: '',
      rules: '',
      manualList: [],
    };
    this.$nextTick(() => {
      this.isEdit = false;
    });
  }

  @Emit('groupSubmit')
  submitGroup(config) {
    this.showAddGroupDialog = false;
    this.$nextTick(() => {
      this.isEdit = false;
    });
    return config;
  }

  async handleDelFunction() {
    this.showDelDialog = false;
    this.$emit('groupDelByName', this.delGroupName);
    this.delGroupName = '';
  }

  handleCancelDel() {
    this.delGroupName = '';
    this.showDelDialog = false;
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
              {this.topGroupList.map(group => (
                <div
                  key={group.id}
                  class={['group', this.selectedLabel === group.id ? 'group-selected' : '']}
                  onClick={() => this.changeSelectedLabel(group.id)}
                >
                  <div class='group-name'>
                    <i class={`icon-monitor ${group.icon}`} />
                    <span>{group.name}</span>
                  </div>
                  <div class='group-count'>{this.getCountByType(group.id)}</div>
                </div>
              ))}
            </div>
            <div class='custom-group-set'>
              <div
                class='add-group icon-monitor icon-a-1jiahao'
                onClick={this.handleAddGroup}
              />
              <bk-input
                ext-cls='search-group'
                placeholder={window.i18n.tc('搜索 自定义分组名称')}
                right-icon='icon-monitor icon-mc-search'
                value={this.searchGroupKeyword}
                onInput={this.handleSearchInput} // 绑定输入事件
              />
            </div>
            <div class='filter-group-list-main'>
              {this.filteredCustomGroups.length ? ( // 过滤后的列表
                <CustomGroupingList
                  groupList={this.filteredCustomGroups}
                  isSearchMode={this.isSearchMode}
                  selectedLabel={this.selectedLabel}
                  onChangeGroup={this.changeSelectedLabel}
                  onMenuClick={this.handleMenuClick}
                  {...{
                    on: {
                      ...this.$listeners,
                    },
                    props: this.$attrs,
                  }}
                />
              ) : (
                <div>
                  {this.searchGroupKeyword ? (
                    <div class='empty-group'>
                      <div class='empty-img'>
                        <bk-exception
                          scene='part'
                          type='search-empty'
                        >
                          <span class='empty-text'>{this.$t('搜索结果为空')}</span>
                        </bk-exception>
                      </div>
                      <div
                        class='add-group'
                        onClick={this.handleClearSearch}
                      >
                        {this.$t('清空关键词')}
                      </div>
                    </div>
                  ) : (
                    <div class='empty-group'>
                      <div class='empty-img'>
                        <bk-exception
                          class='exception-wrap-item exception-part'
                          scene='part'
                          type='empty'
                        >
                          <span class='empty-text'>{this.$t('暂无自定义分组')}</span>
                        </bk-exception>
                      </div>
                      <div
                        class='add-group'
                        onClick={this.handleAddGroup}
                      >
                        {this.$t('新建')}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
            {
              <AddGroupDialog
                groupInfo={this.currentGroupInfo}
                isEdit={this.isEdit}
                nameList={this.groupNameList}
                show={this.showAddGroupDialog}
                onCancel={this.handleCancel}
                onGroupSubmit={this.submitGroup}
                {...{
                  props: this.$attrs,
                }}
              />
            }
          </div>
        </div>
        <div class='right'>
          <IndicatorTable
            showAutoDiscover={this.selectedLabel === ALL_LABEL}
            {...{
              props: this.$attrs,
              on: {
                ...this.$listeners,
              },
            }}
            onShowAddGroup={v => (this.showAddGroupDialog = v)}
          />
        </div>
        <bk-dialog
          v-model={this.showDelDialog}
          header-position='left'
          title={`${this.$t('确认删除')}？`}
          onCancel={this.handleCancelDel}
          onConfirm={this.handleDelFunction}
        />
      </div>
    );
  }
}
