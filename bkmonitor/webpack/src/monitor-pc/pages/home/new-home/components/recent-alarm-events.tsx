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

import {
  deleteAlarmGraphConfig,
  getAlarmGraphConfig,
  saveAlarmGraphBizIndex,
  saveAlarmGraphConfig,
} from 'monitor-api/modules/overview';
import { getStrategyListV2 } from 'monitor-api/modules/strategies';
import draggable from 'vuedraggable';

import { shortcuts } from '../../../../components/time-range/utils';
import emptyImageSrc from '../../../../static/images/png/empty.png';
import { EStatusType } from '../utils';
import HomeAlarmChart from './home-alarm-chart';
import HomeBizSelect from './home-biz-list';

import type { TimeRangeType } from '../../../../components/time-range/time-range';
import type { IAlarmGraphConfig } from '../type';

import './recent-alarm-events.scss';

// type IProps = {};
@Component({
  name: 'RecentAlarmEvents',
  components: {
    draggable,
  },
})
export default class RecentAlarmEvents extends tsc<object> {
  tabs = [];

  handleMuenMode: '' | 'delete' | 'detail' | 'edit' = '';

  bottomLoadingOptions = {
    isLoading: false,
    size: 'mini',
  };

  // 数据分页
  pagination = {
    currentPage: 1,
    limit: 10,
    isLastPage: false,
  };

  activeTabId = null; // 默认选中第一个标签

  alarmGraphConfig = {
    bizId: '',
    config: [],
  };

  isAppendMode = false;
  editChartIndex = null; // 编辑的图表下标

  showDelDialog = false;
  showAddTaskDialog = false; // 展示添加业务弹窗
  dragoverId = '';
  dragId = '';

  loading = false;

  currentDelId = null;
  strategyConfig = {
    strategy_ids: [],
    name: '',
    status: [],
  };

  timeRange = JSON.stringify(shortcuts[5].value as TimeRangeType);

  strategyList = [];

  filterStrategyIdSet = new Set();

  content: IAlarmGraphConfig[] = [];

  isSelected(id) {
    return this.strategyConfig.strategy_ids.includes(id);
  }

  @Watch('activeTabId')
  handleSwitchTab() {
    this.getData(false);
  }

  async getData(updateTab = true) {
    try {
      updateTab && (this.loading = true);
      const data = await getAlarmGraphConfig({
        bk_biz_id: this.activeTabId,
      });
      this.loading = false;
      if (updateTab) {
        if (this.tabs.length === 0) {
          this.activeTabId = data.tags?.[0].bk_biz_id;
        }
        this.tabs = data.tags || [];
      }
      this.content = data.config || [];
    } catch (error) {
      console.log('get Date error', error);
    }
  }

  async created() {
    await this.getData();
    this.activeTabId = this.tabs[0]?.bk_biz_id; // 默认选中第一个标签
  }

  // 可以添加业务flag
  get canAddBusiness() {
    // 仅支持添加 10 个业务
    return this.tabs.length <= 10;
  }

  get noBusiness() {
    return this.tabs.length === 0;
  }

  // 选择标签
  selectTab(tabId: number) {
    this.activeTabId = tabId;
  }

  // 拖拽 start
  // 拖拽开始，记录当前拖拽的ID
  handleDragstart(index: number) {
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
      const dragIndex = Number.parseInt(this.dragId, 10);
      const dragoverIndex = Number.parseInt(this.dragoverId, 10);

      const draggedTab = this.tabs[dragIndex];
      this.tabs.splice(dragIndex, 1);
      this.tabs.splice(dragoverIndex, 0, draggedTab);
    }

    this.dragId = '';
    this.dragoverId = '';
    // 保存排序
    saveAlarmGraphBizIndex({
      bk_biz_ids: this.tabs.map(tab => tab.bk_biz_id),
    });
  }
  // 拖拽 end

  // 新增图表
  handleAddChart(isEdit = false) {
    this.alarmGraphConfig.bizId = this.activeTabId;
    this.isAppendMode = true;
    isEdit ? this.getStrategyListById() : this.getStrategyListByPage();
    this.showAddTaskDialog = true;
  }

  // 取消新增图表
  handleCancel() {
    this.alarmGraphConfig.bizId = '';
    this.clearStrategyConfig();
    this.showAddTaskDialog = false;
  }
  // 确定新增图表
  async handleConfirm() {
    let config = [];
    // 区分新增业务/新增图表
    if (this.isAppendMode) {
      config = this.content.map(({ name, strategy_ids }) => ({
        name,
        strategy_ids,
      }));
    }
    // 区分修改/新增
    if (this.editChartIndex !== null) {
      // 区分删除/修改
      if (this.handleMuenMode === 'delete') {
        config.splice(this.editChartIndex, 1);
      } else {
        config.splice(this.editChartIndex, 1, this.strategyConfig);
      }
    } else {
      config.push(this.strategyConfig);
    }
    try {
      await saveAlarmGraphConfig({
        bk_biz_id: this.alarmGraphConfig.bizId || this.activeTabId,
        config,
      });
      // 新增业务，需刷新tabs
      await this.getData(!this.isAppendMode);
    } catch (error) {
      console.log('error', error);
    }
    this.editChartIndex = null;
    this.showAddTaskDialog = false;
    this.clearStrategyConfig();
  }

  // 清除相关数据
  clearStrategyConfig() {
    this.strategyConfig.strategy_ids = [];
    this.strategyConfig.name = '';
    this.editChartIndex = null;
    this.handleMuenMode = '';
    this.showDelDialog = false;
    this.pagination = {
      currentPage: 1,
      limit: 10,
      isLastPage: false,
    };
    this.filterStrategyIdSet = new Set();
  }

  async getStrategyListByPage() {
    try {
      const { currentPage: page, limit } = this.pagination;
      const data = await getStrategyListV2({
        page,
        limit,
        bk_biz_id: this.alarmGraphConfig.bizId,
      });
      this.pagination.isLastPage = data.total <= page * limit;
      if (this.handleMuenMode === 'edit') {
        this.strategyList.push(
          ...(data.strategy_config_list.filter(item => {
            if (!this.filterStrategyIdSet.has(item.id)) {
              return true; // 保留在 filter 结果中
            }
            this.filterStrategyIdSet.delete(item.id); // 从集合中移除已处理的 ID
          }) || [])
        );
        return;
      }
      this.strategyList.push(...(data.strategy_config_list || []));
    } catch (error) {
      console.log('getStrategyListByPage error', error);
    }
  }
  // 根据策略 Id 获取数据
  async getStrategyListById() {
    try {
      this.strategyList = [];
      const data = await getStrategyListV2({
        limit: 50,
        bk_biz_id: this.alarmGraphConfig.bizId,
        conditions: [{ key: 'strategy_id', value: this.strategyConfig.strategy_ids }],
      });
      this.filterStrategyIdSet = new Set(data.strategy_config_list.map(({ id }) => id));
      this.strategyList.unshift(
        ...(this.strategyConfig.status.map(item => {
          const strategy = data.strategy_config_list.find(strategy => strategy.id === item.strategy_id);
          if (strategy) return strategy;
          return {
            is_deleted: true,
            name: item.name,
            id: item.strategy_id,
          };
        }) || [])
      );
      // 如果回显值过少，手动触发触底事件
      if (this.strategyList.length < 10) {
        this.handleScrollToBottom();
      }
    } catch (error) {
      console.log('getStrategyListByPage error', error);
    }
  }

  getStrategyStatus(isDeleted = false, isInvalid = false, isEnabled = true) {
    let status = ''; // 默认状态

    // 优先级 已删除 > 已屏蔽 > 已停用
    if (isDeleted) {
      status = 'deleted';
    } else if (isInvalid) {
      status = 'shielded';
    } else if (!isEnabled) {
      status = 'disabled';
    }
    return EStatusType[status];
  }

  getAddDialog() {
    return (
      <bk-dialog
        width={480}
        ext-cls='task-add-dialog'
        v-model={this.showAddTaskDialog}
        header-position='left'
        title={this.handleMuenMode === 'edit' ? this.$t('修改图表') : this.$t('新增图表')}
        show-footer
        onCancel={this.handleCancel}
      >
        <bk-form
          ref='taskForm'
          formType='vertical'
        >
          {
            <bk-form-item
              label={this.$t('策略')}
              property='dir'
            >
              <bk-select
                v-model={this.strategyConfig.strategy_ids}
                placeholder={this.$t('请选择策略')}
                scrollLoading={this.bottomLoadingOptions}
                enable-scroll-load
                multiple
                searchable
                on-scroll-end={this.handleScrollToBottom}
              >
                {this.strategyList.map(item => (
                  <bk-option
                    id={item.id}
                    key={item.id}
                    class={{ 'add-task-select-ext': true, 'is-deleted': item.is_deleted }}
                    name={item.name}
                  >
                    <div class={{ 'strategy-name': true, selected: this.isSelected(item.id) }}>{item.name}</div>
                    <div class='strategy-status'>
                      <span class='strategy-tag'>
                        {this.getStrategyStatus(item.is_deleted, item.is_invalid, item.is_enabled)}
                      </span>
                      {this.isSelected(item.id) && <span class='icon-monitor icon-mc-check-small' />}
                    </div>
                  </bk-option>
                ))}
              </bk-select>
            </bk-form-item>
          }
          {
            <bk-form-item
              label={this.$t('图表名称')}
              property='name'
            >
              <bk-input
                v-model={this.strategyConfig.name}
                placeholder={this.$t('请输入图表名称，默认为策略名称')}
              />
            </bk-form-item>
          }
        </bk-form>
        <div
          class='task-add-dialog-footer'
          slot='footer'
        >
          <bk-button
            theme='primary'
            onClick={this.handleConfirm}
          >
            {this.$t('确认')}
          </bk-button>
          <bk-button
            theme='default'
            onClick={this.handleCancel}
          >
            {this.$t('取消')}
          </bk-button>
        </div>
      </bk-dialog>
    );
  }

  async handleScrollToBottom() {
    try {
      // 判断是否为最后一页
      if (this.pagination.isLastPage) return;
      this.bottomLoadingOptions.isLoading = true;
      this.pagination.currentPage++;
      await this.getStrategyListByPage();
      this.bottomLoadingOptions.isLoading = false;
    } catch (error) {
      console.log('error', error);
    }
  }

  // 删除业务 start
  getDelDialog() {
    // console.log(this.tabs.filter(tab => tab?.bk_biz.id === this.currentDelId)[0]?.bk_biz_name);
    let detail = this.$t('业务：{0}', this.currentDelId);
    let tips = this.$t('删除后，首页将不再显示当前业务的所有告警事件视图');
    let handleDelFunction = this.delTaskByIndex;
    if (this.handleMuenMode === 'delete') {
      detail = '';
      tips = '';
      this.alarmGraphConfig.bizId = this.activeTabId;
      this.isAppendMode = true;
      handleDelFunction = this.handleConfirm;
    }
    return (
      <bk-dialog
        width={480}
        ext-cls='task-del-dialog'
        v-model={this.showDelDialog}
        header-position='left'
        show-footer={false}
        onCancel={this.handleCancelDel}
      >
        <div class='icon icon-exclamation bk-icon' />
        <div class='info'>{this.$t('确定删除该业务的告警事件视图？')}</div>
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

  /** 业务列表 */
  get bizIdList() {
    return this.$store.getters.bizList.filter(
      ({ bk_biz_id }) => !this.tabs.map(item => item.bk_biz_id).includes(bk_biz_id)
    );
  }

  // 取消删除
  handleCancelDel() {
    this.currentDelId = null;
    this.showDelDialog = false;
    this.handleMuenMode = '';
  }

  // 删除
  delTaskByIndex() {
    this.tabs = this.tabs.filter(item => item.bk_biz_id !== this.currentDelId);
    deleteAlarmGraphConfig({
      bk_biz_id: this.currentDelId,
    });
    // 当删除的是当前的业务，切换activeTab状态
    if (this.currentDelId === this.activeTabId && this.tabs.length) {
      this.activeTabId = this.tabs[0].bk_biz_id;
    }
    // 业务全部删除
    if (this.tabs.length === 0) {
      this.content = [];
    }
    this.clearStrategyConfig();
    this.showDelDialog = false;
  }
  // 删除业务 end

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
          {this.tabs.length === 0
            ? this.$t('当前还未配置业务，快点击添加业务按钮新增图表')
            : this.$t('当前业务还未配置视图，快点击下方按钮新增图表')}
        </div>
        {this.tabs.length > 0 && (
          <div class='empty-btn'>
            <bk-button
              icon='plus'
              outline={true}
              theme='primary'
              onClick={this.handleAddChart}
            >
              {this.$t('新增图表')}
            </bk-button>
          </div>
        )}
      </div>
    );
  }

  // 列表展示
  getStrategyList(list) {
    // 列表最后一个为新增图表
    const add = () => (
      <div
        class='add-content list-item'
        onClick={this.handleAddChart}
      >
        <i class='icon-mc-add icon-monitor' />
        <span>{this.$t('新增图表')}</span>
      </div>
    );
    return (
      <div class='list-content'>
        {list.map((item, index) => (
          <div
            key={item.name}
            class='list-item'
          >
            <HomeAlarmChart
              config={item}
              currentActiveId={this.activeTabId}
              timeRange={JSON.parse(this.timeRange)}
              onMenuClick={({ id }) => this.handleMuenClick(id, item, index)}
            />
          </div>
        ))}
        {add()}
      </div>
    );
  }

  handleMuenClick(mode, item, index) {
    this.handleMuenMode = mode;
    switch (mode) {
      case 'edit':
        this.strategyConfig.name = item.name;
        this.strategyConfig.strategy_ids = item.strategy_ids;
        this.strategyConfig.status = item.status;
        this.editChartIndex = index;
        this.handleAddChart(true);
        break;
      case 'delete':
        this.editChartIndex = index;
        this.showDelDialog = true;
        break;
      case 'detail':
        // TODO 详情
        break;
    }
  }

  async handleSelectBiz(id) {
    this.alarmGraphConfig.bizId = id;
    await this.getStrategyListByPage();
    this.isAppendMode = false;
    this.showAddTaskDialog = true;
  }

  render() {
    return (
      <div class='recent-alarm-events'>
        <div class='title'>
          <span>{this.$t('最近告警事件')}</span>
        </div>
        {/* 头部功能区 */}
        <div class='head'>
          {!this.loading ? (
            <div class='tabs'>
              {this.tabs.map(({ bk_biz_name: name, bk_biz_id: id }, index) => (
                <div
                  key={id}
                  class='tab'
                  draggable={true}
                  onDragleave={this.handleDragleave}
                  onDragover={e => this.handleDragover(index, e)}
                  onDragstart={() => this.handleDragstart(index)}
                  onDrop={this.handleDrop}
                >
                  <span class='icon-monitor icon-mc-tuozhuai item-drag' />
                  <span
                    class={['tab-title', this.activeTabId === id ? 'active' : '']}
                    onClick={() => this.selectTab(id)}
                  >
                    {name}
                  </span>
                  <div>
                    <span
                      class='icon-monitor item-close icon-mc-delete-line'
                      v-bk-tooltips={{
                        content: this.$t('删除该业务'),
                        trigger: 'mouseenter',
                        zIndex: 9999,
                        boundary: document.body,
                        allowHTML: false,
                      }}
                      onClick={() => this.handleDelTask(id)}
                    />
                  </div>
                </div>
              ))}
              {!this.canAddBusiness ? (
                <span
                  class='add-task task-disabled'
                  v-bk-tooltips={{
                    content: this.$t('仅支持添加 10 个业务'),
                    trigger: 'mouseenter',
                    zIndex: 9999,
                    boundary: document.body,
                    allowHTML: false,
                  }}
                >
                  <i class='bk-icon icon-plus-circle' />
                  {this.$t('添加业务')}
                </span>
              ) : (
                <HomeBizSelect
                  bizList={this.bizIdList}
                  canAddBusiness={this.canAddBusiness}
                  minWidth={380}
                  stickyList={[]}
                  theme='light'
                  onChange={this.handleSelectBiz}
                />
              )}
            </div>
          ) : (
            <div class='skeleton-element' />
          )}
          {/* 删除业务-模态框 */}
          {this.getDelDialog()}
          {/* 新增业务-模态框 */}
          {this.getAddDialog()}
          {/* 时间选择器 */}
          <div class='alarm-time-filter'>
            <bk-select
              ext-cls='alarm-time-select'
              v-model={this.timeRange}
              clearable={false}
              popover-width={70}
            >
              {shortcuts.map(option => (
                <bk-option
                  id={JSON.stringify(option.value)}
                  key={option.text}
                  name={option.text}
                />
              ))}
            </bk-select>
          </div>
        </div>
        {/* 主体内容 */}
        <div class='content'>{!this.content.length ? this.getEmptyContent() : this.getStrategyList(this.content)}</div>
      </div>
    );
  }
}
