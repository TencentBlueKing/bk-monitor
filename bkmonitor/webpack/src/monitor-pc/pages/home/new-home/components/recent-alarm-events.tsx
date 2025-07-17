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
import { Component, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { deleteAlarmGraphConfig, getAlarmGraphConfig, saveAlarmGraphConfig } from 'monitor-api/modules/overview';
import draggable from 'vuedraggable';

import { shortcuts } from '../../../../components/time-range/utils';
import emptyImageSrc from '../../../../static/images/png/empty.png';
import { DEFAULT_SEVERITY_LIST, RECENT_ALARM_SEVERITY_KEY } from '../utils';
import AddAlarmChartDialog from './add-alarm-chart-dialog';
import HomeAlarmChart from './home-alarm-chart';
import RecentAlarmTab from './recent-alarm-tab';

import type { TimeRangeType } from '../../../../components/time-range/time-range';
import type { IAlarmGraphConfig } from '../type';
import type { IRecentAlarmTab } from '../type';

import './recent-alarm-events.scss';

@Component({
  name: 'RecentAlarmEvents',
  components: {
    draggable,
  },
})
export default class RecentAlarmEvents extends tsc<object> {
  /** Tab 相关 */
  businessTab: IRecentAlarmTab[] = []; // 业务选项卡
  showTabLoading = false; // 展示tab的加载loading、
  activeTabId = null; // 默认选中第一个标签

  /** 图表 相关 */
  alarmGraphContent: IAlarmGraphConfig[] = []; // 图表配置
  alarmGraphBizId = null; // 告警图表业务id

  loadingAlarmList = true; // 加载图表列表

  isAppendMode = false; // 是否为新增图表
  showAddTaskDialog = false; // 展示添加图表/业务弹窗

  editChartIndex = null; // 编辑的图表下标
  showDelDialog = false; // 展示删除图表/业务弹窗
  currentDelId = null; // 当前删除的图表id

  bizLimit = 5; // 默认添加5个业务
  graphLimit = 10; // 默认添加十个图表

  /** 策略配置 相关 */
  strategyConfig = {
    strategy_ids: [],
    name: '',
    status: [],
  };
  delStrategyIdSet: Set<number> = new Set(); // 已删除的策略id列表

  handleMenuMode: '' | 'delete' | 'detail' | 'edit' = ''; // MenuList 操作模式
  childRefs = []; // 存储每个子组件的 ref
  timeRange = shortcuts[5].value as TimeRangeType; // 时间选择器

  @Watch('activeTabId')
  handleSwitchTab(val) {
    if (!val) return;
    this.getTabAndAlarmConfig(false);
  }

  // 可以添加图表flag
  get canAddGraph() {
    // 仅支持添加 n 个图表
    return this.alarmGraphContent.length < this.graphLimit;
  }

  get computedWidth() {
    return window.innerWidth < 2560 ? 392 : 452;
  }

  async created() {
    await this.getTabAndAlarmConfig(true, false);
    this.activeTabId = this.businessTab[0]?.bk_biz_id; // 默认选中第一个标签
  }

  async getTabAndAlarmConfig(updateTab = true, updateAlarmConfig = true) {
    try {
      this.loadingAlarmList = !this.editChartIndex;
      this.showTabLoading = updateTab;
      const data = await getAlarmGraphConfig({
        bk_biz_id: this.activeTabId || this.$store.getters.bizId,
      });
      const currentBizLength = data.tags.length;
      this.bizLimit = currentBizLength > data.biz_limit ? currentBizLength : data.biz_limit || this.bizLimit;
      this.graphLimit = data.graph_limit || this.graphLimit;
      if (updateTab) {
        if (this.businessTab.length === 0) {
          this.activeTabId = data.tags?.[0]?.bk_biz_id;
        } else if (this.businessTab.length < data.tags.length) {
          // 当新增业务时,切换至当前的新增业务
          this.activeTabId = data.tags?.at(-1)?.bk_biz_id;
        }
        this.businessTab = data.tags || [];
      }
      if (updateAlarmConfig) {
        this.alarmGraphContent = data.config || [];
      }
    } catch (error) {
      console.log('get Date error', error);
    } finally {
      this.showTabLoading = false;
      this.loadingAlarmList = false;
    }
  }

  // 图表 start
  // 图表列表
  getAlarmGraphList(list) {
    // 列表最后一个为新增图表
    const add = () => (
      <div
        style={{ 'min-width': `${this.computedWidth}px` }}
        class={{ 'add-content list-item': true, 'unable-add-graph': !this.canAddGraph }}
        v-bk-tooltips={{
          content: this.$t('仅支持添加 {0} 个图表', {
            0: this.graphLimit,
          }),
          trigger: 'mouseenter',
          zIndex: 9999,
          boundary: document.body,
          allowHTML: false,
          disabled: this.canAddGraph,
        }}
        onClick={() => this.handleAddChart()}
      >
        <i class='icon-mc-add icon-monitor' />
        <span>{this.$t('添加图表')}</span>
      </div>
    );
    return (
      <div class='list-content'>
        {list.map((item, index) => (
          <div
            key={item.name + index}
            style={{ 'min-width': `${this.computedWidth}px` }}
            class='list-item'
          >
            <HomeAlarmChart
              ref={el => (this.childRefs[index] = el)} // 存储子组件的 ref
              config={item}
              currentActiveId={this.activeTabId}
              severityProp={this.severityList[index]}
              timeRange={this.timeRange}
              onMenuClick={data => this.handleMenuClick(data, item, index)}
              onSeverityChange={severity => this.saveSeverityList(index, severity)}
            />
          </div>
        ))}
        {add()}
      </div>
    );
  }

  get severityList() {
    return JSON.parse(
      localStorage.getItem(`${RECENT_ALARM_SEVERITY_KEY}_${this.activeTabId}`) ||
        JSON.stringify(Array(this.alarmGraphContent.length).fill(DEFAULT_SEVERITY_LIST))
    );
  }

  /** 保存图表严重程度数组 */
  saveSeverityList(index, severity = []) {
    const severityList = this.severityList;
    severity.length ? severityList.splice(index, 1, severity) : severityList.splice(index, 1);
    localStorage.setItem(`${RECENT_ALARM_SEVERITY_KEY}_${this.activeTabId}`, JSON.stringify(severityList));
  }

  /** MenuList操作 */
  handleMenuClick(data, item, index) {
    const { id: mode } = data;
    this.handleMenuMode = mode;
    switch (mode) {
      case 'edit':
        this.strategyConfig.name = item.name;
        this.strategyConfig.strategy_ids = item.strategy_ids;
        this.strategyConfig.status = item.status;
        this.editChartIndex = index;
        this.handleAddChart();
        break;
      case 'delete':
        this.editChartIndex = index;
        this.showDelDialog = true;
        break;
      case 'detail': {
        // 跳转至事件中心
        const baseUrl = window.location.href.split('#')[0];
        let queryString = '';
        for (const id of item.strategy_ids) {
          queryString += `策略ID : ${id} OR `;
        }
        queryString = queryString.slice(0, queryString.length - 3);
        const [from, to] = this.timeRange;
        const xAxis = data.xAxis;
        const url = `${baseUrl}#/event-center/?queryString=${encodeURIComponent(queryString)}&from=${xAxis ? xAxis : from}&to=${xAxis ? xAxis : to}&bizIds=${this.activeTabId}`;
        window.open(url, '_blank');
        break;
      }
    }
  }

  // 新增业务
  handleAddSpace() {
    this.$refs.recentAlarmTab?.$refs?.homeBizSelect?.$refs?.homePopoverRef?.showHandler?.();
  }
  // 新增图表
  handleAddChart() {
    if (!this.canAddGraph) return;
    this.alarmGraphBizId = this.activeTabId;
    this.isAppendMode = true;
    this.showAddTaskDialog = true;
  }

  // 取消新增图表
  handleCancel() {
    this.alarmGraphBizId = null;
    this.showAddTaskDialog = false;
  }

  // 生成配置
  generateConfig() {
    // 如果是追加模式，遍历内容生成配置
    if (this.isAppendMode) {
      return this.alarmGraphContent.map(({ name, strategy_ids }) => ({
        name,
        strategy_ids,
      }));
    }
    // 否则，返回空数组
    return [];
  }

  /**
   * 更新配置的主函数，根据编辑模式和操作类型执行相应操作。
   * @param config - 当前配置数组。
   * @param editChartIndex - 当前编辑的索引，null 表示新增模式。
   * @param handleMenuMode - 当前操作模式，'delete' 表示删除。
   * @param strategyConfig - 当前策略配置对象。
   * @param delStrategyIdSet - 需要删除的策略 ID 集合。
   */
  updateConfig(
    config: Array<any>,
    editChartIndex: null | number,
    handleMenuMode: string,
    strategyConfig: { status: Array<any>; strategy_ids: Array<any> },
    delStrategyIdSet: Set<number>
  ): void {
    const isEditMode = editChartIndex !== null; // 判断是否处于编辑模式
    const isDeleteMode = handleMenuMode === 'delete'; // 判断是否为删除操作

    if (isEditMode) {
      this.handleEditMode(config, editChartIndex, isDeleteMode, strategyConfig, delStrategyIdSet);
      isDeleteMode && this.saveSeverityList(editChartIndex);
    } else {
      // 如果不是编辑模式，添加新的配置
      this.saveSeverityList(this.alarmGraphContent.length, DEFAULT_SEVERITY_LIST);
      config.push(strategyConfig);
    }
  }

  /**
   * 处理编辑模式下的配置更新。
   * @param config - 当前配置数组。
   * @param editChartIndex - 当前编辑的索引。
   * @param isDeleteMode - 是否为删除操作。
   * @param strategyConfig - 当前策略配置对象。
   * @param delStrategyIdSet - 需要删除的策略 ID 集合。
   */
  handleEditMode(
    config: Array<any>,
    editChartIndex: number,
    isDeleteMode: boolean,
    strategyConfig: { status: Array<any>; strategy_ids: Array<any> },
    delStrategyIdSet: Set<number>
  ): void {
    if (isDeleteMode) {
      this.deleteConfig(config, editChartIndex);
    } else {
      this.modifyConfig(config, editChartIndex, strategyConfig, delStrategyIdSet);
    }
  }

  /**
   * 删除指定索引的配置。
   * @param config - 当前配置数组。
   * @param editChartIndex - 要删除的索引。
   */
  deleteConfig(config: Array<any>, editChartIndex: number): void {
    config.splice(editChartIndex, 1);
  }

  /**
   * 修改指定索引的配置。
   * @param config - 当前配置数组。
   * @param editChartIndex - 要修改的索引。
   * @param strategyConfig - 当前策略配置对象。
   * @param delStrategyIdSet - 需要删除的策略 ID 集合。
   */
  modifyConfig(
    config: Array<any>,
    editChartIndex: number,
    strategyConfig: { status: Array<any>; strategy_ids: Array<any> },
    delStrategyIdSet: Set<number>
  ): void {
    if (delStrategyIdSet.size > 0) {
      this.filterStrategyConfig(strategyConfig, delStrategyIdSet);
    }
    config.splice(editChartIndex, 1, strategyConfig);
  }

  /**
   * 过滤策略配置中的状态和策略 ID。
   * @param strategyConfig - 当前策略配置对象。
   * @param delStrategyIdSet - 需要删除的策略 ID 集合。
   */
  filterStrategyConfig(
    strategyConfig: { status: Array<any>; strategy_ids: Array<any> },
    delStrategyIdSet: Set<number>
  ): void {
    strategyConfig.status = strategyConfig.status.filter(item => !delStrategyIdSet.has(item.strategy_id));
    strategyConfig.strategy_ids = strategyConfig.strategy_ids.filter(id => !delStrategyIdSet.has(id));
  }

  async handleSaveAlarmGraphConfig() {
    // 生成初始配置
    this.showAddTaskDialog = false;
    const config = this.generateConfig();
    this.updateConfig(config, this.editChartIndex, this.handleMenuMode, this.strategyConfig, this.delStrategyIdSet);
    try {
      // 保存告警图表配置
      await saveAlarmGraphConfig({
        bk_biz_id: this.getBusinessConfigId(),
        config,
      });
      // 如果是新增业务，需要刷新 tabs
      await this.getTabAndAlarmConfig(!this.isAppendMode);
      // 调用子组件的方法
      if (this.childRefs[this.editChartIndex]) {
        this.childRefs[this.editChartIndex].getPanelData(); // 调用子组件的方法
      }
    } catch (error) {
      // 捕获并处理错误
      console.error('Error saving alarm graph config:', error);
      this.$bkMessage({
        theme: 'error',
        message: this.$t('保存告警图表配置时出错，请稍后重试'),
      });
    } finally {
      this.showDelDialog = false;
    }
  }
  // 图表 end

  // 业务 start
  // 添加业务
  async handleSelectBiz(id) {
    this.alarmGraphBizId = id;
    this.showAddTaskDialog = true;
    this.isAppendMode = false;
  }

  // 获取业务配置 ID
  getBusinessConfigId() {
    // 返回业务配置 ID，如果没有则返回当前活动的 Tab ID
    return this.alarmGraphBizId || this.activeTabId;
  }

  // 删除图表/业务 Dialog
  getDelChartDialog() {
    let detail = this.$t('业务：{0}', {
      0: this.businessTab.filter(item => item.bk_biz_id === this.currentDelId)[0]?.bk_biz_name,
    });
    let width = 680;
    let tips = this.$t('删除后，该tab下的视图也会一起删除');
    let info = this.$t('确定删除该业务视图？');
    let handleDelFunction = this.delTaskByIndex;
    if (this.handleMenuMode === 'delete') {
      detail = '';
      tips = '';
      info = this.$t('确定删除该视图？');
      this.alarmGraphBizId = this.activeTabId;
      this.isAppendMode = true;
      width = 580;
      handleDelFunction = this.handleSaveAlarmGraphConfig;
    }
    return (
      <bk-dialog
        width={width}
        ext-cls='task-del-dialog'
        v-model={this.showDelDialog}
        header-position='left'
        show-footer={false}
        on-after-leave={() => {
          this.currentDelId = null;
          this.handleMenuMode = '';
          // 重置编辑索引，关闭对话框，清除策略配置
          this.clearStrategyConfig();
        }}
        onCancel={this.handleCancelDel}
      >
        <div class='icon icon-exclamation bk-icon' />
        <div class='info'>{info}</div>
        {detail && <div class='detail'>{detail}</div>}
        {tips && <div class='tips'>{tips}</div>}
        <div class='foot'>
          <bk-button
            theme='danger'
            onClick={handleDelFunction}
          >
            {this.$t('删除')}
          </bk-button>
          <bk-button
            theme='default'
            onClick={this.handleCancelDel}
          >
            {this.$t('取消')}
          </bk-button>
        </div>
      </bk-dialog>
    );
  }

  // 处理删除业务逻辑
  handleDelTask(id) {
    this.currentDelId = id;
    this.showDelDialog = true;
  }

  // 取消删除
  handleCancelDel() {
    this.showDelDialog = false;
  }

  // 删除业务
  delTaskByIndex() {
    this.businessTab = this.businessTab.filter(item => item.bk_biz_id !== this.currentDelId);
    deleteAlarmGraphConfig({
      bk_biz_id: this.currentDelId,
    });
    localStorage.removeItem(`${RECENT_ALARM_SEVERITY_KEY}_${this.activeTabId}`);
    // 当删除的是当前的业务，切换activeTab状态
    if (this.currentDelId === this.activeTabId && this.businessTab.length) {
      this.activeTabId = this.businessTab[0].bk_biz_id;
    }
    // 业务全部删除
    if (this.businessTab.length === 0) {
      this.alarmGraphContent = [];
    }
    this.showDelDialog = false;
    this.clearStrategyConfig();
  }
  // 业务 end

  // 空数组展示
  getEmptyContent() {
    return (
      <div class='empty-content'>
        <div class='empty-img'>
          <img
            alt=''
            src={emptyImageSrc}
          />
        </div>
        <div class='empty-info'>
          {this.businessTab.length === 0 ? this.$t('尚未添加业务') : this.$t('尚未添加图表')},&nbsp;
          <span
            class='empty-btn'
            onClick={this.businessTab.length ? this.handleAddChart : this.handleAddSpace}
          >
            {this.$t('立刻添加')}
          </span>
        </div>
      </div>
    );
  }

  // 拖拽完成
  handleDropEnd(tabs) {
    this.businessTab = tabs;
  }

  // 计算Loading高度
  getLoadingHeight() {
    if (!this.alarmGraphContent.length) return '398px';
    return `${Math.ceil((this.alarmGraphContent.length + 2) / 3) * 210}px`;
  }

  // 清除相关数据
  clearStrategyConfig() {
    this.strategyConfig.strategy_ids = [];
    this.strategyConfig.name = '';
    this.editChartIndex = null;
    this.handleMenuMode = '';
    this.delStrategyIdSet = new Set();
  }

  render() {
    return (
      <div class='recent-alarm-events'>
        <div class='title'>
          <span>{this.$t('最近告警事件')}</span>
        </div>
        {/* 头部功能区 */}
        <RecentAlarmTab
          ref='recentAlarmTab'
          // @ts-ignore
          activeTabId={this.activeTabId}
          bizLimit={this.bizLimit}
          showTabLoading={this.showTabLoading}
          tabs={this.businessTab}
          onChangeTab={id => {
            this.activeTabId = id;
          }}
          onChangeTime={timeRange => {
            this.timeRange = timeRange;
          }}
          onHandleDelTask={this.handleDelTask}
          onHandleDropTab={this.handleDropEnd}
          onHandleSelectBiz={this.handleSelectBiz}
        />
        {/* 主体内容 */}
        <div class='content'>
          {this.loadingAlarmList ? (
            <div
              style={{ height: this.getLoadingHeight() }}
              class='loading-element'
            />
          ) : !this.alarmGraphContent.length ? (
            this.getEmptyContent()
          ) : (
            this.getAlarmGraphList(this.alarmGraphContent)
          )}
        </div>
        {/* 删除业务/图表-模态框 */}
        {this.getDelChartDialog()}
        {/* 新增业务/图表-模态框 */}
        {
          <AddAlarmChartDialog
            currentBizId={this.alarmGraphBizId}
            editStrategyConfig={this.strategyConfig}
            handleMenuMode={this.handleMenuMode}
            showAddTaskDialog={this.showAddTaskDialog}
            spaceName={this.businessTab.filter(item => item.bk_biz_id === this.alarmGraphBizId)[0]?.bk_biz_name}
            onAfterDialogLeave={() => {
              this.handleMenuMode = '';
              this.editChartIndex = null;
            }}
            onCancel={this.handleCancel}
            onConfirm={(strategyIds, name, delStrategyIds) => {
              this.strategyConfig.name = name;
              this.strategyConfig.strategy_ids = strategyIds;
              this.delStrategyIdSet = delStrategyIds;
              this.handleSaveAlarmGraphConfig();
            }}
          />
        }
      </div>
    );
  }
}
