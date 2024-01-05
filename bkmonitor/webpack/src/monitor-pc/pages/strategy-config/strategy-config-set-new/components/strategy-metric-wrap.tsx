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
/*
 * @Date: 2021-06-17 19:16:02
 * @LastEditTime: 2021-07-05 16:27:05
 * @Description:
 */
import { TranslateResult } from 'vue-i18n';
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getMetricListV2 } from '../../../../../monitor-api/modules/strategies';
import { deepClone } from '../../../../../monitor-common/utils/utils';
import MonitorDialog from '../../../../../monitor-ui/monitor-dialog/monitor-dialog';
import { strategyType } from '../typings/index';

import StrategyMetricTableEvent from './strategy-metric-table-event';

import './strategy-metric-wrap.scss';

const { i18n } = window;
interface IStrategyMetricWrap {
  isShow: boolean;
  readonly?: boolean;
  scenarioList: any;
  // multiple?: boolean;
  mode?: TMode;
  isEdit?: boolean;
  monitorType?: string;
  checkedMetric?: any[]; // 回显指标数据
  strategyType?: strategyType;
}
interface IEventFn {
  onShowChange?: boolean;
  onLeftSelect?: string;
  onSelected?: any;
}
interface IPagination {
  page: number;
  limit: number;
}
interface ITabItem {
  id: string;
  name: string | TranslateResult;
  count: number;
  data: any;
  show: boolean;
}

export type TMode = 'event' | 'log';

@Component({
  name: 'StrategyMetricWrap'
})
export default class StrategyMetricWrap extends tsc<IStrategyMetricWrap, IEventFn> {
  @Prop({ default: 'event', type: String }) mode: TMode;
  @Prop({ default: 'application_check', type: String }) monitorType: string;
  @Prop({ default: false, type: Boolean }) isShow: boolean;
  @Prop({ default: () => [], type: Array }) scenarioList: any;
  @Prop({ default: false, type: Boolean }) isEdit: boolean;
  @Prop({ default: () => [] }) checkedMetric: any[];
  @Prop({ default: false, type: Boolean }) readonly: boolean;
  @Prop({ default: 'monitor', type: String }) strategyType: strategyType;

  // 搜索可选列表
  searchKeyList: any = [];
  localCheckedId: string[] = [];
  // 选中指标
  localCheckedMetric = [];

  isLoading = false;
  // 头部搜索数据
  searchData = {
    keyWord: [],
    interval: 7,
    justSelected: false
  };
  // 分页数据
  pagination: IPagination = {
    page: 1,
    limit: 20
  };

  // 标题
  titleMap = {
    event: i18n.t('选择事件'),
    log: i18n.t('选择日志关键字')
  };

  // 侧栏选中数据
  leftActive = 'application_check';

  // tab选中数据
  tabActive = 'bk_monitor';

  // 事件数据
  eventTabList: ITabItem[] = [
    { id: 'bk_monitor', name: i18n.t('系统事件'), count: 0, data: null, show: true },
    { id: 'custom', name: i18n.t('自定义事件'), count: 0, data: null, show: true },
    { id: 'bk_fta', name: i18n.t('第三方告警'), count: 0, data: null, show: true }
  ];
  // 日志数据
  logTabList: ITabItem[] = [
    { id: 'bk_monitor', name: i18n.t('监控采集'), count: 0, data: null, show: true },
    { id: 'bk_log_search', name: i18n.t('日志平台'), count: 0, data: null, show: true },
    { id: 'bk_apm', name: i18n.t('应用监控'), count: 0, data: null, show: true }
  ];

  // 指标数据
  dataSourceCountList = [];
  scenarioCountList = [];
  metricList = [];

  get getTitle() {
    return this.titleMap[this.mode];
  }

  get tabList() {
    const map = {
      event: this.getEventTabList,
      log: this.getLogTabList
    };
    return map[this.mode];
  }

  get curTabData() {
    const target = this.mode === 'event' ? this.eventTabList : this.logTabList;
    const res = target.find(item => item.id === this.tabActive);
    return res ? res : null;
  }

  // 获取侧栏数据
  get getLeftList() {
    const list = deepClone(this.scenarioList);
    const countMap = {};
    this.scenarioCountList.forEach(item => {
      countMap[item.id] = item.count;
    });
    const res = list.reduce((total, cur) => {
      const child = cur.children || [];
      total = total.concat(child);
      return total;
    }, []);
    res.forEach(item => {
      this.$set(item, 'count', countMap[item.id] || 0);
    });
    return res;
  }

  // tab数据
  get getEventTabList() {
    const res = this.eventTabList.map(item => {
      const obj = this.dataSourceCountList.find(
        me => me.data_type_label === this.mode && me.data_source_label === item.id
      );
      obj && (item.count = obj.count);
      return item;
    });
    return res;
  }
  get getLogTabList() {
    const res = this.logTabList.map(item => {
      const obj = this.dataSourceCountList.find(
        me => me.data_type_label === this.mode && me.data_source_label === item.id
      );
      obj && (item.count = obj.count);
      return item;
    });
    return res;
  }

  // 添加按钮禁用状态
  get isCanAdd(): boolean {
    return !this.localCheckedId.length;
  }

  // 表格数据
  get tabelData() {
    const data = deepClone(this.curTabData?.data || []);
    return data;
  }

  created() {
    if (this.strategyType === 'fta') {
      this.tabActive = 'bk_fta';
      this.eventTabList.forEach(item => {
        item.show = item.id === 'bk_fta';
      });
    }
  }

  @Emit('selected')
  handleAddMetric() {
    this.showChange(false);
    this.emitLeftSelect();
    return deepClone(this.localCheckedMetric);
  }

  @Emit('showChange')
  showChange(v: boolean) {
    return v;
  }

  @Emit('leftSelect')
  emitLeftSelect() {
    return this.leftActive;
  }

  @Watch('isShow')
  isShowChange(v: boolean) {
    if (!v) return this.initData();
    if (this.isEdit) {
      this.localCheckedMetric = this.checkedMetric;
      this.localCheckedId = this.checkedMetric.map(item => item.metric_id);
      if (this.checkedMetric[0]) {
        this.tabActive = this.checkedMetric[0].data_source_label;
        this.leftActive = this.checkedMetric[0].result_table_label || this.monitorType;
      }
    }
    this.getSearchOptions();
    this.getDataList();
  }

  @Watch('monitorType', { immediate: true })
  monitorTypeChange(val: string) {
    this.leftActive = val;
  }

  initData() {
    this.tabActive = this.strategyType === 'fta' ? 'bk_fta' : 'bk_monitor';
    this.pagination.page = 1;
    this.searchData.keyWord = [];
    this.clearLocalChecked();
  }

  handleSearch() {
    this.pagination.page = 1;
    this.getMetricList();
  }

  getSearchCondition() {
    return this.searchData.keyWord.map(item => ({
      key: item.values ? item.id : 'query',
      value: item.values ? item.values.map(val => val.id) : item.id
    }));
  }

  getDataList() {
    this.getMetricList();
    // this.mode === 'event' && this.getMetricList()
    // this.mode === 'log' && this.getLogDataList()
  }

  // 获取指标数据
  getMetricList(customParams = null, needLoading = true) {
    return new Promise((resolve, reject) => {
      needLoading && (this.isLoading = true);
      const { page, limit } = this.pagination;
      const params = {
        data_source_label: Array.isArray(this.tabActive) ? this.tabActive : [this.tabActive],
        data_type_label: this.mode,
        page,
        page_size: limit,
        result_table_label: this.leftActive,
        conditions: this.getSearchCondition()
      };
      getMetricListV2(customParams || params)
        .then(res => {
          this.dataSourceCountList = res.data_source_list;
          this.scenarioCountList = res.scenario_list;
          this.setMetricList(res.metric_list);
          resolve(res);
        })
        .catch(err => reject(err))
        .finally(() => needLoading && (this.isLoading = false));
    });
  }

  setMetricList(metricList) {
    if (this.curTabData) {
      const { page } = this.pagination;
      const pageData = metricList.map(item => {
        this.$set(item, 'checked', false);
        return item;
      });
      page === 1 && (this.curTabData.data = pageData);
      page > 1 && this.curTabData.data.push(...pageData);
    }
  }

  clearMetricData() {
    this.eventTabList.forEach(item => (item.data = null));
  }

  // 选中侧栏操作
  leftListItemSelect(item) {
    if (this.leftActive === item.id) return;
    this.pagination.page = 1;
    this.leftActive = item.id;
    this.clearTableData();
    this.getSearchOptions();
    this.clearLocalChecked();
    this.clearMetricData();
    this.getDataList();
    // this.emitLeftSelect(item)
  }

  // 清空缓存数据
  clearTableData() {
    const tabDataMap = ['eventTabList', 'logTabList'];
    tabDataMap.forEach(key => {
      this?.[key]?.forEach(item => {
        item.count = 0;
        item.data = null;
      });
    });
  }

  // 清空已选信息
  clearLocalChecked() {
    this.localCheckedId = [];
    this.localCheckedMetric = [];
  }

  // tab选中
  handleTabChange(item) {
    if (item.id === this.tabActive) return;
    this.tabActive = item.id;
    this.getCurPage();
    this.getSearchOptions();
    !this.curTabData.data && this.getDataList();
  }

  getCurPage() {
    const { data } = this.curTabData;
    if (!data) return (this.pagination.page = 1);
    const leng = this.curTabData.data.length;
    const { limit } = this.pagination;
    this.pagination.page = Math.ceil(leng / limit);
  }

  // 获取下一分页
  getNextPage(): number {
    const { page, limit } = this.pagination;
    const { count } = this.curTabData;
    const isTotal = count <= page * limit;
    if (isTotal) return null;
    return page + 1;
  }

  handleScrollToEnd(v: boolean) {
    if (v) {
      const page = this.getNextPage();
      if (!page) return;
      this.pagination.page = page;
      this.getMetricList(null, false);
    }
  }

  // 选中操作
  handleCheckedChange({ ids, rows }) {
    this.localCheckedId = ids;
    this.localCheckedMetric = rows;
  }

  // 刷新数据
  handleRefresh() {
    this.clearMetricData();
    this.localCheckedMetric = [];
    this.localCheckedId = [];
    this.pagination.page = 1;
    this.getMetricList();
  }

  /**
   * 根据不同的sourceType生成不同的搜索选项
   */
  getSearchOptions(sourceType = `${this.tabActive}_${this.mode}`) {
    const options = [
      // { id: 'plugin_id', name: this.$t('插件ID'), children: [] },
      // { id: 'plugin_name', name: this.$t('插件名'), children: [] },
      { id: 'result_table_name', name: this.$t('表别名'), children: [] },
      { id: 'result_table_id', name: this.$t('表名'), children: [] },
      { id: 'collect_config', name: this.$t('采集配置'), children: [] },
      { id: 'metric_field', name: this.$t('指标名'), children: [] },
      { id: 'metric_filed_name', name: this.$t('指标别名'), children: [] },
      { id: 'plugin_type', name: this.$t('插件类型'), children: [] }
    ];
    const searchObj = {
      bk_monitor_time_series: [...options],
      bk_data_time_series: [...options],
      custom_time_series: [...options],
      log_time_series: [...options, { id: 'releated_id', name: this.$t('索引集'), children: [] }],
      bk_monitor_event: [...options],
      custom_event: [
        { id: 'result_table_name', name: this.$t('数据名称'), children: [] },
        { id: 'metric_field_name', name: this.$t('事件名称'), children: [] },
        { id: 'result_table_id', name: this.$t('数据ID'), children: [] },
        { id: 'metric_field', name: this.$t('事件ID'), children: [] }
      ]
    };
    let searchList = searchObj[sourceType] || [];

    if (sourceType === 'log_time_series') {
      searchList.find(item => item.id === 'result_table_name').name = this.$t('索引');
    }

    if (this.mode === 'event') {
      if (sourceType === 'bk_fta_event') {
        // searchList.push({ id: 'metric_field_name', name: this.$t('告警名称') })
        searchList = [];
      } else if (this.leftActive === 'uptimecheck') {
        searchList.push(
          { id: 'task_id', name: this.$t('任务ID'), children: [] },
          { id: 'task_name', name: this.$t('任务名'), children: [] }
        );
      } else {
        searchList.push(
          { id: 'plugin_id', name: this.$t('插件ID'), children: [] },
          { id: 'plugin_name', name: this.$t('插件名'), children: [] }
        );
      }
    }
    this.searchKeyList = searchList;
  }

  render() {
    return (
      <MonitorDialog
        class='strategy-metric-wrap'
        value={this.isShow}
        title={this.getTitle}
        width='850'
        {...{ on: { 'update:value': this.showChange } }}
      >
        <div v-bkloading={{ isLoading: this.isLoading }}>
          <div class='metric-wrap-common'>
            <div class='metric-handle-row'>
              <bk-search-select
                class='search-select'
                v-model={this.searchData.keyWord}
                showPopoverTagChange={false}
                popoverZindex={2600}
                data={this.searchKeyList}
                placeholder={this.$t('关键字搜索')}
                show-condition={false}
                onChange={this.handleSearch}
              ></bk-search-select>
              <bk-button
                class='btn-refresh'
                icon='icon-refresh'
                onClick={this.handleRefresh}
              ></bk-button>
            </div>
          </div>
          <div class='metric-wrap-main'>
            {/* 左侧监控对象列表 */}
            <div class='metric-wrap-main-left'>
              <ul class='left-list'>
                {this.getLeftList.map(item => (
                  <li
                    class={['left-list-item', { 'left-list-item-active': item.id === this.leftActive }]}
                    onClick={() => this.leftListItemSelect(item)}
                  >
                    <span>{item.name}</span>
                    <span class='item-count'>{item.count || 0}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div class='metric-wrap-main-right'>
              {/* 右侧tab */}
              <div class='tab-list-wrap'>
                <ul class='tab-list'>
                  {this.tabList.map(item =>
                    item.show ? (
                      <li
                        class={['tab-item', { 'tab-item-active': item.id === this.tabActive }]}
                        onClick={() => this.handleTabChange(item)}
                      >
                        <div class='tab-item-main'>
                          <span class='tab-item-text'>{item.name}</span>
                          <span class='tab-item-count'>{item.count}</span>
                        </div>
                      </li>
                    ) : undefined
                  )}
                </ul>
              </div>
              <div style='padding-top: 8px;'>
                {/* 数据表格 */}
                <StrategyMetricTableEvent
                  data={this.tabelData}
                  type={this.tabActive}
                  mode={this.mode}
                  readonly={this.readonly}
                  checked={this.localCheckedId}
                  onScrollToEnd={this.handleScrollToEnd}
                  onCheckedChange={this.handleCheckedChange}
                ></StrategyMetricTableEvent>
              </div>
            </div>
          </div>
        </div>
        <div slot='footer'>
          <bk-button
            theme='primary'
            disabled={this.readonly || this.isCanAdd}
            onClick={this.handleAddMetric}
          >
            {this.$t('添加')}
          </bk-button>
          <bk-button
            style='margin-left: 10px;'
            onClick={() => this.showChange(false)}
          >
            {this.$t('取消')}
          </bk-button>
        </div>
      </MonitorDialog>
    );
  }
}
