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
/* eslint-disable camelcase */
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { debounce, throttle } from 'throttle-debounce';

import { getMetricListV2 } from '../../../../../monitor-api/modules/strategies';
import { deepClone } from '../../../../../monitor-common/utils/utils';
import MonitorDialog from '../../../../../monitor-ui/monitor-dialog/monitor-dialog.vue';
import { MetricDetail } from '../typings/index';

import './strategy-metric-alert.scss';

interface IStrategyMetricAlertProps {
  isShow: boolean;
  scenarioList: IScenarioItem[];
  monitorType?: string;
  metricData?: MetricDetail[];
}
interface IStrategyMetricAlertEvent {
  onShowChange?: boolean;
  onSelected?: any[];
  onScenarioChange?: string;
}
interface IDataSource {
  bk_fta_alert?: IDataSourceItem; // 第三方告警
  bk_monitor_alert?: IDataSourceItem; // 告警策略
}
interface IDataSourceItem {
  count: number;
  dataSourceLabel: string;
  dataTypeLabel: string;
  sourceType: string;
  sourceName: string;
  list: any[];
}
interface IScenarioItem {
  id: string;
  name: string;
  children?: IScenarioItem[];
}
interface ISearchObj {
  keyWord: { values: { id: string; name: string }[]; id: string; name: string }[];
  data: ISearchOption[];
}
interface ISearchOption {
  id: string;
  name: string;
  children: any[];
}
interface IStaticParams {
  bk_biz_id: number;
  data_source_label: string[];
  data_type_label: string;
  result_table_label: string;
}
interface ICache {
  [propName: string]: { page?: number; list?: any[]; count?: number; scrollTop?: number; scenarioCounts?: any[] };
}
@Component({
  name: 'StrategyMetricAlert'
})
export default class StrategyMetricAlert extends tsc<IStrategyMetricAlertProps, IStrategyMetricAlertEvent> {
  @Prop({ type: Boolean, default: false }) isShow: boolean;
  @Prop({ type: Array, default: () => [] }) scenarioList: IScenarioItem[];
  @Prop({ default: 'application_check', type: String }) monitorType: string;
  @Prop({ default: () => [], type: Array }) metricData: MetricDetail[];
  @Ref('alertTable') tableRef: any;

  isLoading = false;
  // 数据来源
  sourceType = 'bk_monitor_alert';
  dataSource: IDataSource = {};
  oldDataSourec: IDataSource = {};
  isSeeSelected = false;
  // 各监控对象的count值
  scenarioCounts: any[] = [];
  scenarioType = '';
  // 筛选项
  searchObj: ISearchObj = {
    // 键值对搜索数据
    keyWord: [],
    data: []
  };
  pageSize = 20;
  cache: ICache = {};
  checkData: MetricDetail[] = [];
  scrollEl = null;
  throttledScroll: Function = () => {};
  handleSearch: Function = () => {};

  //  处理监控对象数据结构
  get scenarioListAll() {
    let arr = [];
    const list = JSON.parse(JSON.stringify(this.scenarioList));
    if (this.scenarioCounts.length !== 0) {
      arr = this.scenarioCounts.map(item => ({ name: item.id, label: item.name, count: item.count }));
    } else {
      list.reverse().forEach(item => {
        const child = item.children.map(one => ({ name: one.id, label: one.name, count: 0 }));
        arr = [...child, ...arr];
      });
    }
    return arr;
  }

  get curTableData(): IDataSourceItem {
    return this.dataSource[this.sourceType];
  }

  // 生成后台所需要的搜索参数
  get seachParams() {
    const strValue = [];
    const objValue = [];
    this.searchObj.keyWord.forEach(item => {
      if (Array.isArray(item.values)) {
        const temp = { key: item.id, value: item.values.map(v => v.id) };
        objValue.push(temp);
      } else {
        const temp = { key: 'query', value: item.id };
        strValue.push(temp);
      }
    });
    return [...strValue, ...objValue];
  }

  // 是否可以添加
  get isCanAdd(): boolean {
    return this.checkData.length >= 2;
  }

  @Watch('isShow')
  isShowChange(v: boolean) {
    if (v) {
      this.dataInit();
      this.scenarioType = this.monitorType;
      if (this.metricData.length) {
        this.checkData = [...this.metricData];
        const item = this.metricData[0];
        this.sourceType = `${item.data_source_label}_${item.data_type_label}`;
      }
      this.cacheDataInit();
      this.getMonitorSource();
    }
  }

  @Emit('showChange')
  handleShowChange(val: boolean) {
    return val;
  }
  @Emit('scenarioChange')
  handleScenarioChange() {
    return this.scenarioType;
  }
  @Emit('selected')
  handleAdd(): any[] {
    this.handleShowChange(false);
    this.handleScenarioChange();
    return this.checkData;
  }

  created() {
    this.dataInit();
    this.searchObj.keyWord = [];
    this.handleSearch = debounce(300, false, this.handleSearchChange);
    this.searchObj.data = this.getSearchOptions();
  }

  mounted() {
    this.scrollEl = this.tableRef.$el.querySelector('.bk-table-body-wrapper');
    this.throttledScroll = throttle(300, false, this.handleTableScroll);
    this.scrollEl.addEventListener('scroll', this.throttledScroll);
  }

  /**
   * @description: 初始化
   * @param {*}
   * @return {*}
   */
  dataInit(isCache = true, isClearChecked = true) {
    this.dataSource = {
      bk_monitor_alert: {
        count: 0,
        dataSourceLabel: 'bk_monitor',
        dataTypeLabel: 'alert',
        sourceType: 'bk_monitor_alert',
        sourceName: `${this.$t('告警策略')}`,
        list: []
      },
      bk_fta_alert: {
        count: 0,
        dataSourceLabel: 'bk_fta',
        dataTypeLabel: 'alert',
        sourceType: 'bk_fta_alert',
        sourceName: `${this.$t('第三方告警')}`,
        list: []
      }
    };
    this.oldDataSourec = deepClone(this.dataSource);
    if (isClearChecked) {
      this.checkData = [];
    }
    if (isCache) {
      this.cache = {};
    }
    this.isSeeSelected = false;
  }

  /**
   * @description: 搜索可选项
   * @param {*}
   * @return {*}
   */
  getSearchOptions() {
    const searchObj = {
      bk_fta_alert: [{ id: 'alert_name', name: this.$t('指标名'), children: [] }],
      bk_monitor_alert: [
        { id: 'strategy_name', name: this.$t('策略名称'), children: [] },
        { id: 'strategy_id', name: this.$t('策略ID'), children: [] }
      ]
    };
    return searchObj[this.sourceType];
  }

  /**
   * @description: 获取指标数据
   * @param {string} dataSourceLabel
   * @param {string} dataTypeLabel
   * @param {*} staticObj
   * @return {*}
   */
  async getMonitorSource(dataSourceLabel?: string, dataTypeLabel?: string, staticObj?) {
    this.isLoading = true;
    // // 处理外部调用(仪表盘跳转)时传进来的参数
    const staticParams = this.handleStaticParams(dataSourceLabel, dataTypeLabel, staticObj);
    const cacheKey = `${this.sourceType}_${this.scenarioType}`;
    const params = {
      ...staticParams,
      conditions: this.seachParams,
      page_size: this.pageSize,
      page: this.cache?.[cacheKey]?.page ? this.cache[cacheKey].page : 1
    };
    await getMetricListV2(params)
      .then(data => {
        this.scenarioCounts = data.scenario_list;
        data.data_source_list.forEach(item => {
          if (this.dataSource[item.id]) {
            this.dataSource[item.id].count = item.count;
          }
        });
        if (params.page === 1) {
          this.dataSource[this.sourceType].list = data.metric_list;
        } else {
          this.dataSource[this.sourceType].list = [...this.dataSource[this.sourceType].list, ...data.metric_list];
        }
        if (!this.seachParams.length) {
          this.cache[cacheKey].list = this.dataSource[this.sourceType].list;
          this.cache[cacheKey].scenarioCounts = data.scenario_list;
        }
        this.cache[cacheKey].count = this.dataSource[this.sourceType].count;
      })
      .finally(() => {
        this.isLoading = false;
      });
  }

  /**
   * @description: 默认上传参数
   * @param {string} dataSourceLabel
   * @param {string} dataTypeLabel
   * @param {*} staticObj
   * @return {*}
   */
  handleStaticParams(dataSourceLabel?: string, dataTypeLabel?: string, staticObj?): IStaticParams {
    if (staticObj) return staticObj;
    const dataSource = dataSourceLabel || this.curTableData.dataSourceLabel;
    return {
      bk_biz_id: this.$store.getters.bizId,
      data_source_label: Array.isArray(dataSource) ? dataSource : [dataSource],
      data_type_label: dataTypeLabel || this.curTableData.dataTypeLabel,
      result_table_label: this.scenarioType
    };
  }

  /**
   * @description: 搜索
   * @param {*}
   * @return {*}
   */
  handleSearchChange() {
    this.dataInit(false, false);
    const cacheKey = `${this.sourceType}_${this.scenarioType}`;
    this.cache[cacheKey].page = 1;
    this.getMonitorSource();
  }

  /**
   * @description: 刷新数据
   * @param {*}
   * @return {*}
   */
  handleRefresh() {
    this.dataInit();
    this.searchObj.keyWord = [];
    this.cacheDataInit();
    this.getMonitorSource();
  }

  /**
   * @description: 只看已选
   * @param {boolean} val
   * @return {*}
   */
  async handleseeSelectedChange(val: boolean) {
    if (val) {
      this.oldDataSourec[this.sourceType].list = this.curTableData.list;
    } else {
      this.dataSource[this.sourceType].list = this.oldDataSourec[this.sourceType].list;
      this.oldDataSourec[this.sourceType].list = [];
    }
  }

  /**
   * @description: 切换数据来源
   * @param {string} sourceType
   * @return {*}
   */
  handleSourceTypeChange(sourceType: string) {
    if (this.sourceType === sourceType) return;
    this.cacheScrollTop();
    this.isSeeSelected = false;
    this.sourceType = sourceType;
    this.searchObj.data = this.getSearchOptions();
    this.searchObj.keyWord = [];
    this.cacheDataSet();
  }

  /**
   * @description: 切换监控对象
   * @param {string} scenarioType
   * @return {*}
   */
  async handleLeftChange(scenarioType: string) {
    if (this.scenarioType === scenarioType) return;
    this.cacheScrollTop();
    this.isSeeSelected = false;
    this.scenarioType = scenarioType;
    this.searchObj.data = this.getSearchOptions();
    this.searchObj.keyWord = [];
    this.cacheDataSet();
  }

  /**
   * @description: 写入滚动条位置
   * @param {boolean} isSet
   * @return {*}
   */
  cacheScrollTop(isSet = true) {
    const cacheKey = `${this.sourceType}_${this.scenarioType}`;
    if (isSet) {
      this.cache[cacheKey].scrollTop = this.scrollEl.scrollTop;
    } else {
      this.scrollEl.scrollTop = this.cache[cacheKey].scrollTop;
    }
  }

  /**
   * @description: 写入缓存数据
   * @param {*}
   * @return {*}
   */
  cacheDataSet() {
    const cacheKey = `${this.sourceType}_${this.scenarioType}`;
    if (this.cache?.[cacheKey]?.list && this.cache[cacheKey].list.length <= this.cache[cacheKey].count) {
      this.dataSource[this.sourceType].list = this.cache[cacheKey].list;
      this.dataSource[this.sourceType].count = this.cache[cacheKey].count;
      this.scenarioCounts = this.cache[cacheKey].scenarioCounts;
      this.$nextTick(() => this.cacheScrollTop(false));
    } else {
      this.cacheDataInit(false);
      this.getMonitorSource();
    }
  }

  /**
   * @description: 初始化缓存数据
   * @param {boolean} isInit
   * @return {*}
   */
  cacheDataInit(isInit = true) {
    if (isInit) {
      this.cache = {};
    }
    const cacheKey = `${this.sourceType}_${this.scenarioType}`;
    this.cache[cacheKey] = { page: 1, list: [], count: 0, scrollTop: 0 };
  }

  /**
   * @description: 列表滑动到底部时下一页
   * @param {any} e
   * @return {*}
   */
  async handleTableScroll(e: any) {
    if (this.isSeeSelected) return;
    const { scrollHeight, scrollTop, clientHeight } = e.target;
    const isEnd = scrollHeight - scrollTop === clientHeight && scrollTop;
    const { count: metricCount } = this.dataSource[this.sourceType];
    const cacheKey = `${this.sourceType}_${this.scenarioType}`;
    if (!(isEnd && this.cache[cacheKey].page * this.pageSize <= metricCount)) return;
    this.cache[cacheKey].page += 1;
    await this.getMonitorSource();
  }

  /**
   * @description: 选中
   * @param {boolean} val
   * @param {any} row
   * @return {*}
   */
  handleCheck(val: boolean, row: any) {
    const { metric_id } = row;
    if (val) {
      this.checkData.push(row);
    } else {
      const index = this.checkData.findIndex((item: any) => item.metric_id === metric_id);
      index >= 0 && this.checkData.splice(index, 1);
    }
  }
  /**
   * @description: 全选
   * @param {boolean} val
   * @return {*}
   */
  handleAllCheck(val: boolean) {
    const checkedMetricIdList = this.checkData.map((item: any) => item.metric_id);
    if (val) {
      this.curTableData.list.forEach(item => {
        if (!checkedMetricIdList.includes(item.metric_id)) {
          this.checkData.push(item);
        }
      });
    } else {
      this.curTableData.list.forEach(item => {
        if (checkedMetricIdList.includes(item.metric_id)) {
          const index = this.checkData.findIndex((data: any) => data.metric_id === item.metric_id);
          index >= 0 && this.checkData.splice(index, 1);
        }
      });
    }
  }

  /**
   * @description: 只看已选模式下
   * @param {*} row
   * @return {*}
   */
  handleDeleteCheckedMetric(row) {
    const index = this.checkData.findIndex((data: any) => data.metric_id === row.metric_id);
    index >= 0 && this.checkData.splice(index, 1);
  }

  getTableComponent() {
    const checkboxSlot = {
      default: ({ row }) => {
        const isCheck = this.checkData.map((item: any) => item.metric_id).includes(row.metric_id);
        return (
          <bk-checkbox
            checked={isCheck}
            on-change={v => this.handleCheck(v, row)}
          ></bk-checkbox>
        );
      }
    };
    const seeCheckedSlot = {
      default: ({ row }) => (
        <bk-checkbox
          checked={true}
          on-change={() => this.handleDeleteCheckedMetric(row)}
        ></bk-checkbox>
      )
    };
    const renderHeader = () => {
      const checkedMetricIdList = this.checkData.map((item: any) => item.metric_id);
      const curMetricIdList = this.curTableData.list.map((item: any) => item.metric_id);
      const isAllChecked =
        curMetricIdList.every(item => checkedMetricIdList.includes(item)) && this.curTableData.list.length > 0;
      return (
        <bk-checkbox
          checked={isAllChecked}
          on-change={this.handleAllCheck}
          disabled={this.curTableData.list.length === 0}
        ></bk-checkbox>
      );
    };
    const renderSeeCheckedHeader = () => (
      <bk-checkbox
        checked={true}
        on-change={() => (this.checkData = [])}
        disabled
      ></bk-checkbox>
    );
    const checkBox = (
      <bk-table-column
        width={48}
        scopedSlots={checkboxSlot}
        render-header={renderHeader}
      ></bk-table-column>
    );
    const columnMap = {
      bk_monitor_alert: () => [
        checkBox,
        <bk-table-column
          label={this.$t('策略ID')}
          prop='metric_field'
          width='80'
          show-overflow-tooltip
        ></bk-table-column>,
        <bk-table-column
          label={this.$t('策略名称')}
          prop='metric_field_name'
          show-overflow-tooltip
        ></bk-table-column>
      ],
      bk_fta_alert: () => [
        checkBox,
        <bk-table-column
          label={this.$t('告警名称')}
          prop='metric_field_name'
          show-overflow-tooltip
        ></bk-table-column>
      ],
      seeChecked: () => [
        <bk-table-column
          width={48}
          key={String(this.isSeeSelected)}
          scopedSlots={seeCheckedSlot}
          render-header={renderSeeCheckedHeader}
        ></bk-table-column>,
        <bk-table-column
          label={`${this.$t('策略名称')}/${this.$t('告警名称')}`}
          prop='metric_field_name'
          show-overflow-tooltip
        ></bk-table-column>
      ]
    };
    return (
      <div class='metric-alert-table'>
        <bk-table
          {...{
            props: {
              data: this.isSeeSelected ? this.checkData : this.curTableData.list
            }
          }}
          ref='alertTable'
          height={397}
          max-height={397}
          outer-border={false}
        >
          {this.isSeeSelected ? columnMap.seeChecked() : columnMap[this.sourceType]()}
        </bk-table>
      </div>
    );
  }

  render() {
    return (
      <MonitorDialog
        class='strategy-metric-alert'
        value={this.isShow}
        title={this.$t('选择关联告警')}
        width={850}
        on-change={this.handleShowChange}
      >
        <div v-bkloading={{ isLoading: this.isLoading }}>
          <div class='metric-wrap-common'>
            <div class='metric-handle-row'>
              <bk-search-select
                class='search-select'
                ref='searchSelect'
                v-model={this.searchObj.keyWord}
                showPopoverTagChange={false}
                popoverZindex={2600}
                data={this.searchObj.data}
                placeholder={this.$t('关键字搜索')}
                on-change={this.handleSearch}
                show-condition={false}
              ></bk-search-select>
              <bk-button
                class='btn-refresh'
                icon='icon-refresh'
                onClick={this.handleRefresh}
              ></bk-button>
              <div class='see-selected'>
                <bk-checkbox
                  checked={false}
                  true-value={true}
                  false-value={false}
                  v-model={this.isSeeSelected}
                  on-change={this.handleseeSelectedChange}
                >
                  <div class='selected-text'>
                    {this.$t('只看已选')}
                    <span class='num'>{`(${this.checkData.length})`}</span>
                  </div>
                </bk-checkbox>
              </div>
            </div>
          </div>
          <div class='metric-wrap-main'>
            <div class='wrap-main-left'>
              <ul class='left-list'>
                {this.scenarioListAll.map(item => (
                  <li
                    class={['left-list-item', { 'left-list-item-active': this.scenarioType === item.name }]}
                    key={item.name}
                    on-click={() => this.handleLeftChange(item.name)}
                  >
                    <span>{item.label}</span>
                    <span class='item-count'>{item.count}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div class='wrap-main-right'>
              <div class='tab-list-wrap'>
                <ul class='tab-list'>
                  {Object.keys(this.dataSource).map(key => (
                    <li
                      class={['tab-item', { 'tab-item-active': this.dataSource[key].sourceType === this.sourceType }]}
                      onClick={() => this.handleSourceTypeChange(this.dataSource[key].sourceType)}
                    >
                      <div class='tab-item-main'>
                        <span class='tab-item-text'>{this.dataSource[key].sourceName}</span>
                        <span class='tab-item-count'>{this.dataSource[key].count}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
              {this.getTableComponent()}
            </div>
          </div>
        </div>
        <div slot='footer'>
          <span
            style='display: inline-block;'
            v-bk-tooltips={{
              content: this.$t('关联告警需选择多个'),
              disabled: this.isCanAdd,
              allowHTML: false
            }}
          >
            <bk-button
              theme='primary'
              onClick={this.handleAdd}
              disabled={!this.isCanAdd}
            >
              {this.$t('添加')}
            </bk-button>
          </span>
          <bk-button
            style='margin-left: 10px;'
            onClick={() => this.handleShowChange(false)}
          >
            {this.$t('取消')}
          </bk-button>
        </div>
      </MonitorDialog>
    );
  }
}
