import { Component, Ref, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import _ from 'lodash';
import AutoGroup from './components/auto-group';
import ManualGroup, { type ITableRowData } from './components/manual-group';
import ResultPreview, { type IListItem } from './components/result-preview';
import type { IGroupingRule } from '../../../../../../../service';
import { random } from 'monitor-common/utils/utils';

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

  /**
   * 监听分组信息变化，同步更新手动分组和自动分组列表
   */
  @Watch('groupInfo', { immediate: true, deep: true })
  handleGroupInfoChange() {
    this.manualList =
      this.groupInfo.metric_list?.map(item => ({
        id: item.field_id,
        name: item.metric_name,
        isAdded: false,
        isDeleted: false,
      })) || [];
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

  /**
   * 切换标签页
   * @param id 标签页ID，'manual' 或 'auto'
   */
  handleTabChange(id: string) {
    this.activeTab = id;
  }

  /**
   * 处理总指标列表变化
   * @param totalMetrics 更新后的总指标列表
   */
  handleTotalMetricsChange(totalMetrics: ITableRowData[]) {
    this.totalMetrics = totalMetrics;
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
    this.manualList = [];
    this.manualGroupMainRef?.clearSelect();
    this.autoList = [];
    this.autoGroupMainRef?.clearSelect();
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
  }

  /**
   * 处理恢复手动分组项
   * @param item 要恢复的列表项
   */
  handleRecoverManualItem(item: IListItem) {
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
                class={['tab-item', { 'is-active': this.activeTab === item.id }]}
                key={item.id}
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
              isEdit={this.isEdit}
              v-show={this.activeTab === 'manual'}
              groupInfo={this.groupInfo}
              manualList={this.manualList}
              ref='manualGroupMainRef'
              onSelectChange={this.handleSelectManualChange}
              onTotalMetricsChange={this.handleTotalMetricsChange}
            />
            <AutoGroup
              autoList={this.autoList}
              ref='autoGroupMainRef'
              v-show={this.activeTab === 'auto'}
              onRegexInput={this.handleRegexInput}
              onDeleteItem={this.handleDeleteAutoItem}
            />
          </div>
        </div>
        <div class='preview-main'>
          <ResultPreview
            manualList={this.manualList}
            autoList={this.autoList}
            localRawAutoList={this.localAutoList}
            localRawManualList={this.localManualList}
            isEdit={this.isEdit}
            onClearSelect={this.handleClearAll}
            onRemoveManual={this.handleRemoveManual}
            onRemoveAuto={this.handleRemoveAuto}
            onRecoverManualItem={this.handleRecoverManualItem}
            onRecoverAutoItem={this.handleRecoverAutoItem}
          />
        </div>
      </div>
    );
  }
}
