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

import { Component, Emit, Mixins, Prop, Watch } from 'vue-property-decorator';
import * as tsx from 'vue-tsx-support';
// import MonitorDateRange from '../../../../components/monitor-date-range/monitor-date-range.vue'
import { debounce, throttle } from 'throttle-debounce';

import { getMetricListV2 } from '../../../../../monitor-api/modules/strategies';
import { deepClone } from '../../../../../monitor-common/utils/utils';
import MonitorDialog from '../../../../../monitor-ui/monitor-dialog/monitor-dialog.vue';
import { handleGotoLink } from '../../../../common/constant';
import metricTipsContentMixin from '../../../../mixins/metricTipsContentMixin';
import {
  IDataSource,
  IDataSourceItem,
  ISearchObj,
  ISearchOption,
  IStaticParams
} from '../../../../types/strategy-config/strategy-metric';
import { IScenarioItem, MetricDetail } from '../typings/index';

import HorizontalScrollContainer from './horizontal-scroll-container';

import './strategy-metric-common.scss';

interface IStrategyMetricCommon {
  isShow: boolean;
  scenarioList: IScenarioItem[];
  monitorType: string;
  timerangeList?: IOption;
  metricData: MetricDetail[];
  multiple?: boolean;
  readonly?: boolean;
  maxLength?: number;
}
interface IOption {
  name: string;
  id?: string | number;
  value?: string | number;
  children?: IOption[];
}

interface ICache {
  [propName: string]: {
    page?: number;
    list?: any[];
    count?: number;
    scrollTop?: number;
    tags?: { id: string; name: string }[];
    scenarioCounts?: any[];
  };
}

@Component({
  name: 'StrategyMetricCommon'
})
class StrategyMetricCommon extends Mixins(metricTipsContentMixin) {
  @Prop({ type: Boolean, default: false }) isShow: boolean;
  @Prop() readonly scenarioList: IScenarioItem[]; // 监控对象列表
  @Prop({ default: 'application_check' }) readonly monitorType: string; // 传进来的监控对象
  @Prop({ default: () => [], type: Array }) metricData: MetricDetail[];
  @Prop({ default: false, type: Boolean }) multiple: boolean; // 是否多选
  @Prop({ default: false, type: Boolean }) readonly: boolean; // 是否只读
  @Prop({ default: 10, type: Number }) maxLength: number; // 多指标最大选择个数

  loading = false;
  searchObj: ISearchObj = {
    // 键值对搜索数据
    keyWord: [],
    data: []
  };
  scenarioCounts = []; // 各监控对象的count值
  sourceType = 'bk_monitor_time_series'; // 数据来源
  scenarioType = ''; // 当前监控对象
  isSeeSelected = false; // 是否只看已选
  dataSource: IDataSource = {};
  cache: ICache = {}; // 缓存已加载的数据
  checkedMetric = []; // 已选指标
  oldDataSource = {}; // 只看已选时保存已加载datasource
  oldCheckedMetricTap = {
    // 已选指标的数据来源及监控对象
    sourceType: '',
    scenarioType: ''
  };
  hoverTimer = null; // tip
  popoverInstance = null;
  popoverConfirmInstance = null; // 选择指标时确认tip
  curPopoverMetric = null; // 弹出确认tip时选中的指标
  pageSize = 28; // 每页个数
  scrollEl = null; // 滚动条
  isCheckedOther = false; // 是否已选择其他数据来源的指标
  tag = {
    value: '',
    list: []
  };
  paramsMap = {
    bk_monitor_time_series: 'fromMonitor', // 监控采集指标
    bk_data_time_series: 'fromDataSource', // 计算平台指标
    custom_time_series: 'fromCustomRreporting', // 自定义指标
    custom_event: 'fromCustomRreporting', // 自定义事件
    bk_monitor_event: 'homeLink', // 系统事件
    log_time_series: 'formLogPlatform' // 日志平台指标
  };
  isSingleChoice = ['bk_data_time_series', 'log_time_series']; // 数据来源单选列表
  isSpecialCMDBDimension = false; // 已选指标维度包含已选维度 bk_inst_id bk_obj_id 则只能进行单选
  isSpecialCMDBDimensionPop = false; // 此次选择是否已经弹出过特殊维度tip
  uptimeCheckTaskId = -1;
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
  //  当前右侧CardList Data
  get curData(): IDataSourceItem {
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

  // 初始化
  created() {
    this.scenarioType = this.monitorType;
    this.searchObj.data = this.getSearchOptions();
    this.handleSearch = debounce(300, false, this.filterMetric);
    this.throttledScroll = throttle(300, false, this.handleScroll);
    this.dataSourceInit();
    this.cacheDataInit();
  }

  @Emit('show-change')
  handleShowChange(v) {
    return v;
  }
  @Emit('add')
  handleAdd(checkedMetric = this.checkedMetric) {
    return checkedMetric;
  }
  @Emit('scenariotype')
  handleScenarioTypeEmit() {
    return this.oldCheckedMetricTap.scenarioType;
  }

  // 真*初始化
  @Watch('isShow')
  async onIsShowChanged(newV) {
    if (newV) {
      this.scenarioType = this.monitorType;
      if (this.metricData.length <= 0) {
        this.searchObj.keyWord = [];
      }
      this.isSeeSelected = false;
      this.tag.value = '';
      this.dataSourceInit();
      if (this.metricData.length) {
        const dataSourceTypeList = Object.keys(this.dataSource).map(key => this.dataSource[key]);
        dataSourceTypeList.forEach(item => {
          if (
            this.metricData[0].data_source_label === item.dataSourceLabel &&
            this.metricData[0].data_type_label === item.dataTypeLabel
          ) {
            this.sourceType = item.sourceType;
            this.oldCheckedMetricTap.sourceType = item.sourceType;
          }
        });
      }
      this.oldCheckedMetricTap.scenarioType = this.scenarioType;
      this.isCheckedOther = false;
      this.cacheDataInit();
      this.getMonitorSource();
      this.isSpecialCMDBDimension = this.metricData.some(item => item.isSpecialCMDBDimension);
      this.isSpecialCMDBDimensionPop = false;
      this.checkedMetric = this.metricData.map(item => item);
    }
  }
  // 指标数据初始化
  dataSourceInit() {
    this.dataSource = {
      bk_monitor_time_series: {
        count: 0,
        dataSourceLabel: 'bk_monitor',
        dataTypeLabel: 'time_series',
        sourceType: 'bk_monitor_time_series',
        sourceName: this.$tc('监控采集指标'),
        list: []
      },
      bk_data_time_series: {
        count: 0,
        dataSourceLabel: 'bk_data',
        dataTypeLabel: 'time_series',
        sourceType: 'bk_data_time_series',
        sourceName: this.$tc('计算平台指标'),
        list: []
      },
      custom_time_series: {
        count: 0,
        dataSourceLabel: 'custom',
        dataTypeLabel: 'time_series',
        sourceType: 'custom_time_series',
        sourceName: this.$tc('自定义指标'),
        list: []
      },
      log_time_series: {
        count: 0,
        dataSourceLabel: 'bk_log_search',
        dataTypeLabel: 'time_series',
        sourceType: 'log_time_series',
        sourceName: this.$tc('日志平台指标'),
        list: []
      },
      bk_apm_trace_timeseries: {
        count: 0,
        dataSourceLabel: 'bk_apm',
        dataTypeLabel: 'time_series',
        sourceType: 'bk_apm_trace_timeseries',
        sourceName: 'APM',
        list: []
      }
    };
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
    this.cache[cacheKey] = { page: 1, list: [], count: 0, scrollTop: 0, tags: [], scenarioCounts: [] };
  }

  /**
   * @description: 获取指标数据
   * @param {string} dataSourceLabel
   * @param {string} dataTypeLabel
   * @param {*} staticObj
   * @param {*} needResultTableLabel
   * @return {*}
   */
  async getMonitorSource(dataSourceLabel?: string, dataTypeLabel?: string, staticObj?, needResultTableLabel = true) {
    this.loading = true;
    // // 处理外部调用(仪表盘跳转)时传进来的参数
    const staticParams = this.handleStaticParams(dataSourceLabel, dataTypeLabel, staticObj);
    const cacheKey = `${this.sourceType}_${this.scenarioType}`;
    const params = {
      ...staticParams,
      conditions: this.seachParams,
      page_size: this.pageSize,
      page: this.cache?.[cacheKey]?.page ? this.cache[cacheKey].page : 1,
      tag: this.tag.value
    };
    if (!needResultTableLabel) {
      delete params.result_table_label;
    }
    await getMetricListV2(params)
      .then(data => {
        this.scenarioCounts = data.scenario_list;
        this.tag.list = data.tag_list;
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
        if (this.tag.value === '' && this.seachParams.length === 0) {
          this.cache[cacheKey].list = this.dataSource[this.sourceType].list;
          this.cache[cacheKey].tags = data.tag_list;
          this.cache[cacheKey].scenarioCounts = data.scenario_list;
        }
        this.cache[cacheKey].count = this.dataSource[this.sourceType].count;
        this.$nextTick(() => {
          this.scrollEl = this.$el.querySelector('.metric-common-content');
          this.scrollEl?.addEventListener('scroll', this.throttledScroll);
        });
      })
      .finally(() => {
        this.loading = false;
      });
  }
  /**
   * @description: 默认传参
   * @param {string} dataSourceLabel
   * @param {string} dataTypeLabel
   * @param {*} staticObj
   * @return {*}
   */
  handleStaticParams(dataSourceLabel?: string, dataTypeLabel?: string, staticObj?): IStaticParams {
    if (staticObj) return staticObj;
    const dataSource = dataSourceLabel || this.curData.dataSourceLabel;
    return {
      bk_biz_id: this.$store.getters.bizId,
      data_source_label: Array.isArray(dataSource) ? dataSource : [dataSource],
      data_type_label: dataTypeLabel || this.curData.dataTypeLabel,
      result_table_label: this.scenarioType
    };
  }
  // 刷新按钮
  refreshMonitorSource() {
    this.searchObj.keyWord = [];
    this.tapChangeInit();
    this.cacheDataInit();
    this.getMonitorSource();
    //
  }
  /**
   * @description: 写入缓存数据
   * @param {*}
   * @return {*}
   */
  cacheDataSet() {
    const cacheKey = `${this.sourceType}_${this.scenarioType}`;
    if (
      this.cache?.[cacheKey]?.list &&
      this.cache[cacheKey].list.length <= this.cache[cacheKey].count &&
      !Boolean(this.searchObj.keyWord.length)
    ) {
      this.dataSource[this.sourceType].list = this.cache[cacheKey].list;
      this.dataSource[this.sourceType].count = this.cache[cacheKey].count;
      this.tag.list = this.cache[cacheKey].tags;
      this.scenarioCounts = this.cache[cacheKey].scenarioCounts;
      this.$nextTick(() => this.cacheScrollTop(false));
    } else {
      this.cacheDataInit(false);
      this.getMonitorSource();
    }
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
   * @description: 点击内置分类
   * @param {string} id
   * @return {*}
   */
  async handleTagClick(id: string) {
    if (this.tag.value === id) {
      this.tag.value = '';
      this.cacheDataInit(false);
    } else {
      this.tag.value = id;
    }
    this.tapChangeInit(true);
    const cacheKey = `${this.sourceType}_${this.scenarioType}`;
    this.cache[cacheKey].page = 1;
    this.getMonitorSource();
  }
  /**
   * @description: 切换监控对象
   * @param {string} scenarioType
   * @return {*}
   */
  handleLeftChange(scenarioType: string) {
    if (this.scenarioType === scenarioType) return;
    this.cacheScrollTop();
    this.scenarioType = scenarioType;
    this.searchObj.data = this.getSearchOptions();
    if (this.tag.value) {
      this.tagCacheInit();
      return;
    }
    this.tapChangeInit();
    this.handleCheckedOther();
    this.cacheDataSet();
  }
  /**
   * @description: 切换数据来源
   * @param {string} sourceType
   * @return {*}
   */
  handleTabChang(sourceType: string) {
    if (this.sourceType === sourceType) return;
    this.cacheScrollTop();
    this.sourceType = sourceType;
    this.searchObj.data = this.getSearchOptions();
    if (this.tag.value) {
      this.tagCacheInit();
      return;
    }
    this.tapChangeInit();
    this.handleCheckedOther();
    this.cacheDataSet();
  }
  // 切换类型时清除内置标签缓存数据
  tagCacheInit() {
    this.cacheDataInit();
    this.tapChangeInit();
    this.handleCheckedOther();
    this.getMonitorSource();
  }
  /**
   * @description: 重置头部标签
   * @param {*} isTag
   * @return {*}
   */
  tapChangeInit(isTag = false) {
    this.isSeeSelected = false;
    this.dataSource[this.sourceType].list = [];
    if (!isTag) {
      this.tag.value = '';
    }
  }
  /**
   * @description: 切换只看已选
   * @param {boolean} v
   * @return {*}
   */
  SeeSelectedChange(v: boolean) {
    if (v) {
      this.cacheScrollTop();
      this.oldDataSource = deepClone(this.dataSource);
      this.dataSource[this.sourceType].list = this.checkedMetric;
    } else {
      this.dataSource = deepClone(this.oldDataSource);
      this.$nextTick(() => this.cacheScrollTop(false));
    }
  }

  //  处理监控指标名列数据
  handleMetricFieldName(row) {
    const obj = {
      id: '',
      alias: ''
    };
    obj.id =
      this.sourceType === 'log_time_series'
        ? `${row.related_name}.${row.metric_field}`
        : row.result_table_id
          ? `${row.result_table_id}.${row.metric_field}`
          : row.metric_field;
    // 英文
    if (this.$store.getters.lang !== 'en') {
      obj.alias = !row.metric_field_name || row.metric_field_name === row.metric_field ? '' : row.metric_field_name;
    }
    return obj;
  }
  /**
   * @description: 选中指标
   * @param {any} item
   * @return {*}
   */
  handleCheckMertric(item: any) {
    this.popoverCancel();
    if (this.checkedMetric.length === 0 && !this.isSeeSelected) {
      this.oldCheckedMetricTap.scenarioType = this.scenarioType;
      this.oldCheckedMetricTap.sourceType = this.sourceType;
    }
    // 是否单选
    if (this.isSingleChoice.includes(this.sourceType) || !this.multiple || this.isSpecialCMDBDimension) {
      this.checkedMetric = [];
      this.checkedMetric.push(item);
    } else {
      const index = this.checkedMetric.findIndex(met => met.metric_id === item.metric_id);
      if (index > -1) {
        this.checkedMetric.splice(index, 1);
      } else {
        this.checkedMetric.length < this.maxLength && this.checkedMetric.push(item);
      }
    }
  }
  /**
   * @description: tip
   * @param {*} refDom
   * @param {*} target
   * @return {*}
   */
  popConfirmMertricUtil(refDom, target) {
    this.popoverCancel();
    this.popoverConfirmInstance = this.$bkPopover(target, {
      content: refDom,
      trigger: 'click',
      maxWidth: 270,
      extCls: 'metric-confirm-pop',
      theme: 'light',
      arrow: true,
      placement: 'top-end',
      boundary: 'window',
      sticky: true,
      interactive: true
    });
    this.popoverConfirmInstance?.show(100);
  }
  /**
   * @description: 是否已选择其他数据来源的指标
   * @param {Event} e
   * @param {*} item
   * @param {string} type
   * @return {*}
   */
  handleConfirmMertric(e: Event, item, type?: string) {
    const typeMap = {
      other: this.$refs.popoverConfirm,
      uptimeCheck: this.$refs.popoverConfirmUptimeCheck, // 如果选中服务拨测相关指标则只能单选
      CMDB: this.$refs.popoverSpecialCMDBD // 如果选中CMDB节点维度的聚合则不能多选
    };
    this.curPopoverMetric = item;
    this.popConfirmMertricUtil(typeMap[type], e.target);
  }
  confirmCheckCurMetricSpecialCMDBD() {
    this.isSpecialCMDBDimensionPop = true;
    this.confirmCheckCurMetric();
  }
  // 选中当前指标并清空已选指标
  confirmCheckCurMetric() {
    this.popoverCancel();
    this.checkedMetric = [];
    if (this.curPopoverMetric) {
      this.handleCheckMertric(this.curPopoverMetric);
      this.handleCheckedOther();
    }
  }
  // 跳转到已选指标的tap
  handleToCheckedMetric() {
    this.popoverCancel();
    this.sourceType = this.oldCheckedMetricTap.sourceType;
    this.scenarioType = this.oldCheckedMetricTap.scenarioType;
    this.tapChangeInit();
    this.cacheDataSet();
    this.isCheckedOther = false;
  }
  // 清除确认弹出
  popoverCancel() {
    if (this.popoverConfirmInstance) {
      this.popoverConfirmInstance.destroy();
      this.popoverConfirmInstance = null;
    }
  }

  /**
   * @description: 是否已选中指标
   * @param {*} checkedMetric
   * @param {*} item
   * @return {*}
   */
  handleDetermineMetric(checkedMetric, item): boolean {
    return checkedMetric.some(met => met.metric_id === item.metric_id);
  }
  /**
   * @description: 移入指标tip显示
   * @param {Event} e
   * @param {*} data
   * @return {*}
   */
  handleNameEnter(e: Event, data) {
    if (this.scenarioType === 'uptimecheck' && data.disabled) {
      this.uptimeCheckTaskId = Number(data.related_id);
    }
    this.hoverTimer && window.clearTimeout(this.hoverTimer);
    this.hoverTimer = setTimeout(() => {
      this.popoverInstance = this.$bkPopover(e.target, {
        content: this.handleGetMetricTipsContent(data),
        trigger: 'manual',
        theme: 'tippy-metric',
        arrow: true,
        placement: 'auto',
        boundary: 'window'
      });
      this.popoverInstance?.show();
    }, 1000);
  }
  // 移出指标
  handleNameLeave() {
    this.handleTipsLeave();
    this.hoverTimer && window.clearTimeout(this.hoverTimer);
  }
  // 去除指标tip
  handleTipsLeave() {
    if (this.popoverInstance) {
      this.popoverInstance.hide(0);
      this.popoverInstance.destroy();
      this.popoverInstance = null;
    }
  }

  //  跳转拨测任务
  handleToUptimcheck() {
    this.handleTipsLeave();
    this.$router.push({
      name: 'uptime-check',
      params: {
        taskId: this.uptimeCheckTaskId.toString()
      }
    });
  }

  /* eslint-disable camelcase */

  //  监听滚动加载 到底触发加载
  async handleScroll(e: any) {
    if (this.isSeeSelected) {
      return false;
    }
    const { scrollHeight, scrollTop, clientHeight } = e.target;
    const isEnd = scrollHeight - scrollTop === clientHeight && scrollTop !== 0;
    const { count: metricCount } = this.dataSource[this.sourceType];
    const cacheKey = `${this.sourceType}_${this.scenarioType}`;
    if (!(isEnd && this.cache[cacheKey].page * this.pageSize <= metricCount)) return;
    this.cache[cacheKey].page += 1;
    await this.getMonitorSource();
  }
  //
  //  根据不同的sourceType生成不同的搜索选项
  getSearchOptions(): ISearchOption[] {
    const options = [
      // 公共项
      { id: 'metric_field', name: this.$tc('指标名'), children: [] },
      { id: 'metric_field_name', name: this.$tc('指标别名'), children: [] }
    ];
    const searchObj = {
      bk_monitor_time_series: [
        // 监控采集指标
        ...options,
        { id: 'related_id', name: this.$tc('插件ID'), children: [] },
        { id: 'related_name', name: this.$tc('插件名'), children: [] },
        { id: 'result_table_id', name: this.$tc('分类ID'), children: [] },
        { id: 'result_table_name', name: this.$tc('分类名'), children: [] },
        { id: 'description', name: this.$tc('含义'), children: [] },
        { id: 'collect_config', name: this.$tc('采集配置'), children: [] }
      ],
      log_time_series: [
        // 日志平台指标
        ...options,
        { id: 'related_name', name: this.$tc('索引集'), children: [] },
        { id: 'related_id', name: this.$tc('索引集ID'), children: [] },
        { id: 'result_table_id', name: this.$tc('索引'), children: [] },
        { id: 'scenario_name', name: this.$tc('数据源类别'), children: [] },
        { id: 'storage_cluster_name', name: this.$tc('数据源名'), children: [] }
      ],
      bk_data_time_series: [
        // 计算平台指标
        ...options,
        { id: 'result_table_id', name: this.$tc('表名'), children: [] }
      ],
      custom_time_series: [
        // 自定义指标
        ...options,
        { id: 'bk_data_id', name: this.$tc('数据ID'), children: [] },
        { id: 'result_table_name', name: this.$tc('数据名'), children: [] }
      ]
    };
    return searchObj[this.sourceType];
  }

  // 当已选指标时切换监控对象或者数据来源
  handleCheckedOther() {
    if (this.checkedMetric.length !== 0) {
      const { scenarioType, sourceType } = this.oldCheckedMetricTap;
      if (this.scenarioType === scenarioType && this.sourceType === sourceType) {
        this.isCheckedOther = false;
      } else {
        this.isCheckedOther = true;
      }
    }
  }

  //  搜索事件
  filterMetric() {
    this.tapChangeInit();
    const cacheKey = `${this.sourceType}_${this.scenarioType}`;
    this.cache[cacheKey].page = 1;
    if (!this.searchObj.keyWord.length) {
      this.cacheDataInit();
    }
    this.getMonitorSource();
  }

  // 添加
  handleConfirm() {
    this.handleAdd();
    this.handleScenarioTypeEmit();
    this.handleShowChange(false);
  }
  // 取消
  handleCancel() {
    this.handleShowChange(false);
  }

  // 指标项
  getMetricComponent(item) {
    const { alias, id } = this.handleMetricFieldName(item);
    let dom = null;
    // 是否为服务拨测
    const uptimecheckreg = /uptimecheck/;
    const checkMetric = event => {
      if (this.readonly) {
        return false;
      }
      /** 多选时需要校验指标类型 */
      if (this.multiple) {
        const isUptimeCheck =
          (`${item?.result_table_id}`.match(uptimecheckreg) ||
            this.checkedMetric.some(item => `${item?.result_table_id}`.match(uptimecheckreg) !== null)) &&
          this.checkedMetric.length !== 0;
        if (this.isCheckedOther) {
          this.handleConfirmMertric(event, item, 'other');
        } else if (isUptimeCheck) {
          this.handleConfirmMertric(event, item, 'uptimeCheck');
        } else if (this.isSpecialCMDBDimension && !this.isSpecialCMDBDimensionPop) {
          this.handleConfirmMertric(event, item, 'CMDB');
        } else {
          this.handleCheckMertric(item);
        }
      } else {
        this.handleCheckMertric(item);
      }
    };
    const className = [
      'content-card',
      { 'card-active': this.handleDetermineMetric(this.checkedMetric, item) },
      { 'card-disabled': item.disabled }
    ];
    if (alias) {
      dom = (
        <div
          class={className}
          on-click={!item.disabled && checkMetric}
          on-mouseenter={event => this.handleNameEnter(event, item)}
          on-mouseleave={this.handleNameLeave}
        >
          <span class='card-text card-desc'>{alias}</span>
          <span class='card-text card-id'>{id}</span>
          <i class='bk-icon icon-check-1'></i>
        </div>
      );
    } else {
      dom = (
        <div
          class={className}
          on-click={!item.disabled && checkMetric}
          on-mouseenter={event => this.handleNameEnter(event, item)}
          on-mouseleave={this.handleNameLeave}
        >
          <span class='card-text-one card-desc'>{id}</span>
          <i class='bk-icon icon-check-1'></i>
        </div>
      );
    }
    return dom;
  }

  // 找不到相关的指标项
  getNoMetricComponent(position = 'abs') {
    let dom = null;
    const handleGoto = () => {
      handleGotoLink(this.paramsMap[this.sourceType]);
    };
    if (position === 'abs') {
      dom =
        this.curData.list.length <= 20 ? (
          <div
            class='card-help-abs'
            on-click={handleGoto}
          >
            {this.$t('找不到相关的指标项？')}
          </div>
        ) : undefined;
    } else {
      dom =
        this.curData.list.length > 20 ? (
          <div
            class='card-help'
            on-click={handleGoto}
          >
            {this.$t('找不到相关的指标项？')}
          </div>
        ) : undefined;
    }
    return dom;
  }

  render() {
    return (
      <MonitorDialog
        value={this.isShow}
        title={this.$t('选择监控指标')}
        width={960}
        zIndex={3000}
        on-change={this.handleShowChange}
      >
        <div
          class='strategy-metric-common'
          v-bkloading={{ isLoading: this.loading }}
        >
          <div class='head'>
            <bk-search-select
              ref='searchSelect'
              class='metric-search'
              v-model={this.searchObj.keyWord}
              showPopoverTagChange={false}
              popoverZindex={2600}
              data={this.searchObj.data}
              placeholder={this.$t('关键字搜索')}
              on-change={this.handleSearch}
              show-condition={false}
            ></bk-search-select>
            <bk-button
              class='metric-refresh'
              icon='icon-refresh'
              on-click={() => this.refreshMonitorSource()}
            ></bk-button>
          </div>
          <HorizontalScrollContainer
            key={String(this.tag.list?.length || 0)}
            style={{ marginTop: '8px' }}
          >
            <div class='built-in'>
              {this.tag.list.map(item => (
                <div
                  on-click={() => this.handleTagClick(item.id)}
                  class={['built-in-item', { active: this.tag.value === item.id }]}
                  key={item.id}
                >
                  {item.name}
                </div>
              ))}
            </div>
          </HorizontalScrollContainer>
          <div class='content'>
            <ul class='content-left'>
              {this.scenarioListAll.map(item => (
                <li
                  class={['left-item', { 'item-active': this.scenarioType === item.name }]}
                  key={item.name}
                  on-click={() => this.handleLeftChange(item.name)}
                >
                  <span class='left-item-name'>{item.label}</span>
                  <span class='left-item-num'>{item.count}</span>
                </li>
              ))}
            </ul>
            <div class='content-right'>
              <div class='tab-list-wrap'>
                <ul class='tab-list'>
                  {Object.keys(this.dataSource).map(key => (
                    <li
                      class={['tab-item', { 'tab-item-active': this.dataSource[key].sourceType === this.sourceType }]}
                      onClick={() => this.handleTabChang(this.dataSource[key].sourceType)}
                    >
                      <div class='tab-item-main'>
                        <span class='tab-item-text'>{this.dataSource[key].sourceName}</span>
                        <span class='tab-item-count'>{this.dataSource[key].count}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
              <div class='see-selected'>
                <bk-checkbox
                  checked={false}
                  true-value={true}
                  false-value={false}
                  v-model={this.isSeeSelected}
                  on-change={this.SeeSelectedChange}
                >
                  <div class='selected-text'>
                    {this.$t('只看已选')}
                    <span class='num'>{`(${this.checkedMetric.length})`}</span>
                  </div>
                </bk-checkbox>
              </div>
              {this.curData?.list.length ? (
                <div
                  class='metric-common-content'
                  ref='metricContent'
                >
                  {this.curData.list.map(item => this.getMetricComponent(item))}
                  {this.getNoMetricComponent('rel')}
                </div>
              ) : (
                <div class='metric-common-content'>
                  <bk-exception
                    class='exception-wrap-item right-empty'
                    type='empty'
                    scene='part'
                  ></bk-exception>
                </div>
              )}
              {this.getNoMetricComponent()}
            </div>
          </div>
          {this.getPopoverConfirmComponent()}
        </div>
        <template slot='footer'>
          {!this.readonly ? (
            <bk-button
              theme='primary'
              style='margin-right: 10px'
              disabled={this.checkedMetric && this.checkedMetric.length === 0}
              on-click={this.handleConfirm}
            >
              {this.$t('添加')}
            </bk-button>
          ) : undefined}
          <bk-button on-click={this.handleCancel}>{this.$t('取消')}</bk-button>
        </template>
      </MonitorDialog>
    );
  }

  getPopoverConfirmComponent() {
    const { sourceType, scenarioType } = this.oldCheckedMetricTap;
    const sourceName = this.dataSource[sourceType]?.sourceName;
    const scenarioName = this.scenarioListAll.find(scenario => scenarioType === scenario.name)?.label;
    return [
      // 选择不同数据来源的数据时
      <div style='display: none'>
        <div
          ref='popoverConfirm'
          class='content-text'
        >
          <span>{`${this.$t('只能同时选择同一数据来源下的指标')}。 ${this.$t('已选【{0}-{1}】指标', [
            scenarioName,
            sourceName
          ])}，`}</span>
          <span
            on-click={this.handleToCheckedMetric}
            class='text-click'
          >{`${this.$t('前往查看')};`}</span>
          <span>{`${this.$t('你也可以')}`}</span>
          <span
            on-click={this.confirmCheckCurMetric}
            class='text-click'
          >{`${this.$t('清空已选并选择当前指标')}。`}</span>
          <div
            on-click={this.popoverCancel}
            class='text-click cancel'
          >
            {this.$t('取消')}
          </div>
        </div>
      </div>,
      // 选择服务拨测相关的指标时
      <div style='display: none'>
        <div
          ref='popoverConfirmUptimeCheck'
          class='content-text'
        >
          <span>{`${this.$t('拨测相关指标只能单选')}。`}</span>
          <span
            on-click={this.confirmCheckCurMetric}
            class='text-click'
          >{`${this.$t('清空已选并选择当前指标')}。`}</span>
          <div
            on-click={this.popoverCancel}
            class='text-click cancel'
          >
            {this.$t('取消')}
          </div>
        </div>
      </div>,
      // 已选择cmdb节点维度情况时
      <div style='display: none'>
        <div
          ref='popoverSpecialCMDBD'
          class='content-text'
        >
          <span>{`${this.$t('多指标下不支持cmdb节点维度的聚合')}。`}</span>
          <span
            on-click={this.confirmCheckCurMetricSpecialCMDBD}
            class='text-click'
          >{`${this.$t('清空已选并选择当前指标')}。`}</span>
          <div
            on-click={this.popoverCancel}
            class='text-click cancel'
          >
            {this.$t('取消')}
          </div>
        </div>
      </div>,
      <div style='display: none'>
        <div
          on-mouseleave={this.handleTipsLeave}
          class='uptimecheck-tips'
          ref='uptimecheckTips'
        >
          {this.$t('该指标需设置期望返回码/期望响应信息后才可选取')}
          <span
            style={{ color: ' #3a9eff', cursor: 'pointer' }}
            class='set-uptimecheck'
            on-click={this.handleToUptimcheck}
          >
            {' '}
            {this.$t('前往设置')}{' '}
          </span>
        </div>
      </div>
    ];
  }
}
export default tsx.ofType<IStrategyMetricCommon>().convert(StrategyMetricCommon);
