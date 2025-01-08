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
import { Component, Ref, Watch } from 'vue-property-decorator';
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
// import HomeBizSelect from './home-biz-list';

import RecentAlarmTab from './recent-alarm-tab';

import type { TimeRangeType } from '../../../../components/time-range/time-range';
import type { IAlarmGraphConfig } from '../type';
import type { IRecentAlarmTab } from '../type';

import './recent-alarm-events.scss';

// type IProps = {};
@Component({
  name: 'RecentAlarmEvents',
  components: {
    draggable,
  },
})
export default class RecentAlarmEvents extends tsc<object> {
  tabs: IRecentAlarmTab[] = [];
  @Ref() taskForm;
  handleMeunMode: '' | 'delete' | 'detail' | 'edit' = '';

  // select 底部加载配置
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
  /** 表单规则 */
  rules = {
    name: [{ required: true, message: window.i18n.tc('必填项'), trigger: 'blur' }],
    strategy_ids: [
      {
        validator: val => val.length,
        message: window.i18n.tc('必填项'),
        trigger: 'blur',
      },
    ],
  };
  dragoverId = '';
  dragId = '';

  loading = false;

  currentDelId = null;
  strategyConfig = {
    strategy_ids: [],
    name: '',
    status: [],
  };

  timeRange = shortcuts[5].value as TimeRangeType;

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
      if (updateTab) {
        if (this.tabs.length === 0) {
          this.activeTabId = data.tags?.[0]?.bk_biz_id;
        }
        this.tabs = data.tags || [];
      }
      this.content = data.config || [];
    } catch (error) {
      console.log('get Date error', error);
    } finally {
      this.loading = false;
    }
  }

  async created() {
    await this.getData();
    this.activeTabId = this.tabs[0]?.bk_biz_id; // 默认选中第一个标签
  }

  // 拖拽完成时逻辑
  hanleDropEnd(tabs) {
    this.tabs = tabs;
  }

  // 新增图表
  handleAddChart(isEdit = false) {
    this.alarmGraphConfig.bizId = this.activeTabId;
    this.isAppendMode = true;
    this.showAddTaskDialog = true;
    isEdit ? this.getStrategyListById() : this.getStrategyListByPage();
  }

  // 取消新增图表
  handleCancel() {
    this.alarmGraphConfig.bizId = '';
    this.clearStrategyConfig();
    this.showAddTaskDialog = false;
  }
  // 确定新增图表
  async handleConfirm() {
    const isPass = await this.handleValidate();
    if (!isPass) return;
    this.processBusiness();
  }

  // 获取业务配置 ID
  getBusinessConfigId() {
    // 返回业务配置 ID，如果没有则返回当前活动的 Tab ID
    return this.alarmGraphConfig.bizId || this.activeTabId;
  }

  // 生成配置
  generateConfig() {
    // 如果是追加模式，遍历内容生成配置
    if (this.isAppendMode) {
      return this.content.map(({ name, strategy_ids }) => ({
        name,
        strategy_ids,
      }));
    }
    // 否则，返回空数组
    return [];
  }

  async processBusiness() {
    // 生成初始配置
    const config = this.generateConfig();

    // 如果在编辑模式下，处理修改或删除操作
    if (this.editChartIndex !== null) {
      if (this.handleMeunMode === 'delete') {
        // 删除指定索引的配置
        config.splice(this.editChartIndex, 1);
      } else {
        // 修改指定索引的配置
        config.splice(this.editChartIndex, 1, this.strategyConfig);
      }
    } else {
      // 如果不是编辑模式，添加新的配置
      config.push(this.strategyConfig);
    }

    try {
      // 保存告警图表配置
      await saveAlarmGraphConfig({
        bk_biz_id: this.getBusinessConfigId(),
        config,
      });
      // 如果是新增业务，需要刷新 tabs
      await this.getData(!this.isAppendMode);
    } catch (error) {
      // 捕获并处理错误
      console.error('Error saving alarm graph config:', error);
      this.$bkMessage({
        theme: 'error',
        message: this.$t('保存告警图表配置时出错，请稍后重试'),
      });
    } finally {
      // 重置编辑索引，关闭对话框，清除策略配置
      this.editChartIndex = null;
      this.showAddTaskDialog = false;
      this.clearStrategyConfig();
    }
  }

  // 清除相关数据
  clearStrategyConfig() {
    this.taskForm.clearError();
    this.strategyConfig.strategy_ids = [];
    this.strategyConfig.name = '';
    this.editChartIndex = null;
    this.handleMeunMode = '';
    this.showDelDialog = false;
    this.pagination = {
      currentPage: 1,
      limit: 10,
      isLastPage: false,
    };
    this.filterStrategyIdSet = new Set();
    this.strategyList = [];
  }

  async getStrategyListByPage() {
    if (!this.alarmGraphConfig.bizId) return;
    try {
      const { currentPage: page, limit } = this.pagination;
      const data = await getStrategyListV2({
        page,
        limit,
        bk_biz_id: this.alarmGraphConfig.bizId,
      });
      this.pagination.isLastPage = data.total <= page * limit;
      if (this.handleMeunMode === 'edit') {
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
    if (!this.alarmGraphConfig.bizId) return;
    try {
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
      console.log('getStrategyListByPage error2', error);
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

  /** 表单校验 */
  handleValidate(): Promise<boolean> {
    return this.taskForm
      .validate()
      .then(() => true)
      .catch(() => false);
  }

  getAddDialog() {
    return (
      <bk-dialog
        width={480}
        ext-cls='task-add-dialog'
        v-model={this.showAddTaskDialog}
        header-position='left'
        title={this.handleMeunMode === 'edit' ? this.$t('修改图表') : this.$t('新增图表')}
        show-footer
        onCancel={this.handleCancel}
      >
        <bk-form
          ref='taskForm'
          formType='vertical'
          {...{
            props: {
              model: this.strategyConfig,
              rules: this.rules,
            },
          }}
        >
          {
            <bk-form-item
              iconOffset={-18}
              label={this.$t('策略')}
              property='strategy_ids'
              required
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
                    <div
                      class={{
                        'strategy-name': true,
                        'has-tag': this.getStrategyStatus(item.is_deleted, item.is_invalid, item.is_enabled),
                        selected: this.isSelected(item.id),
                      }}
                      v-bk-tooltips={{
                        content: item.name,
                        trigger: 'mouseenter',
                        zIndex: 9999,
                        boundary: document.body,
                        allowHTML: false,
                        delay: [1000, 0],
                      }}
                    >
                      {item.name}
                    </div>
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
              iconOffset={-18}
              label={this.$t('图表名称')}
              property='name'
              required
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
    let detail = this.$t('业务：{0}', {
      0: this.tabs.filter(item => item.bk_biz_id === this.currentDelId)[0]?.bk_biz_name,
    });
    let tips = this.$t('删除后，首页将不再显示当前业务的所有告警事件视图');
    let handleDelFunction = this.delTaskByIndex;
    if (this.handleMeunMode === 'delete') {
      detail = '';
      tips = '';
      this.alarmGraphConfig.bizId = this.activeTabId;
      this.isAppendMode = true;
      handleDelFunction = this.processBusiness;
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

  // 取消删除
  handleCancelDel() {
    this.currentDelId = null;
    this.showDelDialog = false;
    this.handleMeunMode = '';
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
        onClick={() => this.handleAddChart()}
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
              timeRange={this.timeRange}
              onMenuClick={({ id }) => this.handleMenuClick(id, item, index)}
            />
          </div>
        ))}
        {add()}
      </div>
    );
  }

  /** MenuList操作 */
  handleMenuClick(mode, item, index) {
    this.handleMeunMode = mode;
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
      case 'detail': {
        // 跳转至事件中心
        const baseUrl = window.location.href.split('#')[0];
        let queryString = '';
        for (const id of item.strategy_ids) {
          queryString += `策略ID : ${id} OR `;
        }
        queryString = queryString.slice(0, queryString.length - 3);
        const [from, to] = this.timeRange;
        const url = `${baseUrl}#/event-center/?queryString=${encodeURIComponent(queryString)}&from=${from}&to=${to}&bizIds=${this.activeTabId}`;
        window.open(url, '_blank');
        break;
      }
    }
  }


  // 添加业务
  async handleSelectBiz(id) {
    this.alarmGraphConfig.bizId = id;
    this.strategyList = [];
    this.showAddTaskDialog = true;
    this.isAppendMode = false;
    await this.getStrategyListByPage();
  }

  render() {
    return (
      <div class='recent-alarm-events'>
        <div class='title'>
          <span>{this.$t('最近告警事件')}</span>
        </div>
        {/* 头部功能区 */}
        <RecentAlarmTab
          activeTabId={this.activeTabId}
          loading={this.loading}
          tabs={this.tabs}
          onChangeTab={id => {
            // console.log(id);
            this.activeTabId = id;
          }}
          onChangeTime={timeRange => {
            this.timeRange = timeRange;
          }}
          onHandleDelTask={this.handleDelTask}
          onHandleDropTab={this.hanleDropEnd}
          onHandleSelectBiz={this.handleSelectBiz}
        />
        {/* 主体内容 */}
        <div class='content'>{!this.content.length ? this.getEmptyContent() : this.getStrategyList(this.content)}</div>
        {/* 删除业务-模态框 */}
        {this.getDelDialog()}
        {/* 新增业务-模态框 */}
        {this.getAddDialog()}
      </div>
    );
  }
}
