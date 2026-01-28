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
import { Component, Prop, Ref, InjectReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { ALL_LABEL, NULL_LABEL, type IGroupListItem } from '../../../../type';
import EditGroupDialog from '../edit-group';
import type { IGroupingRule } from '../../../../../service';
import type { RequestHandlerMap } from '../../../../type';

import './index.scss';

interface IProps {
  /** 分组列表 */
  groupList: IGroupListItem[];
  /** 指标总数 */
  metricNum: number;
  /** 未分组指标数量 */
  nonGroupNum: number;
  /** 是否为搜索模式 */
  isSearchMode: boolean;
  /** 分组映射表，key为分组名称，value为分组信息 */
  groupsMap: Map<string, IGroupListItem>;
}

interface IEmits {
  onEditGroupSuccess: (config: Partial<IGroupingRule>, isCreate: boolean) => void;
  onGroupDelByName: (name: string) => void;
  onChangeGroup: (groupInfo: { id: number; name: string }) => void;
}

@Component
export default class CustomGroupingList extends tsc<IProps, IEmits> {
  @Prop({ default: () => [] }) groupList: IProps['groupList'];
  @Prop({ default: 0 }) metricNum: number;
  @Prop({ default: 0 }) nonGroupNum: IProps['nonGroupNum'];
  @Prop({ default: false }) isSearchMode: IProps['isSearchMode'];
  @Prop({ default: () => new Map() }) groupsMap: IProps['groupsMap'];

  @InjectReactive('timeSeriesGroupId') readonly timeSeriesGroupId: number;
  @InjectReactive('requestHandlerMap') readonly requestHandlerMap: RequestHandlerMap;
  @InjectReactive('isAPM') readonly isAPM: boolean;
  @InjectReactive('appName') readonly appName: string;
  @InjectReactive('serviceName') readonly serviceName: string;

  @Ref('editGroupDialogRef') readonly editGroupDialogRef!: InstanceType<typeof EditGroupDialog>;
  @Ref('groupListRef') readonly groupListRef!: HTMLDivElement;

  /** 是否为编辑模式，false表示新增模式 */
  isEdit = false;
  /** 控制删除模态框显示/隐藏 */
  showDelDialog = false;
  /** 当前选中的分组信息 */
  selectedGroupInfo = { id: 0, name: ALL_LABEL };
  /** 当前编辑的分组信息 */
  currentGroupInfo: IGroupingRule = {
    scope_id: 0,
    name: '',
    auto_rules: [],
    metric_list: [],
    metric_count: 0,
    create_from: 'user',
  };

  /** 顶部分组列表（全部、未分组） */
  topGroupList = [
    { id: ALL_LABEL, name: this.$t('全部') as string, icon: 'icon-all' },
    { id: NULL_LABEL, name: this.$t('默认分组') as string, icon: 'icon-FileFold-Close' },
  ];

  /** 搜索关键词 */
  searchGroupKeyword = '';

  /** 控制新增/编辑分组模态框显示/隐藏 */
  showAddGroupDialog = false;
  /** 待删除的分组名称 */
  delGroupName = '';
  /** 是否为初始化 */
  isInit = false;

  /**
   * 过滤后的自定义分组列表
   * 根据搜索关键词过滤分组，如果无关键词则返回全部自定义分组
   */
  get filteredCustomGroups() {
    this.isSearchMode = Boolean(this.searchGroupKeyword);
    if (!this.searchGroupKeyword) return this.renderGroupList;
    const keyword = this.searchGroupKeyword.toLowerCase();
    const filterList = this.renderGroupList.filter(group => group.name.toLowerCase().includes(keyword));
    return filterList;
  }

  /**
   * 获取分组名称列表
   */
  get groupNameList(): string[] {
    return this.groupList.map(item => item.name);
  }

  /**
   * 渲染的分组列表
   * 过滤掉"未分组"项，只返回自定义分组
   */
  get renderGroupList() {
    return this.groupList.filter(item => item.name !== NULL_LABEL);
  }

  @Watch('groupList', { immediate: true })
  handleGroupListChange(list: IGroupListItem[]) {
    if (list.length > 0 && !this.isInit) {
      this.isInit = true;
      if (this.isAPM) {
        const viewPayload = JSON.parse(this.$route.query.viewPayload as string);
        const { metrics } = viewPayload;
        if (metrics.length > 0) {
          const [firstMetric] = metrics;
          const activeGroup = this.groupList.find(item => item.name === firstMetric.scope_name);
          this.changeSelectedLabel({
            id: activeGroup?.scopeId || 0,
            name: activeGroup?.name || '',
          });
        }
        return;
      }
      this.changeSelectedLabel(
        {
          id: -1,
          name: ALL_LABEL,
        },
        true
      );
    }
  }

  // handleMenuClick(type: 'delete' | 'edit', groupName) {
  //   // TODO[中等]
  //   this.$emit('menuClick', type, groupName);
  // }

  // 拖拽开始，记录当前拖拽的ID
  // handleDragstart(index: number, e) {
  //   this.dragId = index.toString();
  // }

  /**
   * 处理新增分组操作
   * 打开新增分组对话框
   */
  handleAddGroup() {
    this.showAddGroupDialog = true;
  }

  // 拖拽经过事件，设置当前拖拽ID
  // handleDragover(index: number, e: DragEvent) {
  //   e.preventDefault();
  //   this.dragoverId = index.toString();
  // }

  // 拖拽离开事件，清除当前拖拽的ID
  // handleDragleave() {
  //   this.dragoverId = '';
  // }

  // @Emit('groupListOrder')
  // saveGroupRuleOrder(tab) {
  //   this.$store.dispatch('custom-escalation/saveGroupingRuleOrder', {
  //     time_series_group_id: this.timeSeriesGroupId,
  //     group_names: tab.map(item => item.name),
  //   });
  //   return tab;
  // }

  /**
   * 根据分组类型获取指标数量
   * @param type 分组类型（ALL_LABEL: 全部, NULL_LABEL: 未分组）
   * @returns 指标数量
   */
  getCountByType(type: string) {
    const countMap = {
      [ALL_LABEL]: this.metricNum,
      [NULL_LABEL]: this.nonGroupNum,
    };
    return countMap[type];
  }

  /**
   * 取消新增/编辑分组操作
   * 关闭对话框并重置分组信息
   */
  handleCancel() {
    this.showAddGroupDialog = false;
    this.currentGroupInfo = {
      name: '',
      auto_rules: [],
      metric_list: [],
      scope_id: 0,
      metric_count: 0,
      create_from: 'user',
    };
    this.$nextTick(() => {
      this.isEdit = false;
    });
  }

  /**
   * 提交分组配置（新增或更新）
   * @param config 分组配置信息
   */
  async handleSubmitGroup(config: ServiceParameters<typeof this.requestHandlerMap.createOrUpdateGroupingRule>) {
    const params = {
      time_series_group_id: this.timeSeriesGroupId,
      ...config,
    };
    if (this.isAPM) {
      delete params.time_series_group_id;
      Object.assign(params, {
        app_name: this.appName,
        service_name: this.serviceName,
      });
    }
    const data = await this.requestHandlerMap.createOrUpdateGroupingRule(params);
    Object.assign(config, {
      scope_id: data.scope_id,
    });
    this.showAddGroupDialog = false;
    this.$emit('editGroupSuccess', config, !this.isEdit);
    this.editGroupDialogRef.clear();
  }

  /**
   * 处理搜索输入
   * @param val 搜索关键词
   */
  handleSearchInput(val: string) {
    this.searchGroupKeyword = val;
  }

  /**
   * 处理菜单点击操作（编辑或删除）
   * @param type 操作类型：'delete' | 'edit'
   * @param groupName 分组名称
   */
  handleMenuClick(type: 'delete' | 'edit', groupName) {
    const operationList = {
      /** 删除操作 */
      delete: () => {
        this.showDelDialog = true;
        this.delGroupName = groupName;
      },
      /** 编辑操作 */
      edit: () => {
        const currentGroupInfo = this.groupList.filter(item => item.name === groupName)[0];
        if (currentGroupInfo) {
          this.currentGroupInfo.name = currentGroupInfo.name;
          this.currentGroupInfo.metric_list = currentGroupInfo.metricList || [];
          this.currentGroupInfo.auto_rules = currentGroupInfo.matchRules || [];
          this.currentGroupInfo.scope_id = currentGroupInfo.scopeId;
          this.currentGroupInfo.create_from = currentGroupInfo.createFrom;
          this.isEdit = true;
          this.showAddGroupDialog = true;
        }
      },
    };
    operationList[type]();
  }

  /**
   * 清空搜索关键词
   */
  handleClearSearch() {
    this.searchGroupKeyword = '';
  }

  // 拖拽完成时逻辑
  // handleDrop() {
  //   if (this.dragId !== this.dragoverId) {
  //     const tab = Object.assign([], this.groupList);
  //     const dragIndex = Number.parseInt(this.dragId, 10);
  //     const dragoverIndex = Number.parseInt(this.dragoverId, 10);

  //     const draggedTab = this.groupList[dragIndex];
  //     tab.splice(dragIndex, 1);
  //     tab.splice(dragoverIndex, 0, draggedTab);
  //     this.dragId = '';
  //     this.dragoverId = '';
  //     this.saveGroupRuleOrder(tab);
  //   }
  //   this.dragoverId = '';
  // }

  /**
   * 切换选中的分组
   * @param groupInfo 分组信息，包含id和name
   */
  changeSelectedLabel(groupInfo: { id: number; name: string }, force = false) {
    if (groupInfo.name === this.selectedGroupInfo.name && !force) return;
    this.selectedGroupInfo = groupInfo;
    this.$emit('changeGroup', groupInfo);
  }

  /**
   * 根据分组名称获取该分组下的指标数量
   * @param name 分组名称
   * @returns 指标数量，如果分组不存在则返回0
   */
  getGroupCountByName(name: string) {
    const group = this.groupsMap.get(name);
    if (!group) return 0;
    return group.metricList.length || 0;
  }

  /**
   * 执行删除分组操作
   * 关闭删除对话框并触发删除事件
   */
  async handleDeleteGroup() {
    this.showDelDialog = false;
    this.$emit('groupDelByName', this.delGroupName);
    this.delGroupName = '';
  }

  /**
   * 取消删除操作
   * 关闭删除对话框并清空待删除的分组名称
   */
  handleCancelDel() {
    this.delGroupName = '';
    this.showDelDialog = false;
  }

  scrollListToBottom() {
    this.groupListRef.scrollTop = this.groupListRef.scrollHeight;
  }

  render() {
    return (
      <div class='group-list'>
        <div class='top-group'>
          {this.topGroupList.map(group => (
            <div
              key={group.id}
              class={['group', this.selectedGroupInfo.name === group.id ? 'group-selected' : '']}
              onClick={() =>
                this.changeSelectedLabel({
                  id: group.id === ALL_LABEL ? -1 : 0,
                  name: group.id,
                })
              }
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
            onInput={this.handleSearchInput} // 绑定输入事件
          />
        </div>
        <div
          class='filter-group-list-main'
          ref='groupListRef'
        >
          {this.filteredCustomGroups.length ? ( // 过滤后的列表
            <div class='custom-group'>
              {this.filteredCustomGroups.map(group => (
                <div
                  key={group.name}
                  class={[
                    'group',
                    // this.dragoverId === index.toString() ? 'is-dragover' : '',
                    this.selectedGroupInfo.name === group.name ? 'group-selected' : '',
                  ]}
                  // draggable={!this.isSearchMode}
                  onClick={() =>
                    this.changeSelectedLabel({
                      id: group.scopeId,
                      name: group.name,
                    })
                  }
                  // onDragleave={this.handleDragleave}
                  // onDragover={e => this.handleDragover(index, e)}
                  // onDragstart={e => this.handleDragstart(index, e)}
                  // onDrop={this.handleDrop}
                >
                  {/* {!this.isSearchMode && <i class='icon-monitor icon-mc-tuozhuai item-drag' />} */}
                  <div class='group-name'>
                    <i class='icon-monitor icon-FileFold-Close' />
                    <div
                      v-bk-overflow-tips
                      class='name-text'
                    >
                      {group.name}
                    </div>
                  </div>
                  <div class='group-count'>{this.getGroupCountByName(group.name)}</div>
                  <bk-popover
                    ref='menuPopover'
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
                        class={'more-list-item edit'}
                        onClick={() => this.handleMenuClick('edit', group.name)}
                      >
                        {this.$t('编辑')}
                      </span>
                      {group.createFrom === 'user' && (
                        <span
                          class={'more-list-item delete'}
                          onClick={() => this.handleMenuClick('delete', group.name)}
                        >
                          {this.$t('删除')}
                        </span>
                      )}
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
        <EditGroupDialog
          ref='editGroupDialogRef'
          groupInfo={this.currentGroupInfo}
          isEdit={this.isEdit}
          nameList={this.groupNameList}
          isShow={this.showAddGroupDialog}
          onCancel={this.handleCancel}
          onGroupSubmit={this.handleSubmitGroup}
          {...{
            props: this.$attrs,
          }}
        />
        <bk-dialog
          width={480}
          ext-cls='custom-group-del-dialog-main'
          v-model={this.showDelDialog}
          title={`${this.$t('是否删除该分组?')}`}
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
