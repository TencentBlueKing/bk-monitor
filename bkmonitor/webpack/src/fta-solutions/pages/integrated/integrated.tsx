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

import EmptyStatus from 'monitor-pc/components/empty-status/empty-status';

import IntegratedModule from '../../store/modules/integrated';
import MonitorDrag from '../event/monitor-drag';
import CheckboxTree, { type ICheckedData } from './checkbox-tree';
import ContentGroupItem, { type IPluginDetail, type OperateType } from './content-group-item';
import EventSourceDetail from './event-source-detail/event-source-detail';
import Group, { type IGroupData } from './group';
import Header, { type ViewType } from './header';
import InstallPluginDialog, { type IData as ICurrentPluginData } from './install-plugin-dialog';
import List from './list';
import IntegratedCardSkeleton from './skeleton/integrated-card-skeleton';
import IntegratedFilterSkeleton from './skeleton/integrated-filter-skeleton';

import type { MapType } from './status-tips';
import type { EmptyStatusOperationType, EmptyStatusType } from 'monitor-pc/components/empty-status/types';

import './integrated.scss';

interface IIntegratedProps {
  name: string;
}

Component.registerHooks(['beforeRouteEnter']);
@Component({ name: 'integrated' })
export default class Integrated extends tsc<IIntegratedProps> {
  loading = false;
  isShowDetail = false;
  curDetailId = '';
  curDetailVersion = '';
  viewType: ViewType = 'card';
  filterPanelData: IGroupData[] = [];
  defaultActiveFilterGroup = ['main_type', 'status', 'scenario', 'tags'];
  pluginData: IGroupData[] = [];
  defaultActiveContentGroup = ['INSTALLED', 'AVAILABLE'];
  showInstallDialog = false;
  currentPluginData: ICurrentPluginData = null;
  searchKey = '';
  checkedData: MapType<'main_type' | 'scenario' | 'status' | 'tags'> = {};
  listPluginData: IGroupData[] = [];
  filterWidth = 250;
  emptyType: EmptyStatusType = 'search-empty';
  created() {
    this.getData();
  }
  beforeRouteEnter(to, from, next) {
    next(vm => {
      !vm.loading && vm.getData();
    });
  }
  getDefaultPluginData(): IGroupData[] {
    return [
      {
        id: 'INSTALLED',
        name: this.$t('已安装'),
        data: [],
      },
      {
        id: 'DISABLED',
        name: this.$t('已停用'),
        data: [],
      },
      {
        id: 'AVAILABLE',
        name: this.$t('可用'),
        data: [],
      },
    ];
  }
  async getData() {
    this.loading = true;
    this.filterPanelData = [];
    this.pluginData = this.getDefaultPluginData();
    const params = {
      page: 1,
      page_size: -1,
      search_key: this.searchKey,
      // plugin_type: this.checkedData?.['plugin_type']?.length ? this.checkedData.plugin_type.join(',') : '',
      // status: this.checkedData?.['status']?.length ? this.checkedData.status.join(',') : ''
    };
    const { list, count, emptyType } = await IntegratedModule.getPluginEvent(params);
    this.emptyType = emptyType ? emptyType : list?.length ? 'search-empty' : 'empty';
    // 统计数据
    const keyMap = {
      main_type: this.$t('方式'),
      status: this.$t('状态'),
      tags: this.$t('标签'),
      scenario: this.$t('分类'),
    };
    Object.keys(count).forEach(key => {
      const groupData = this.filterPanelData.find(item => item.id === key);
      const item = count[key];
      if (!groupData) {
        this.filterPanelData.push({
          id: key,
          name: keyMap[key],
          data: [...item],
        });
      } else {
        groupData.data.push(...item);
      }
    });

    const pluginTypeMap = {
      event: this.$t('事件插件'),
      service: this.$t('周边服务'),
    };
    // 插件数据
    list.forEach(item => {
      // 非可用和已停用状态的插件就是“已安装”状态
      // const id = ['DISABLED', 'AVAILABLE'].includes(item.status) ? item.status : 'INSTALLED';
      // 根据is_install判断已安装与可用 false 为空可用 true为已安装
      const id = item.is_installed ? 'INSTALLED' : 'AVAILABLE';
      const categoryData = this.pluginData.find(data => data.id === id);
      if (!categoryData) return;
      // 二级分组（事件插件、周边服务）
      const typeData = categoryData.data.find(data => data.id === item.category);
      if (typeData) {
        typeData.data.push({ ...item, show: true });
      } else {
        categoryData.data.push({
          id: item.category,
          name: pluginTypeMap[item.category],
          data: [{ ...item, show: true }],
        });
      }
    });
    this.filterPluginData();
    this.loading = false;
  }
  // 搜索过滤
  filterPluginData() {
    const { status = [], main_type: pluginType = [], scenario = [], tags = [] } = this.checkedData;
    const list = this.pluginData;
    list.forEach(item =>
      item.data.forEach(set =>
        set.data.forEach((child: IPluginDetail) => {
          const isShow =
            (pluginType.length === 0 || pluginType.includes(child.main_type)) &&
            (status.length === 0 || status.includes(child.status)) &&
            (scenario.length === 0 || scenario.includes(child.scenario)) &&
            (tags.length === 0 || child.tags.some(tag => tags.includes(tag))) &&
            this.matchSearchKey(child);
          this.$set(child, 'show', isShow);
        })
      )
    );
    this.listPluginData = list.filter(
      item => item.data.length && item.data.some(set => set?.data?.some(child => child.show))
    );
  }
  // 关键字匹配

  matchSearchKey(data: IPluginDetail) {
    const matchParams = [
      'plugin_display_name',
      'main_type_display',
      'scenario_display',
      'plugin_id',
      'update_user',
      'create_user',
      'author',
    ];
    return matchParams.some(
      key => String(data[key]).toLocaleLowerCase().indexOf(this.searchKey.toLocaleLowerCase()) > -1
    );
  }
  /**
   * 筛选面板 slots
   * @param item 当前分组信息
   */
  filterGroupSlot(item: IGroupData) {
    return (
      <CheckboxTree
        ref={`checkboxtree${item.id}`}
        data={item.data}
        onChange={v => this.handleCheckedChange(item.id, v)}
      />
    );
  }

  // 勾选事件变更（清空也会触发）
  handleCheckedChange(id: number | string, data: ICheckedData[]) {
    this.checkedData[id] = data.reduce((pre, cur) => [...pre, ...cur.values], []);
    this.filterPluginData();
  }

  /** 空状态处理 */
  handleEmptyOperate(type: EmptyStatusOperationType) {
    if (type === 'clear-filter') {
      this.searchKey = '';
      this.handleSearchValueChange('');
      for (const checkboxRefKey of Object.keys(this.$refs)) {
        if (checkboxRefKey.match(/^checkboxtree(\w+)/)) {
          (this.$refs[checkboxRefKey] as CheckboxTree)?.clearChecked?.();
        }
      }
      return;
    }

    if (type === 'refresh') {
      this.getData();
      return;
    }
  }

  /**
   * 插件panel slots
   * @param item 当前分组信息
   * @returns
   */
  contentGroupSlot(item: IGroupData) {
    return this.viewType === 'card' ? (
      <ContentGroupItem
        data={item}
        onOperate={this.handlePluginOperate}
      />
    ) : (
      <List
        data={item}
        emptyType={this.emptyType}
        onEmptyOperate={this.handleEmptyOperate}
        onOperate={this.handlePluginOperate}
      />
    );
  }

  /**
   * 插件操作
   * @param param0
   */
  handlePluginOperate({ type, item }: { item: IPluginDetail; type: OperateType }) {
    switch (type) {
      case 'detail':
        this.curDetailId = item.plugin_id;
        this.curDetailVersion = item.version;
        this.isShowDetail = true;
        break;
      case 'install':
        this.currentPluginData = {
          version: item.version,
          pluginId: item.plugin_id,
          paramsSchema: null,
          pluginDisplayName: item.plugin_display_name,
        };
        this.showInstallDialog = true;
        break;
      default:
        this.curDetailId = item.plugin_id;
        this.curDetailVersion = item.version;
        this.isShowDetail = true;
        break;
    }
  }

  /**
   * 视图类型
   * @param type
   */
  handleViewTypeChange(type: ViewType) {
    this.viewType = type;
  }

  /**
   * 关键字搜索
   * @param value
   */
  handleSearchValueChange(value: string) {
    this.searchKey = value;
    this.filterPluginData();
  }

  /**
   * 清空当前分组勾选
   * @param item
   */
  handleClearChecked(item: IGroupData) {
    const ref = this.$refs[`checkboxtree${item.id}`] as CheckboxTree;

    ref?.clearChecked();
  }

  handleDragFilter(v: number) {
    this.filterWidth = v;
  }

  /* 导入成功 */
  handleImportSuccess() {
    this.getData();
  }

  handleInstall(data) {
    this.isShowDetail = false;
    this.currentPluginData = data;
    this.showInstallDialog = true;
  }
  /* 安装成功 */
  handleInstallSuccess() {
    this.getData();
  }

  render() {
    return (
      <section
        class='integrated'
        // v-bkloading={{ isLoading: this.loading }}
      >
        {/* 筛选条件 */}
        <div
          style={{
            width: `${this.filterWidth}px`,
            flexBasis: `${this.filterWidth}px`,
            display: this.filterWidth > 200 ? 'flex' : 'none',
          }}
          class='integrated-filter'
        >
          {this.loading ? (
            <IntegratedFilterSkeleton />
          ) : (
            <Group
              scopedSlots={{
                default: ({ item }) => this.filterGroupSlot(item),
              }}
              data={this.filterPanelData}
              defaultActiveName={this.defaultActiveFilterGroup}
              theme='filter'
              onActiveChange={v => (this.defaultActiveFilterGroup = v)}
              onClear={this.handleClearChecked}
            />
          )}
          <MonitorDrag on-move={this.handleDragFilter} />
        </div>
        {/* 插件内容 */}
        <div class='integrated-content'>
          <Header
            filterWidth={this.filterWidth}
            searchValue={this.searchKey}
            on-set-filter={() => (this.filterWidth = 250)}
            onImportSuccess={this.handleImportSuccess}
            onSearchValueChange={this.handleSearchValueChange}
            onViewChange={this.handleViewTypeChange}
          />
          {/* 过滤空组 */}
          {(() => {
            if (this.loading) {
              return <IntegratedCardSkeleton />;
            }
            return this.listPluginData?.length ? (
              <Group
                scopedSlots={{
                  default: ({ item }) => this.contentGroupSlot(item),
                }}
                data={this.listPluginData}
                defaultActiveName={this.defaultActiveContentGroup}
                theme='bold'
                onActiveChange={v => (this.defaultActiveContentGroup = v)}
              />
            ) : (
              <div class='integrated-content-empty'>
                {!this.loading ? (
                  <EmptyStatus
                    type={this.emptyType}
                    onOperation={this.handleEmptyOperate}
                  />
                ) : undefined}
              </div>
            );
          })()}
        </div>
        <EventSourceDetail
          id={this.curDetailId}
          v-model={this.isShowDetail}
          version={this.curDetailVersion}
          onInstall={data => this.handleInstall(data)}
        />
        <InstallPluginDialog
          v-model={this.showInstallDialog}
          data={this.currentPluginData}
          onSuccess={this.handleInstallSuccess}
        />
      </section>
    );
  }
}
