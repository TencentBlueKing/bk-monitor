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
import { Component, Prop, ProvideReactive, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';
import { getFunctions } from 'monitor-api/modules/grafana';

import MonitorImport from '../../../../../components/monitor-import/monitor-import.vue';
import { downCsvFile } from '../../../../view-detail/utils';
import {
  validateCustomTsMetricFieldName,
  createOrUpdateGroupingRule,
  customTsGroupingRuleList,
  deleteGroupingRule,
  exportCustomTimeSeriesFields,
  getCustomTsFields,
  getUnitList,
  importCustomTimeSeriesFields,
  modifyCustomTsFields,
  previewGroupingRule,
} from '../../../service';
import { type IGroupListItem, type RequestHandlerMap, ALL_LABEL, NULL_LABEL } from '../../type';
import { matchRuleFn } from '../../utils';
import DimensionList from './components/dimension-list';
import GroupList from './components/group-list';
import MetricList from './components/metric-list';

import type { ICustomTsFields } from '../../index';

import './index.scss';

/**
 * 指标分组映射项接口
 */
export interface IMetricGroupMapItem {
  /** 分组名称列表 */
  groups: string[];
  /** 匹配类型映射，key 为分组名称，value 为匹配类型数组（'auto' | 'manual'） */
  matchType: Record<string, string[]>;
}

/** 创建或更新分组规则的参数类型 */
type CreateOrUpdateGroupingRuleParams = ServiceParameters<typeof createOrUpdateGroupingRule>;

/**
 * 组件 Props 接口
 */
interface IProps {
  /** 是否为 APM 页面 */
  isAPMPage?: boolean;
  /** 时间序列分组 ID */
  metricId?: number;
  tab?: 'dimension' | 'metric';
}

/**
 * 指标/维度管理组件
 * 作为核心容器组件，负责：
 * - 管理分组数据和指标/维度之间的映射关系
 * - 协调左侧分组列表与右侧指标/维度表格的联动
 * - 处理导入、导出、批量分组等全局操作
 */
@Component({
  inheritAttrs: false,
})
export default class IndicatorDimension extends tsc<IProps, any> {
  /** 时间序列分组 ID */
  @Prop({ default: 0 }) metricId: IProps['metricId'];
  /** 指标名称，用于导出文件命名 */
  @Prop({ default: '' }) metricName: string;
  /** 是否为 APM 页面模式（使用 app_name/service_name 替代 time_series_group_id） */
  @Prop({ default: false }) isAPMPage: boolean;
  /** 默认激活的标签页 */
  @Prop({ default: 'metric' }) tab: IProps['tab'];
  @Prop({
    default: () => ({
      validateCustomTsMetricFieldName,
      createOrUpdateGroupingRule,
      exportCustomTimeSeriesFields,
      previewGroupingRule,
      deleteGroupingRule,
      importCustomTimeSeriesFields,
      customTsGroupingRuleList,
      modifyCustomTsFields,
      getCustomTsFields,
      getFunctions,
      getUnitList,
    }),
  })
  requestMap: RequestHandlerMap;

  @ProvideReactive('timeSeriesGroupId') timeSeriesGroupId: IProps['metricId'];
  @ProvideReactive('isAPM') isAPM: boolean;
  @ProvideReactive('requestHandlerMap') requestHandlerMap: RequestHandlerMap & { getFunctions?: () => Promise<any[]> };
  @ProvideReactive('metricFunctions') metricFunctions: any[] = [];
  @ProvideReactive('appName') appName = this.$route.query['filter-app_name'] as string;
  @ProvideReactive('serviceName') serviceName = this.$route.query['filter-service_name'] as string;
  /** 分组列表组件的引用 */
  @Ref('customGroupingListRef') readonly customGroupingListRef!: InstanceType<typeof GroupList>;
  @Ref('metricListRef') readonly metricListRef!: InstanceType<typeof MetricList>;

  /** 每个组所包含的指标映射，key 为分组名称，value 为分组信息 */
  groupsMap: Map<string, IGroupListItem> = new Map();
  /** 分组过滤列表，用于筛选指标 */
  groupFilterList: string[] = [];
  /** 当前选中的分组信息 */
  selectedGroupInfo = { id: 0, name: '' };
  /** 分组管理列表 */
  groupList: IGroupListItem[] = [];
  /** 每个指标包含的组映射，key 为指标名称，value 为分组信息 */
  metricGroupsMap: Map<string, IMetricGroupMapItem> = new Map();
  /** 每个匹配规则包含的指标映射，key 为匹配规则，value 为匹配到的指标名称数组 */
  matchRulesMap: Map<string, string[]> = new Map();
  /** 标签页配置列表 */
  tabs = [
    {
      title: this.$t('指标'),
      id: 'metric',
    },
    {
      title: this.$t('维度'),
      id: 'dimension',
    },
  ];
  /** 当前激活的标签页 ID */
  activeTab = this.tabs[0].id;
  /** 是否显示右侧帮助栏 */
  isShowRightWindow = true;
  /** 单位列表，用于指标单位的展示和选择 */
  unitList: ServiceReturnType<typeof this.requestHandlerMap.getUnitList> = [];

  /** 指标维度数据，包含指标列表和额外的选择状态、监控类型等信息 */
  metricList: (ICustomTsFields['list'][number] & { selection: boolean })[] = [];
  /** 分组列表加载状态 */
  groupListloading = false;

  /**
   * 根据当前选中的分组获取维度表格数据
   * - 选中"全部"分组（id === -1）时，返回所有分组的维度合集
   * - 选中特定分组时，仅返回该分组的维度列表
   */
  get dimensionTable() {
    const groupId = this.selectedGroupInfo.id;
    if (groupId === -1) {
      return this.groupList.flatMap(item =>
        item.dimensionConfig.map(configItem =>
          Object.assign({}, configItem, { scope: { id: item.scopeId, name: item.name } })
        )
      );
    }
    const targetGroup = this.groupList.find(item => item.scopeId === groupId);
    if (targetGroup) {
      return targetGroup.dimensionConfig.map(item =>
        Object.assign({}, item, { scope: { id: targetGroup.scopeId, name: targetGroup.name } })
      );
    }
    return [];
  }

  /**
   * 获取分组选择列表，用于下拉选择组件
   * @returns 分组选择列表，包含 id 和 name
   */
  get groupSelectList() {
    return this.groupList.reduce<{ id: number; name: string }[]>((dataList, item) => {
      if (item.name) {
        dataList.push({
          id: item.scopeId,
          name: item.name,
        });
      }
      return dataList;
    }, []);
  }

  /**
   * 获取默认分组信息（未分组）
   * @returns 默认分组信息对象
   */
  get defaultGroupInfo() {
    const group = this.groupList.find(item => item.name === NULL_LABEL);
    return {
      id: group?.scopeId || 0,
      name: group?.name || '',
    };
  }

  /** 监听 tab 属性变化，同步到当前激活的标签页 */
  @Watch('tab', { immediate: true })
  onTabChange(newVal: IProps['tab']) {
    this.activeTab = newVal;
  }

  /** 监听请求方法映射变化，同步到 provide 注入值 */
  @Watch('requestMap', { immediate: true })
  onRequestMapChange(newVal: RequestHandlerMap) {
    this.requestHandlerMap = newVal;
  }

  /** 监听 isAPMPage 和 metricId 变化，重新加载数据 */
  @Watch('isAPMPage', { immediate: true })
  @Watch('metricId', { immediate: true })
  onMetricIdChange() {
    this.isAPM = this.isAPMPage;
    if (this.metricId || this.isAPM) {
      this.timeSeriesGroupId = this.metricId;
      this.$nextTick(() => {
        this.metricListRef?.handleGetCustomTsFields();
        this.getGroupList();
      });
    }
  }

  /**
   * 组件创建时的生命周期钩子
   * 从路由参数中获取激活的标签页，如果没有则使用默认的第一个标签页
   */
  created() {
    this.handleGetMetricFunctions();
    this.handleGetUnitList();
  }

  /**
   * 加载静态数据（单位列表）
   */
  async handleGetUnitList(): Promise<void> {
    try {
      const unitList = await this.requestHandlerMap.getUnitList();
      this.unitList = unitList;
    } catch (error) {
      console.error('加载静态数据失败:', error);
    }
  }

  /**
   * 获取指标函数列表
   */
  async handleGetMetricFunctions(): Promise<void> {
    this.metricFunctions = await this.requestHandlerMap.getFunctions().catch(() => []);
  }

  /**
   * 处理导出指标数据
   */
  async handleExportMetric() {
    const params = {
      time_series_group_id: this.timeSeriesGroupId,
    };
    if (this.isAPM) {
      delete params.time_series_group_id;
      Object.assign(params, {
        app_name: this.appName,
        service_name: this.serviceName,
      });
    }
    const template = await this.requestHandlerMap.exportCustomTimeSeriesFields(params);
    // 生成动态文件名
    const fileName = `自定义指标-${this.isAPM ? this.appName : this.metricName}-${dayjs.tz().format('YYYY-MM-DD_HH-mm-ss')}.json`;

    // 执行下载
    downCsvFile(JSON.stringify(template, null, 2), fileName);
  }

  /**
   * 处理导入指标数据
   * @param jsonData JSON字符串
   */
  async handleUploadMetric(jsonData: string): Promise<void> {
    if (!jsonData) {
      return;
    }
    const params = {
      time_series_group_id: this.timeSeriesGroupId,
      ...JSON.parse(jsonData),
    };
    if (this.isAPM) {
      delete params.time_series_group_id;
      Object.assign(params, {
        app_name: this.appName,
        service_name: this.serviceName,
      });
    }
    await this.requestHandlerMap.importCustomTimeSeriesFields(params);
    this.updateInfoSuccess();
  }

  /**
   * 批量添加至分组
   * @param groupName 分组名称
   * @param manualList 手动添加的指标列表
   */
  async handleBatchAddGroup(groupName: string, ids: number[]): Promise<void> {
    const group = this.groupsMap.get(groupName);
    if (!group) {
      return;
    }

    try {
      await this.submitGroupInfo({
        name: groupName,
        update_ids: ids,
        auto_rules: group.matchRules || [],
        scope_id: group.scopeId,
      });
      this.$bkMessage({ theme: 'success', message: this.$t('变更成功') });
      this.updateInfoSuccess();
      this.metricListRef?.resetAllSelection();
    } catch (error) {
      console.error(`批量添加分组 ${groupName} 更新失败:`, error);
    }
  }

  /**
   * 删除自定义分组
   * @param name 分组名称
   */
  async handleDelGroup(name: string): Promise<void> {
    const params = {
      time_series_group_id: this.timeSeriesGroupId,
      name,
    };
    if (this.isAPM) {
      delete params.time_series_group_id;
      Object.assign(params, {
        app_name: this.appName,
        service_name: this.serviceName,
      });
    }
    await this.requestHandlerMap.deleteGroupingRule(params);
    this.$bkMessage({ theme: 'success', message: this.$t('删除成功') });
    await this.getGroupList();
    // 如果当前选中的是被删除的分组，则重置筛选条件
    if (this.groupFilterList[0] === name) {
      this.changeGroupFilterList({ id: 0, name: ALL_LABEL });
    }
    this.metricListRef?.handleGetCustomTsFields();
  }

  /**
   * 更改分组过滤列表
   * @param groupInfo 分组信息对象，包含 id 和 name
   */
  changeGroupFilterList(groupInfo: { id: number; name: string }): void {
    this.selectedGroupInfo = groupInfo;
    this.customGroupingListRef.changeSelectedLabel(groupInfo);
    // this.handleClearSearch();
    this.groupFilterList = groupInfo.name === ALL_LABEL ? [] : [groupInfo.name];
  }

  /**
   * 提交分组信息
   * @param config 分组配置
   */
  async submitGroupInfo(config: CreateOrUpdateGroupingRuleParams): Promise<void> {
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
    await this.requestHandlerMap.createOrUpdateGroupingRule(params);
  }

  /**
   * 获取分组管理数据
   */
  async getGroupList(): Promise<void> {
    this.groupListloading = true;
    const params = {
      time_series_group_id: this.timeSeriesGroupId,
    };
    if (this.isAPM) {
      delete params.time_series_group_id;
      Object.assign(params, {
        app_name: this.appName,
        service_name: this.serviceName,
      });
    }
    const data = await this.requestHandlerMap
      .customTsGroupingRuleList(params)
      .catch(() => [] as ServiceReturnType<typeof customTsGroupingRuleList>);

    this.groupList = data.map(item => ({
      name: item.name,
      matchRules: item.auto_rules,
      scopeId: item.id,
      createFrom: item.create_from,
      metricCount: item.metric_count,
      dimensionConfig: item.dimension_config,
    }));
    this.groupsDataTidy();
    this.groupListloading = false;
  }

  /**
   * 整理分组数据
   * 构建分组与指标的映射关系，包括：
   * 1. 收集所有匹配规则并建立规则与指标的映射
   * 2. 为每个分组构建包含的指标列表（包括自动匹配和手动添加）
   * 3. 为每个指标建立所属分组的映射关系
   */
  groupsDataTidy(): void {
    const metricNames = this.metricList.map(item => item.name);
    const allMatchRulesSet = new Set();
    const metricGroupsMap = new Map();
    this.groupsMap = new Map();
    // 收集所有匹配规则
    for (const item of this.groupList) {
      for (const rule of item.matchRules) {
        allMatchRulesSet.add(rule);
      }
    }
    const allMatchRules = Array.from(allMatchRulesSet);

    /* 整理每个匹配规则匹配的指标数据 */
    for (const rule of allMatchRules) {
      this.matchRulesMap.set(
        rule as string,
        metricNames.filter(name => matchRuleFn(name, rule as string))
      );
    }

    // 为每个组构建指标映射
    for (const item of this.groupList) {
      const tempSet = new Set<string>();

      // 收集通过匹配规则匹配到的指标
      for (const rule of item.matchRules) {
        const metrics = this.matchRulesMap.get(rule) || [];
        for (const m of metrics) {
          tempSet.add(m);
        }
      }
      const matchRulesOfMetrics = [...tempSet];

      // 更新组映射
      this.groupsMap.set(item.name, {
        ...item,
        matchRulesOfMetrics,
      });

      /**
       * 为每个指标建立包含的组的映射
       * @param metricName 指标名称
       * @param type 匹配类型：'auto' 表示自动匹配，'manual' 表示手动添加
       */
      const setMetricGroup = (metricName: string, type: string): void => {
        const metricItem = metricGroupsMap.get(metricName);
        if (metricItem) {
          const { groups, matchType } = metricItem;
          const targetGroups = [...new Set(groups.concat([item.name]))];
          const targetMatchType = JSON.parse(JSON.stringify(matchType));

          for (const t of targetGroups) {
            if (t === item.name) {
              targetMatchType[t] = [...new Set((matchType[t] || []).concat([type]))];
            }
          }

          metricGroupsMap.set(metricName, {
            groups: targetGroups,
            matchType: targetMatchType,
          });
        } else {
          const matchTypeObj = {
            [item.name]: [type],
          };
          metricGroupsMap.set(metricName, {
            groups: [item.name],
            matchType: matchTypeObj,
          });
        }
      };

      // 应用匹配规则匹配的指标
      matchRulesOfMetrics.forEach(m => {
        setMetricGroup(m, 'auto');
      });

      // 应用手动添加的指标
      // item.metricList.forEach(m => {
      //   setMetricGroup(m.metric_name, 'manual');
      // });
    }

    this.metricGroupsMap = metricGroupsMap;
  }

  /**
   * 更新信息成功后的回调
   * 触发刷新事件并重新获取分组列表
   */
  updateInfoSuccess() {
    this.metricListRef?.handleGetCustomTsFields();
    this.getGroupList();
  }

  /**
   * 显示添加分组对话框
   */
  handleShowAddGroup() {
    this.customGroupingListRef.handleAddGroup();
  }

  /**
   * 编辑分组成功后的回调
   * @param groupInfo 分组信息对象，包含 scope_id 和 name
   * @param isCreate 是否为新建分组，默认为 false
   */
  async handleEditGroupSuccess(groupInfo: { name: string; scope_id: number }, isCreate = false) {
    await this.getGroupList();
    this.changeGroupFilterList({
      id: groupInfo.scope_id || 0,
      name: groupInfo.name,
    });
    if (isCreate) {
      this.customGroupingListRef.scrollToGroup(groupInfo.name);
      this.$emit('groupListChange');
    }
    this.metricListRef?.handleGetCustomTsFields();
  }

  /** 触发别名变更事件，通知父组件别名已修改 */
  handleAliasChange() {
    this.$emit('aliasChange');
  }

  render() {
    return (
      <div class='timeseries-detail-page'>
        <div
          class={{ left: true, active: this.isShowRightWindow }}
          v-bkloading={{ isLoading: this.groupListloading }}
        >
          <div
            class={'right-button'}
            onClick={() => {
              this.isShowRightWindow = !this.isShowRightWindow;
            }}
          >
            {this.isShowRightWindow ? (
              <i class='icon-monitor icon-arrow-left icon' />
            ) : (
              <i class='icon-monitor icon-arrow-right icon' />
            )}
          </div>
          <GroupList
            ref='customGroupingListRef'
            defaultGroupInfo={this.defaultGroupInfo}
            groupList={this.groupList}
            isSearchMode={false}
            onChangeGroup={this.changeGroupFilterList}
            onEditGroupSuccess={this.handleEditGroupSuccess}
            onGroupDelByName={this.handleDelGroup}
          />
        </div>
        <div
          style={{ height: this.isAPM ? 'calc(100vh - 52px)' : 'calc(100vh - 430px)' }}
          class='timeseries-detail-page-content'
        >
          <div class='list-header'>
            <div class='head'>
              <div class='tabs'>
                {this.tabs.map(({ title, id }) => (
                  <span
                    key={id}
                    class={['tab', id === this.activeTab ? 'active' : '']}
                    onClick={() => {
                      this.activeTab = id;
                    }}
                  >
                    {title}
                  </span>
                ))}
              </div>
              <div class='tools'>
                <MonitorImport
                  class='tool'
                  base64={false}
                  return-text={true}
                  onChange={this.handleUploadMetric}
                >
                  <i class='icon-monitor icon-xiazai2' /> {this.$t('导入')}
                </MonitorImport>
                <span
                  class='tool'
                  onClick={this.handleExportMetric}
                >
                  <i class='icon-monitor icon-shangchuan' />
                  {this.$t('导出')}
                </span>
              </div>
            </div>
          </div>
          {this.activeTab === 'metric' ? (
            <MetricList
              ref='metricListRef'
              defaultGroupInfo={this.defaultGroupInfo}
              dimensionTable={this.dimensionTable}
              groupSelectList={this.groupSelectList}
              groupsMap={this.groupsMap}
              metricGroupsMap={this.metricGroupsMap}
              timeSeriesGroupId={this.timeSeriesGroupId}
              selectedGroupInfo={this.selectedGroupInfo}
              unitList={this.unitList}
              onAliasChange={this.handleAliasChange}
              onHandleBatchAddGroup={this.handleBatchAddGroup}
              onRefresh={this.updateInfoSuccess}
              onShowAddGroup={this.handleShowAddGroup}
            />
          ) : (
            <DimensionList
              dimensionTable={this.dimensionTable}
              selectedGroupInfo={this.selectedGroupInfo}
              onAliasChange={this.handleAliasChange}
              onRefresh={this.updateInfoSuccess}
            />
          )}
        </div>
      </div>
    );
  }
}
