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
import { Component, InjectReactive, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import type { RequestHandlerMap } from '../../../../../../type';

import _ from 'lodash';
import { random } from 'monitor-common/utils/utils';

import AutoGroup from './components/auto-group';
import ManualGroup, { type ITableRowData } from './components/manual-group';
import ResultPreview, { type IListItem } from './components/result-preview';

import type { IGroupingRule } from '../../../../../../../service';

import './index.scss';

/**
 * 指标选择器组件
 * 支持手动分组和自动分组两种方式选择指标
 */
@Component({
  name: 'IndicatorSelector',
})
export default class IndicatorSelector extends tsc<any> {
  /** 是否为编辑模式 */
  @Prop({ default: false, type: Boolean }) isEdit: boolean;
  /** 分组规则信息 */
  @Prop() groupInfo: IGroupingRule;
  /** 默认分组信息 */
  @Prop({ default: () => {} }) defaultGroupInfo: { id: number; name: string };

  @InjectReactive('timeSeriesGroupId') readonly timeSeriesGroupId: number;
  @InjectReactive('isAPM') readonly isAPM: boolean;
  @InjectReactive('requestHandlerMap') readonly requestHandlerMap: RequestHandlerMap;
  @InjectReactive('appName') readonly appName: string;
  @InjectReactive('serviceName') readonly serviceName: string;

  /** 手动分组组件的引用 */
  @Ref() manualGroupMainRef: InstanceType<typeof ManualGroup>;
  /** 自动分组组件的引用 */
  @Ref() autoGroupMainRef: InstanceType<typeof AutoGroup>;

  /** 当前激活的标签页，'manual' 表示手动分组，'auto' 表示自动分组 */
  activeTab = 'manual';
  /** 标签页列表配置 */
  tabList = [
    {
      name: this.$t('手动选择'),
      id: 'manual',
    },
    {
      name: this.$t('自动发现'),
      id: 'auto',
    },
  ];

  /** 手动分组选中的指标列表 */
  manualList: IListItem[] = [];
  /** 本地维护的手动分组列表 */
  localManualList: IListItem[] = [];
  /** 自动分组规则列表 */
  autoList: IListItem[] = [];
  /** 本地维护的自动分组列表 */
  localAutoList: IListItem[] = [];
  /** 所有可用的指标数据列表 */
  totalMetrics: ITableRowData[] = [];
  /** 原始手动分组列表 */
  originalManualList: ITableRowData[] = [];

  /**
   * 监听分组信息变化，同步更新手动分组和自动分组列表
   */
  @Watch('groupInfo', { immediate: true, deep: true })
  async handleGroupInfoChange() {
    if (!this.groupInfo.id) return;
    const currentSelectedMetrics = await this.fetchCurrentSelectedMetrics();
    this.originalManualList = currentSelectedMetrics;
    this.manualList = currentSelectedMetrics.map(item => ({
      id: item.id,
      name: item.name,
      isAdded: false,
      isDeleted: false,
    }));
    this.localManualList = _.cloneDeep(this.manualList);
    this.autoList =
      this.groupInfo.auto_rules?.map(item => ({
        id: random(8),
        name: item,
        isAdded: false,
        isDeleted: false,
        isChanged: false,
      })) || [];
    this.localAutoList = _.cloneDeep(this.autoList);
  }

  /** 拉取当前分组已选中的指标列表 */
  async fetchCurrentSelectedMetrics() {
    const params = {
      time_series_group_id: this.timeSeriesGroupId,
      page: 1,
      page_size: -1,
      conditions: [
        {
          key: 'scope_id',
          values: [this.groupInfo.id],
          search_type: 'exact' as const,
        },
      ],
    };
    if (this.isAPM) {
      delete params.time_series_group_id;
      Object.assign(params, {
        app_name: this.appName,
        service_name: this.serviceName,
      });
    }
    const data = await this.requestHandlerMap.getCustomTsFields(params);
    return data.list;
  }

  /**
   * 切换标签页
   * @param id 标签页ID，'manual' 或 'auto'
   */
  handleTabChange(id: string) {
    this.activeTab = id;
  }

  /** 更新全量指标列表缓存，用于手动分组行选择的状态同步 */
  handleMetricListChange(metricList: ITableRowData[]) {
    this.totalMetrics = metricList;
  }

  /**
   * 处理手动分组选择变化
   * @param selectList 选中的指标列表
   */
  handleSelectManualChange(selectList: ITableRowData[]) {
    this.manualList = selectList.map(item => ({
      id: item.id,
      name: item.name,
    }));
  }

  /**
   * 处理自动分组正则表达式输入
   * 如果规则已存在则更新，否则添加新规则
   * @param data 正则规则数据
   */
  handleRegexInput(data: IListItem) {
    const currentItem = this.autoList.find(item => item.id === data.id);
    if (currentItem) {
      currentItem.name = data.name;
      return;
    }

    this.autoList.push(data);
  }

  /**
   * 删除自动分组规则项
   * @param id 要删除的规则ID
   */
  handleDeleteAutoItem(id: string) {
    this.autoList = this.autoList.filter(item => item.id !== id);
  }

  /**
   * 清空所有选择
   * 清空手动分组和自动分组的选中项
   */
  handleClearAll() {
    this.manualGroupMainRef?.clearSelect();
    this.autoGroupMainRef?.clearSelect();
    this.$nextTick(() => {
      this.autoList = [];
      this.manualList = [];
    })
  }

  /**
   * 移除手动分组中的指定项
   * @param item 要移除的指标项
   */
  handleRemoveManual(item: IListItem) {
    const deleteRow = this.totalMetrics.find(row => row.id === item.id);
    if (deleteRow) {
      this.manualGroupMainRef?.toggleRowSelection(deleteRow, false);
    }
    this.manualList = this.manualList.filter(row => row.id !== item.id);
  }

  /**
   * 处理恢复手动分组项
   * @param item 要恢复的列表项
   */
  handleRecoverManualItem(item: IListItem) {
    this.manualList.push({
      id: item.id,
      name: item.name,
    });
    const recoverRow = this.totalMetrics.find(row => row.id === item.id);
    if (recoverRow) {
      this.manualGroupMainRef?.toggleRowSelection(recoverRow, true);
    }
  }

  /**
   * 处理恢复自动分组项
   * @param item 要恢复的列表项
   */
  handleRecoverAutoItem(item: IListItem) {
    const recoverRawItem = this.localAutoList.find(row => row.id === item.id);
    const recoverItem = _.cloneDeep(recoverRawItem);
    recoverItem.isDeleted = false;
    const lastDeleteIndex = this.localAutoList.findIndex(row => row.isDeleted);
    if (lastDeleteIndex !== -1) {
      this.autoList.splice(lastDeleteIndex, 0, recoverItem);
    } else {
      this.autoList.push(recoverItem);
    }
  }

  /**
   * 移除自动分组中的指定项
   * @param item 要移除的规则项
   */
  handleRemoveAuto(item: IListItem) {
    this.autoGroupMainRef?.handleDeleteItem(item.id as string);
  }

  render() {
    return (
      <div class='indicator-selector-main'>
        <div class='content-main'>
          <div class='tab-main'>
            {this.tabList.map(item => (
              <div
                key={item.id}
                class={['tab-item', { 'is-active': this.activeTab === item.id }]}
                onClick={() => this.handleTabChange(item.id)}
              >
                <div class='top-bar' />
                <div class='tab-name'>{item.name}</div>
              </div>
            ))}
            <div class='remain-block' />
          </div>
          <div class='group-main'>
            <ManualGroup
              ref='manualGroupMainRef'
              v-show={this.activeTab === 'manual'}
              groupInfo={this.groupInfo}
              defaultGroupInfo={this.defaultGroupInfo}
              isEdit={this.isEdit}
              manualList={this.manualList}
              onMetricListChange={this.handleMetricListChange}
              onSelectChange={this.handleSelectManualChange}
            />
            <AutoGroup
              ref='autoGroupMainRef'
              v-show={this.activeTab === 'auto'}
              autoList={this.autoList}
              onDeleteItem={this.handleDeleteAutoItem}
              onRegexInput={this.handleRegexInput}
            />
          </div>
        </div>
        <div class='preview-main'>
          <ResultPreview
            autoList={this.autoList}
            isEdit={this.isEdit}
            localRawAutoList={this.localAutoList}
            localRawManualList={this.localManualList}
            manualList={this.manualList}
            onClearSelect={this.handleClearAll}
            onRecoverAutoItem={this.handleRecoverAutoItem}
            onRecoverManualItem={this.handleRecoverManualItem}
            onRemoveAuto={this.handleRemoveAuto}
            onRemoveManual={this.handleRemoveManual}
          />
        </div>
      </div>
    );
  }
}
