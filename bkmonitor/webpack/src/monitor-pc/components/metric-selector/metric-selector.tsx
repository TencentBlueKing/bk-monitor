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

import { Component, Emit, Mixins, Prop, Ref, Watch } from 'vue-property-decorator';
import * as tsx from 'vue-tsx-support';

import { queryAsyncTaskResult } from '../../../monitor-api/modules/commons';
import { addCustomMetric } from '../../../monitor-api/modules/custom_report';
import { getMetricListV2, updateMetricListByBiz } from '../../../monitor-api/modules/strategies';
import { LANGUAGE_COOKIE_KEY } from '../../../monitor-common/utils/constant';
import { copyText, Debounce, deepClone, docCookies } from '../../../monitor-common/utils/utils';
import { xssFilter } from '../../../monitor-common/utils/xss';
import { handleGotoLink } from '../../common/constant';
import { isEn } from '../../i18n/i18n';
import metricTipsContentMixin from '../../mixins/metricTipsContentMixin';
import HorizontalScrollContainer from '../../pages/strategy-config/strategy-config-set-new/components/horizontal-scroll-container';
import { MetricDetail, MetricType } from '../../pages/strategy-config/strategy-config-set-new/typings';
import EmptyStatus from '../empty-status/empty-status';
import { EmptyStatusOperationType, EmptyStatusType } from '../empty-status/types';

import CheckedboxList from './checkedbox-list';
import MetricPopover from './metric-popover';
import { CheckedboxListVlaue, MetricSelectorEvents, MetricSelectorProps } from './typings';

import './metric-selector.scss';

const { i18n } = window;

// const placeholderSearch = {
//   [MetricType.common]: window.i18n.tc('指标'),
//   [MetricType.event]: window.i18n.tc('事件'),
//   [MetricType.log]: window.i18n.tc('日志关键字'),
//   [MetricType.alert]: window.i18n.tc('策略')
// };

const promqlParams = [
  ['custom', 'time_series'],
  ['bk_monitor', 'time_series']
];

/**
 * 指标选择器
 */
@Component
class MetricSelector extends Mixins(metricTipsContentMixin) {
  /** 指标选择器的类型 */
  @Prop({ type: String, default: MetricType.TimeSeries }) type: MetricType;
  /** 触发对象id */
  @Prop({ type: String }) targetId: string;
  /** 显隐状态 */
  @Prop({ type: Boolean, default: false }) show: boolean;
  /* 指标唯一id */
  @Prop({ type: String }) metricId: string;
  /* 指标key metricid 为空的清空以此为标识 */
  @Prop({ type: String, default: '' }) metricKey: string;
  /** 监控对象列表 */
  @Prop({ type: Array, default: () => [] }) scenarioList: any;
  /* 自定义参数 */
  @Prop({ type: Boolean, default: false }) isPromql: boolean;
  /* 默认选择的监控对象 */
  @Prop({ type: String, default: '' }) defaultScenario: string;
  @Ref() metricScrollWrap: HTMLElement;

  loading = false;
  nextPageLoading = false;

  /** 指标列表 */
  metricList: MetricDetail[] = new Array(50).fill(new MetricDetail());

  /** 当前定位到的item */
  currentIndex = 0;
  /** 鼠标hover的索引 */
  hoverIndex = null;
  /** 鼠标是否hover item */
  isHoverItem = false;

  /** 分页数据 */
  pagination = {
    page: 1,
    pageSize: 20,
    total: 0
  };

  search = '';

  /* tags */
  tag = {
    list: [],
    value: '',
    activeItem: null
  };

  lang = docCookies.getItem(LANGUAGE_COOKIE_KEY);

  hoverTimer = null; // tip
  popoverInstance = null;
  popoverConfirmInstance = null; // 选择指标时确认tip
  curPopoverMetric = null; // 弹出确认tip时选中的指标
  refreshLoading = false; // 刷新功能loading
  timer = null;
  emptyStatusType: EmptyStatusType = 'empty';

  localScenarioList = [];
  dataSourceList = [];

  /** 侧栏选中数据 */
  checkededValue: CheckedboxListVlaue = {};

  /** 指标类型映射 */
  dataTypeLabelMap: Record<MetricType, string> = {
    [MetricType.TimeSeries]: 'time_series',
    [MetricType.EVENT]: 'event',
    [MetricType.LOG]: 'log',
    [MetricType.ALERT]: 'alert'
  };

  /** 采集来源数据 */
  dataSourceCheckedList = {
    // 监控指标
    [MetricType.TimeSeries]: [
      { id: 'bk_monitor', name: i18n.t('监控采集指标'), count: 0 },
      { id: 'bk_data', name: i18n.t('计算平台指标'), count: 0 },
      { id: 'custom', name: i18n.t('自定义指标'), count: 0 },
      { id: 'bk_log_search', name: i18n.t('日志平台指标'), count: 0 },
      { id: 'bk_apm', name: 'APM', count: 0 }
    ],
    // 事件数据
    [MetricType.EVENT]: [
      { id: 'bk_monitor', name: i18n.t('系统事件'), count: 0 },
      { id: 'custom', name: i18n.t('自定义事件'), count: 0 },
      { id: 'bk_fta', name: i18n.t('第三方告警'), count: 0 }
    ],
    // 日志数据
    [MetricType.LOG]: [
      { id: 'bk_monitor', name: i18n.t('监控采集'), count: 0 },
      { id: 'bk_log_search', name: i18n.t('日志平台'), count: 0 },
      { id: 'bk_apm', name: i18n.t('应用监控'), count: 0 }
    ],
    // 关联告警
    [MetricType.ALERT]: [
      { id: 'bk_monitor', name: i18n.t('告警策略'), count: 0 },
      { id: 'bk_fta', name: i18n.t('第三方告警'), count: 0 }
    ]
  };

  /* 是否点击了刷新并且执行了初始化操作 无需清空搜索 */
  isRefreshSuccess = false;

  /** 是否在滚动中 */
  isScrolling = false;

  /** 滚动计时器 */
  scrollEndTimer;

  /* 当前选中的指标 */
  selectedMetric: MetricDetail = null;

  /** 当前的指标类型 */
  get currentDataTypeLabel() {
    return this.dataTypeLabelMap[this.type];
  }
  /** 侧栏列表数据 */
  get checkedboxList() {
    const scenarioCountMap = {};
    this.localScenarioList.forEach(item => {
      scenarioCountMap[item.id] = item.count;
    });
    return [
      {
        id: 'data_source_label',
        name: i18n.tc(this.type === MetricType.ALERT ? '告警类型' : '数据来源'),
        children:
          this.dataSourceCheckedList[this.type]?.map(item => {
            // eslint-disable-next-line max-len
            const target = this.dataSourceList.find(
              set => set.data_type_label === this.currentDataTypeLabel && set.data_source_label === item.id
            );
            item.count = (() => {
              if (this.isPromql) {
                return promqlParams.map(p => p[0]).includes(item.id) ? target?.count || 0 : 0;
              }
              return target?.count || 0;
            })();
            return item;
          }) || []
      },
      {
        id: 'result_table_label',
        name: i18n.tc('监控对象'),
        children: this.scenarioList.map(item => {
          this.$set(item, 'count', scenarioCountMap[item.id] || 0);
          return item;
        })
      }
    ];
  }

  /** 搜索条件 */
  get searchConditions() {
    return [
      {
        key: 'query',
        value: this.search.trim()
      }
    ];
  }

  /** 已加载全部数据了 */
  get isLoadAll() {
    const { page, pageSize, total } = this.pagination;
    return page * pageSize >= total;
  }

  beforeDestroy() {
    clearTimeout(this.timer);
  }

  @Watch('show')
  onShowChange(val: boolean) {
    if (val) {
      this.initData();
      this.getMetricList();
      document.addEventListener('keydown', this.handleSelectItem);
      setTimeout(() => {
        this.$refs.searchInput.focus();
      }, 0);
    } else {
      document.removeEventListener('keydown', this.handleSelectItem);
    }
  }

  @Emit('showChange')
  handleShowChange(val: boolean) {
    this.handleMetricNameLeave();
    return val;
  }

  initData() {
    if (!!this.defaultScenario) {
      this.checkededValue = {
        result_table_label: [this.defaultScenario]
      };
    } else {
      this.checkededValue = {};
    }
    this.metricList = [];
    if (!this.isRefreshSuccess) {
      this.search = '';
    }
    this.currentIndex = 0;
    this.pagination.page = 1;
    this.pagination.total = 0;
    this.tag.value = '';
    this.isRefreshSuccess = false;
  }

  @Debounce(300)
  handleSearch() {
    if (this.emptyStatusType !== '500') this.emptyStatusType = this.search ? 'search-empty' : 'empty';
    this.pagination.page = 1;
    this.currentIndex = 0;
    this.isHoverItem = false;
    this.metricScrollWrap.scrollTo({ top: 0 });
    this.getMetricList();
  }

  /**
   * 处理接口请求的参数
   * @returns
   */
  handleMetricParams(): Record<string, any> {
    const { page, pageSize } = this.pagination;
    const params = {
      conditions: this.searchConditions,
      data_source: this.isPromql
        ? promqlParams
        : this.checkededValue.data_source_label?.map?.(item => [item, this.currentDataTypeLabel]),
      data_type_label: this.isPromql ? undefined : this.currentDataTypeLabel,
      result_table_label: this.checkededValue.result_table_label,
      tag: this.tag.value,
      page,
      page_size: pageSize
    };
    return params;
  }

  /**
   * 获取指标数据
   * @param page 分页
   */
  getMetricList(page = 1) {
    page === 1 && (this.currentIndex = !!this.search ? 0 : null);
    const { pageSize, total } = this.pagination;
    if (page > 1 && (page - 1) * pageSize >= total) return;
    if (page === 1) {
      this.loading = true;
    } else {
      this.nextPageLoading = true;
    }
    const params = this.handleMetricParams();
    params.page = page;
    getMetricListV2(params)
      .then(({ metric_list = [], tag_list = [], scenario_list = [], data_source_list = [], count = 0 }) => {
        const metricList = metric_list.map(item => new MetricDetail(item));
        this.metricList = page === 1 ? metricList : [...this.metricList, ...metricList];
        this.getSelectedMetric();
        page > 1 && (this.pagination.page += 1);
        this.pagination.total = count;
        if (this.tag.value) {
          if (tag_list.findIndex(item => item.id === this.tag.value) < 0) {
            const activeItem = this.tag.list.find(item => item.id === this.tag.value);
            if (activeItem) this.tag.activeItem = deepClone(activeItem);
          } else {
            this.tag.activeItem = null;
          }
        }
        this.tag.list = tag_list;
        this.localScenarioList = scenario_list;
        this.dataSourceList = data_source_list;
      })
      .finally(() => {
        this.loading = false;
        this.nextPageLoading = false;
      });
  }

  /* 关键字高亮 */
  highLightContent(search: string, content: string) {
    if (!search) {
      return content;
    }
    /* 搜索不区分大小写 */
    const searchValue = search.trim().toLowerCase();
    const contentValue = content.toLowerCase();
    /* 获取分隔下标 */
    const indexRanges: number[][] = [];
    const contentValueArr = contentValue.split(searchValue);
    let tempIndex = 0;
    contentValueArr.forEach(item => {
      const temp = tempIndex + item.length;
      indexRanges.push([tempIndex, temp]);
      tempIndex = temp + search.length;
    });
    return indexRanges.map((range: number[], index: number) => {
      if (index !== indexRanges.length - 1) {
        return [
          <span>{content.slice(range[0], range[1])}</span>,
          <span class='light'>{content.slice(range[1], indexRanges[index + 1][0])}</span>
        ];
      }
      return <span>{content.slice(range[0], range[1])}</span>;
    });
  }

  /* 复制指标名 */
  handleCopyMetricMame(metric: MetricDetail) {
    const copyStr = metric.promql_metric;
    let hasErr = false;
    copyText(copyStr, errMsg => {
      this.$bkMessage({
        message: errMsg,
        theme: 'error'
      });
      hasErr = !!errMsg;
    });
    if (!hasErr) this.$bkMessage({ theme: 'success', message: this.$t('复制成功') });
  }

  /**
   * @description: 移入指标tip显示
   * @param {Event} e
   * @param {*} data
   * @return {*}
   */
  handleMetricNameEnter(e: Event, item: MetricDetail) {
    const target = Array.from(e.target.childNodes).find(c => c.className === 'tip-dom');
    this.hoverTimer && window.clearTimeout(this.hoverTimer);
    this.hoverTimer = setTimeout(() => {
      this.popoverInstance = this.$bkPopover(target, {
        content: this.handleGetMetricTipsContent(item),
        trigger: 'manual',
        theme: 'tippy-metric',
        arrow: true,
        placement: 'right',
        boundary: 'window',
        allowHTML: true
      });
      this.popoverInstance?.show();
    }, 1000);
  }
  // 移出指标
  handleMetricNameLeave() {
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

  /**
   * 滚动加载下一页
   * @param evt
   */
  handleScrollContent(evt) {
    this.isScrolling = true;
    clearTimeout(this.scrollEndTimer);
    // 间隔100ms说明滚动已停止
    this.scrollEndTimer = setTimeout(() => {
      this.isScrolling = false;
    }, 100);

    const el = evt.target;
    const { scrollHeight, scrollTop, clientHeight } = el;
    if (Math.ceil(scrollTop) + clientHeight >= scrollHeight) {
      this.getMetricList(this.pagination.page + 1);
    }
  }

  /**
   * 上下键选择指标
   * @param val
   * @param evt
   */
  handleSelectItem(evt: KeyboardEvent) {
    const { key } = evt;
    const leng = this.metricList.length;
    // 当前未选择任何内容按了回车键时，会导致汇聚类别的异常变更，因此加上非空判断
    if (key === 'Enter' && !!leng && this.metricList[this.currentIndex])
      this.handleSelectMetric(this.metricList[this.currentIndex]);
    if (!['ArrowUp', 'ArrowDown'].includes(key)) return;
    evt.preventDefault();
    if (this.isHoverItem) {
      this.currentIndex = this.hoverIndex;
      this.isHoverItem = false;
    }
    if (this.currentIndex === null) {
      this.currentIndex = 0;
      return;
    }
    if (key === 'ArrowUp') {
      if (this.currentIndex === 0) {
        if (this.isLoadAll) {
          this.metricScrollWrap.scrollTo({ top: this.metricScrollWrap.scrollHeight });
          this.currentIndex = leng - 1;
          return;
        }
        this.currentIndex = leng - 3;
        const { height } = this.getTargetItem(this.currentIndex);
        const wrapRect = this.metricScrollWrap.getBoundingClientRect();
        const { height: wrapHeight } = wrapRect;
        this.metricScrollWrap.scrollTo({ top: height * this.currentIndex - (wrapHeight - height * 2) });
        return;
      }
      this.currentIndex -= 1;
    } else if (key === 'ArrowDown') {
      if (this.currentIndex === leng - 1) {
        this.metricScrollWrap.scrollTo({ top: this.metricScrollWrap.scrollHeight });
        if (this.isLoadAll) {
          this.metricScrollWrap.scrollTo({ top: 0 });
          this.currentIndex = 0;
        }
        return;
      }
      this.currentIndex += 1;
    }
    // const item = this.metricList[this.currentIndex];
    // const metricKey = `_metric_id_${item.metric_field}_${this.currentIndex}`.replace(/\./g, '_');
    const wrapRect = this.metricScrollWrap.getBoundingClientRect();
    const { height: wrapHeight, y: wrapY } = wrapRect;
    // const target = this.metricScrollWrap.querySelector(`#${metricKey}`);
    const rect = this.getTargetItem(this.currentIndex);
    const { height, y } = rect;
    const { scrollTop } = this.metricScrollWrap;
    if (y >= wrapHeight + wrapY - height) {
      /** 向下滚动 */
      const val = height - (wrapY + wrapHeight - y);
      this.metricScrollWrap.scrollTo({ top: scrollTop + val });
    } else if (y <= wrapY) {
      /** 向上滚动 */
      const val = wrapY - y;
      this.metricScrollWrap.scrollTo({ top: scrollTop - val });
    }
  }

  /** 获取目标item的rect */
  getTargetItem(index = 0): DOMRect {
    const item = this.metricList[index];
    const metricKey = `_metric_id_${item.metric_field}_${index}`.replace(/\./g, '_');
    const target = this.metricScrollWrap.querySelector(`#${metricKey}`);
    const rect = target.getBoundingClientRect();
    return rect;
  }

  /** 更新鼠标的hover状态 */
  handleMousemove() {
    this.isHoverItem = true;
  }

  /** 更新hover的索引 */
  handleHoverItem(index: number) {
    this.hoverIndex = index;
  }

  /** 刷新功能 */
  async handleRefreshClick() {
    if (this.refreshLoading) return;
    this.refreshLoading = true;

    const polling = (params, cb) => {
      queryAsyncTaskResult(params)
        .then(data => {
          if (!data.is_completed) {
            this.timer = setTimeout(() => {
              polling(params, cb);
              clearTimeout(this.timer);
            }, 1000);
          }
          cb(data);
        })
        .catch(err => {
          const result = {
            is_completed: true,
            state: 'FAILURE',
            data: err.data,
            message: err.message
          };
          cb(result);
        });
    };

    updateMetricListByBiz()
      .then(res => {
        polling({ task_id: res }, data => {
          const { state } = data;
          if (state === 'SUCCESS') {
            this.isRefreshSuccess = true;
            this.onShowChange(true);
            this.refreshLoading = false;
            return;
          }
          if (state === 'FAILURE') {
            this.refreshLoading = false;
            this.$bkMessage({
              message: data.message,
              theme: 'error'
            });
          }
        });
      })
      .catch(() => {
        this.refreshLoading = false;
      });
  }

  @Emit('selected')
  handleSelectMetric(metric: MetricDetail) {
    this.handleShowChange(false);
    return {
      ...metric,
      dimensions: metric.rawDimensions || [],
      key: this.metricKey
    };
  }

  /** 侧栏选中 */
  handleCheckedboxListChange(data: CheckedboxListVlaue) {
    this.checkededValue = data;
    this.pagination.page = 1;
    this.currentIndex = 0;
    this.getMetricList();
    this.metricScrollWrap.scrollTo({ top: 0 });
  }

  /* 选中tag */
  handleTagClick(id: string) {
    if (this.tag.value === id) {
      this.tag.value = '';
      this.tag.activeItem = null;
    } else {
      this.tag.value = id;
    }
    this.pagination.page = 1;
    this.metricScrollWrap.scrollTo({ top: 0 });
    this.getMetricList();
  }

  /* 跳转到文档 */
  handleToDoc() {
    handleGotoLink('fromMonitor');
  }

  /** 指标提示模板 */
  getMetricTipsTpl(data) {
    return `
    <div class="metric-tips-wrap">
      ${data.reduce((total, item) => `${total}<div>${xssFilter(item.label)}：${xssFilter(item.value)}</div>`, '')}
    </div>
    `;
  }
  /* event  */
  metricItemEvent(item: MetricDetail) {
    const data = [
      {
        label: this.$tc('事件名称'),
        value: item.metric_field_name
      },
      {
        label: this.$tc('数据ID'),
        value: item.metric_field
      },
      {
        label: this.$tc('数据名称'),
        value: item.metric_field_name
      }
    ];
    return (
      <div
        class='metric-item-event'
        v-bk-tooltips={{
          delay: [1000, 0],
          placement: 'right',
          boundary: 'window',
          disabled: this.isScrolling,
          content: this.getMetricTipsTpl(data),
          allowHTML: true
        }}
      >
        <span>{item.metric_field_name}</span>
      </div>
    );
  }
  /* log */
  metricItemLog(item: MetricDetail) {
    const data =
      item.data_source_label === 'bk_apm'
        ? [
            {
              label: this.$tc('应用名称'),
              value: item.metric_field_name
            },
            {
              label: this.$tc('结果表'),
              value: item.result_table_id
            }
          ]
        : [
            {
              label: this.$tc('索引集'),
              value: item.index_set_name
            },
            {
              label: this.$tc('索引'),
              value: item.index_set_id
            },
            {
              label: this.$tc('数据源'),
              value: item.data_source_label
            }
          ];
    return (
      <div
        class='metric-item-log'
        v-bk-tooltips={{
          delay: [1000, 0],
          placement: 'right',
          boundary: 'window',
          disabled: this.isScrolling,
          content: this.getMetricTipsTpl(data),
          allowHTML: true
        }}
      >
        <div class='log-name'>{item.metric_field_name}</div>
        <div class='log-desc'>{item.result_table_id}</div>
      </div>
    );
  }
  /* alert */
  metricAlert(item: MetricDetail) {
    return (
      <div class='metric-item-alert'>
        <span class='alert-name'>{item.metric_field_name}</span>
        {item.metric_field && <span class='alert-id'>（#{item.metric_field}）</span>}
      </div>
    );
  }
  /* common */
  metricItemCommon(item: MetricDetail) {
    const obj = {
      id: item.readable_name,
      alias: ''
    };
    // 英文
    if (this.lang !== 'en') {
      obj.alias = !item.metric_field_name || item.metric_field_name === item.metric_field ? '' : item.metric_field_name;
    }
    const dataSourceLabel =
      this.dataSourceCheckedList[MetricType.TimeSeries].find(d => d.id === item.data_source_label)?.name || '--';
    return (
      <div
        class='metric-item-common'
        on-mouseenter={event => this.handleMetricNameEnter(event, item)}
        on-mouseleave={this.handleMetricNameLeave}
      >
        <div class='top'>
          <span class='title'>{this.highLightContent(this.search, item.readable_name)}</span>
          <span class='subtitle'>{this.highLightContent(this.search, obj.alias)}</span>
        </div>
        <div class='bottom'>{`${item.result_table_label_name} / ${dataSourceLabel}${
          item.related_name ? ` / ${item.related_name}` : ''
        }`}</div>
        <div class='operate'>
          <span
            class='icon-monitor icon-mc-copy'
            v-bk-tooltips={{
              content: window.i18n.t('复制指标名'),
              placements: ['top']
            }}
            onClick={e => {
              e.stopPropagation();
              this.handleCopyMetricMame(item);
            }}
          ></span>
          {/* <span class="icon-monitor icon-fenxiang"
            v-bk-tooltips={{
              content: window.i18n.t('完整查看'),
              placements: ['top']
            }}
          ></span> */}
        </div>
        <div class='tip-dom'></div>
      </div>
    );
  }

  metricItem(item: MetricDetail) {
    switch (this.type) {
      case MetricType.TimeSeries:
        return this.metricItemCommon(item);
      case MetricType.EVENT:
        return this.metricItemEvent(item);
      case MetricType.LOG:
        return this.metricItemLog(item);
      case MetricType.ALERT:
        return this.metricAlert(item);
      default:
        return null;
    }
  }

  handleEmptyOperation(type: EmptyStatusOperationType | 'create-custom-metric') {
    if (type === 'refresh') {
      this.getMetricList();
      return;
    }
    if (type === 'create-custom-metric') {
      const [resultTableId, metricField] = this.search.split('.');
      if (!resultTableId || !metricField || !/^[_a-zA-Z][a-zA-Z0-9_]*$/.test(metricField)) {
        this.$bkMessage({
          theme: 'error',
          message: this.$t('格式错误'),
          delay: 2000
        });
        return;
      }

      addCustomMetric({
        result_table_id: resultTableId,
        metric_field: metricField
      }).then(res => {
        this.handleSelectMetric(res[0]);
      });
      return;
    }
  }

  /**
   * @description 获取当前选中的指标
   */
  async getSelectedMetric() {
    if (!this.metricId || this.type !== MetricType.TimeSeries) return;
    let selectedMetric = null;
    this.metricList.forEach(item => {
      if (item.metric_id === this.metricId) {
        selectedMetric = new MetricDetail(item);
      }
    });
    const delIndex = this.metricList.findIndex(item => item.metric_id === this.metricId);
    if (delIndex >= 0) {
      this.metricList.splice(delIndex, 1);
    }
    if (!selectedMetric) {
      const params = {
        ...this.handleMetricParams(),
        conditions: [
          {
            key: 'metric_id',
            value: this.metricId
          }
        ],
        page: 1,
        tag: '',
        result_table_label: [],
        data_source: undefined
      };
      const data = await getMetricListV2(params).catch(() => ({
        metric_list: []
      }));
      data?.metric_list?.forEach(item => {
        if (item.metric_id === this.metricId) {
          selectedMetric = new MetricDetail(item);
        }
      });
    }
    this.selectedMetric = selectedMetric;
  }

  render() {
    return (
      <MetricPopover
        show={this.show}
        targetId={this.targetId}
        onShowChange={this.handleShowChange}
        width={this.type === MetricType.TimeSeries ? 718 : 558}
      >
        <div class='metric-selector-main'>
          <div class={['metric-selector-header', { 'no-border': this.type === MetricType.TimeSeries }]}>
            <bk-input
              ref='searchInput'
              v-model={this.search}
              placeholder={this.$t('搜索')}
              rightIcon={'bk-icon icon-search'}
              onInput={this.handleSearch}
            ></bk-input>
            <bk-button
              class='refresh-btn'
              text
              icon={this.refreshLoading ? 'loading' : 'refresh'}
              disabled={this.refreshLoading}
              onClick={this.handleRefreshClick}
            ></bk-button>
          </div>
          <div
            class='metric-selector-content-wrap'
            v-bkloading={{ isLoading: this.loading }}
          >
            {this.type === MetricType.TimeSeries ? (
              <div class='metric-selector-tags'>
                <HorizontalScrollContainer key={String(this.tag.list?.length || 0)}>
                  <div class='built-in'>
                    {(this.tag.activeItem ? [this.tag.activeItem, ...this.tag.list] : this.tag.list).map(item => (
                      <div
                        class={['built-in-item', { active: this.tag.value === item.id }]}
                        key={item.id}
                        on-click={() => this.handleTagClick(item.id)}
                      >
                        {item.name}
                      </div>
                    ))}
                  </div>
                </HorizontalScrollContainer>
              </div>
            ) : undefined}
            <div class={['metric-selector-content', this.type, { 'has-tag': this.type === MetricType.TimeSeries }]}>
              <div
                class='content-main'
                ref='metricScrollWrap'
                onScroll={this.handleScrollContent}
                onMousemove={this.handleMousemove}
              >
                {!!this.selectedMetric && (
                  <div
                    class={[
                      'metric-item',
                      'pin-top-top',
                      {
                        'common-type': this.type === MetricType.TimeSeries
                      }
                    ]}
                  >
                    <div class='selected-label'>
                      <div class='blue-bg'>
                        {!isEn ? (
                          <span class='text'>{this.$t('已选')}</span>
                        ) : (
                          <span class='icon-monitor icon-mc-check-small'></span>
                        )}
                      </div>
                    </div>
                    {this.metricItem(this.selectedMetric)}
                  </div>
                )}
                {this.metricList.length ? (
                  [
                    this.metricList.map((item, index) => (
                      <div
                        class={[
                          'metric-item',
                          {
                            selected: this.currentIndex === index && !this.isHoverItem,
                            checked: this.metricId === item.metric_id,
                            'common-type': this.type === MetricType.TimeSeries
                          }
                        ]}
                        id={`_metric_id_${item.metric_field}_${index}`.replace(/\./g, '_')}
                        onClick={() => this.handleSelectMetric(item)}
                        onMouseenter={() => this.handleHoverItem(index)}
                      >
                        {this.metricItem(item)}
                      </div>
                    )),
                    <div class='metric-next-page-tips'>
                      {this.nextPageLoading && <span class='loading-icon'></span>}
                      <span class='loading-text'>{this.$tc(this.isLoadAll ? '已加载全部数据' : '加载中...')}</span>
                    </div>
                  ]
                ) : (
                  <EmptyStatus
                    type={this.emptyStatusType}
                    onOperation={this.handleEmptyOperation}
                  >
                    {this.emptyStatusType === 'search-empty' && (
                      <div class='search-empty-msg'>
                        <p class='tip-text'>{this.$t('你可以将该搜索内容直接自定义为指标选项')}</p>
                        <bk-button
                          text
                          title='primary'
                          class='create-custom-metric'
                          onClick={() => this.handleEmptyOperation('create-custom-metric')}
                        >
                          {this.$t('生成自定义指标')}
                        </bk-button>
                      </div>
                    )}
                  </EmptyStatus>
                )}
              </div>
              <div class='content-aside'>
                <CheckedboxList
                  value={this.checkededValue}
                  list={this.checkedboxList}
                  onChange={this.handleCheckedboxListChange}
                />
              </div>
            </div>
          </div>
        </div>
      </MetricPopover>
    );
  }
}

export default tsx.ofType<MetricSelectorProps, MetricSelectorEvents>().convert(MetricSelector);
