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
import { Component, Inject, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce } from 'monitor-common/utils';

import EditGroup from '../edit-group';
import {
  ALL_LABEL,
  GROUP_DEFAULT_NAME,
  type IGroupSubmitPayload,
  type IPluginGroup,
  type ISelectedGroup,
} from '../types';
import { getMetricCount } from '../utils';

import './index.scss';

interface IEmits {
  onChangeGroup: (groupInfo: ISelectedGroup) => void;
  onDeleteGroup: (name: string) => void;
  onSubmitGroup: (payload: IGroupSubmitPayload) => void;
}

interface IProps {
  canManage?: boolean;
  confirmLoading?: boolean;
  groupList: IPluginGroup[];
}

@Component
export default class PluginGroupList extends tsc<IProps, IEmits> {
  @Prop({ default: () => [] }) groupList: IProps['groupList'];
  @Prop({ default: true }) canManage: boolean;
  @Prop({ default: false }) confirmLoading: boolean;

  @Inject({ from: 'authority', default: () => ({ MANAGE_AUTH: true }) }) authority;
  @Inject({ from: 'handleShowAuthorityDetail', default: () => () => {} }) handleShowAuthorityDetail;

  @Ref('groupListRef') readonly groupListRef!: HTMLDivElement;

  selectedGroup: ISelectedGroup = { name: ALL_LABEL };
  searchGroupKeyword = '';
  showAddGroupDialog = false;
  isEdit = false;
  showDelDialog = false;
  delGroupName = '';
  currentGroup: IGroupSubmitPayload = {
    isEdit: false,
    table_name: '',
    table_desc: '',
    rule_list: [],
    fields: [],
  };
  isInit = false;

  topGroupList = [
    { id: ALL_LABEL, name: this.$t('全部') as string, icon: 'icon-all' },
    { id: GROUP_DEFAULT_NAME, name: this.$t('默认分组') as string, icon: 'icon-FileFold-Close' },
  ];

  get customGroups() {
    return this.groupList.filter(item => item.table_name !== GROUP_DEFAULT_NAME);
  }

  get filteredCustomGroups() {
    if (!this.searchGroupKeyword) {
      return this.customGroups;
    }
    const keyword = this.searchGroupKeyword.toLowerCase();
    return this.customGroups.filter(
      group =>
        group.table_name.toLowerCase().includes(keyword) || (group.table_desc || '').toLowerCase().includes(keyword)
    );
  }

  get groupNameList() {
    return this.groupList.map(item => item.table_name);
  }

  get defaultMetricCount() {
    const group = this.groupList.find(item => item.table_name === GROUP_DEFAULT_NAME);
    return group ? getMetricCount(group) : 0;
  }

  get totalMetricCount() {
    return this.groupList.reduce((acc, item) => acc + getMetricCount(item), 0);
  }

  @Watch('groupList', { immediate: true })
  handleGroupListChange(list: IPluginGroup[]) {
    if (list.length > 0 && !this.isInit) {
      this.isInit = true;
      this.changeSelectedLabel({ name: ALL_LABEL }, true);
    }
  }

  getCountByType(type: string) {
    const countMap = {
      [ALL_LABEL]: this.totalMetricCount,
      [GROUP_DEFAULT_NAME]: this.defaultMetricCount,
    };
    return countMap[type];
  }

  changeSelectedLabel(groupInfo: ISelectedGroup, force = false) {
    if (groupInfo.name === this.selectedGroup.name && !force) return;
    this.selectedGroup = groupInfo;
    this.$emit('changeGroup', groupInfo);
  }

  changeSelectedLabelByName(name: string) {
    this.changeSelectedLabel({ name }, true);
  }

  handleAddGroup() {
    if (!this.canManage) {
      this.handleShowAuthorityDetail();
      return;
    }
    this.isEdit = false;
    this.currentGroup = {
      isEdit: false,
      table_name: '',
      table_desc: '',
      rule_list: [],
      fields: [],
    };
    this.showAddGroupDialog = true;
  }

  handleMenuClick(type: 'delete' | 'edit', groupName: string) {
    if (!this.canManage) {
      this.handleShowAuthorityDetail();
      return;
    }
    if (type === 'delete') {
      this.showDelDialog = true;
      this.delGroupName = groupName;
      return;
    }
    const current = this.groupList.find(item => item.table_name === groupName);
    if (current) {
      this.isEdit = true;
      this.currentGroup = {
        isEdit: true,
        oldName: current.table_name,
        table_name: current.table_name,
        table_desc: current.table_desc,
        rule_list: [...(current.rule_list || [])],
        fields: [...(current.fields || [])],
      };
      this.showAddGroupDialog = true;
    }
  }

  @Debounce(300)
  handleSearchInput(val: string) {
    this.searchGroupKeyword = val;
  }

  handleClearSearch() {
    this.searchGroupKeyword = '';
  }

  handleCancel() {
    this.showAddGroupDialog = false;
    this.isEdit = false;
  }

  handleSubmitGroup(payload: IGroupSubmitPayload) {
    this.$emit('submitGroup', payload);
  }

  handleDeleteGroup() {
    this.showDelDialog = false;
    this.$emit('deleteGroup', this.delGroupName);
    this.delGroupName = '';
  }

  handleCancelDel() {
    this.delGroupName = '';
    this.showDelDialog = false;
  }

  scrollToGroup(groupName: string) {
    this.$nextTick(() => {
      const target = this.groupListRef?.querySelector(`[data-group-name="${groupName}"]`) as HTMLElement;
      target?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
  }

  render() {
    return (
      <div class='group-list'>
        <div class='top-group'>
          {this.topGroupList.map(group => (
            <div
              key={group.id}
              class={['group', this.selectedGroup.name === group.id ? 'group-selected' : '']}
              onClick={() => this.changeSelectedLabel({ name: group.id })}
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
            placeholder={this.$t('搜索 自定义分组名称')}
            right-icon='icon-monitor icon-mc-search'
            value={this.searchGroupKeyword}
            clearable
            onInput={this.handleSearchInput}
          />
        </div>
        <div
          ref='groupListRef'
          class='filter-group-list-main'
        >
          {this.filteredCustomGroups.length ? (
            <div class='custom-group'>
              {this.filteredCustomGroups.map(group => (
                <div
                  key={group.table_name}
                  class={['group', this.selectedGroup.name === group.table_name ? 'group-selected' : '']}
                  data-group-name={group.table_name}
                  onClick={() => this.changeSelectedLabel({ name: group.table_name })}
                >
                  <div class='group-name'>
                    <i class='icon-monitor icon-FileFold-Close' />
                    <div
                      class='name-text'
                      v-bk-overflow-tips
                    >
                      {group.table_desc && group.table_desc !== group.table_name
                        ? `${group.table_name}(${group.table_desc})`
                        : group.table_name}
                    </div>
                  </div>
                  <div class='group-count'>{getMetricCount(group)}</div>
                  <bk-popover
                    class='group-popover'
                    ext-cls='group-popover'
                    arrow={false}
                    offset={'0, 0'}
                    placement='bottom-start'
                    theme='light common-monitor'
                  >
                    <span class='more-operation'>
                      <i class='icon-monitor icon-mc-more' />
                    </span>
                    <div
                      class='group-more-list'
                      slot='content'
                    >
                      <span
                        class='more-list-item edit'
                        onClick={() => this.handleMenuClick('edit', group.table_name)}
                      >
                        {this.$t('编辑')}
                      </span>
                      <span
                        class='more-list-item delete'
                        onClick={() => this.handleMenuClick('delete', group.table_name)}
                      >
                        {this.$t('删除')}
                      </span>
                    </div>
                  </bk-popover>
                </div>
              ))}
            </div>
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
        <EditGroup
          confirmLoading={this.confirmLoading}
          groupInfo={this.currentGroup}
          isEdit={this.isEdit}
          isShow={this.showAddGroupDialog}
          nameList={this.groupNameList}
          onCancel={this.handleCancel}
          onGroupSubmit={this.handleSubmitGroup}
        />
        <bk-dialog
          width={480}
          ext-cls='custom-group-del-dialog-main'
          v-model={this.showDelDialog}
          title={this.$t('是否删除该分组?')}
        >
          <div class='content-main'>
            <div class='group-namme-main'>
              <div class='title-main'>{this.$t('分组名称')}:</div>
              <div class='name-main'>{this.delGroupName}</div>
            </div>
            <div class='tip-main'>{this.$t('删除后该分组下的指标将自动挪入<默认分组>')}</div>
            <div class='operation-btn-main'>
              <bk-button
                class='operate-btn'
                theme='danger'
                onClick={this.handleDeleteGroup}
              >
                {this.$t('删除')}
              </bk-button>
              <bk-button
                class='operate-btn'
                onClick={this.handleCancelDel}
              >
                {this.$t('取消')}
              </bk-button>
            </div>
          </div>
        </bk-dialog>
      </div>
    );
  }
}
