<!--
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
-->
<template>
  <monitor-dialog
    class="strategy-config-metric-wrap"
    :value="isShow"
    :title="$t('指标选择器')"
    width="1080"
    @change="handleShowChange"
  >
    <div
      v-bkloading="{ isLoading: loading }"
      class="metric-set"
    >
      <!-- header 监控对象选项卡 -->
      <bk-tab
        :active.sync="scenarioType"
        type="unborder-card"
        @tab-change="handleTabChang"
      >
        <bk-tab-panel
          v-for="(panel, index) in scenarioListAll"
          v-bind="panel"
          :key="index"
          :disabled="disabledScenarioType(panel)"
        />
      </bk-tab>
      <div class="set-content">
        <!-- left 数据来源列表 -->
        <ul class="set-content-left">
          <li
            v-for="(item, index) in dataSource"
            :key="index"
            class="left-item"
            :class="{ 'item-active': item.sourceType === leftActive }"
            @click="handleChangeList(item.sourceType)"
          >
            <span class="left-item-name">{{ item.sourceName }}</span>
            <span
              class="left-item-num"
              :class="{ 'num-active': item.sourceType === leftActive }"
            >
              {{ item.count }}
            </span>
          </li>
        </ul>
        <div class="set-content-right">
          <!-- right 功能栏 -->
          <div class="right-header">
            <!-- 搜索栏 支持 键值对搜索 和 任意内容搜索 和 三段式 -->
            <div class="metric-search">
              <search-select
                :value="searchObj.keyWord"
                :data="searchObj.data"
                :placeholder="$t('关键字搜索')"
                :clearable="false"
                @change="handleSearch"
              />
            </div>
            <!-- 选定时间范围 -->
            <!-- <bk-select v-model="timeSelect.value" class="metric-select" :clearable="false" ext-popover-cls="select-class">
              <bk-option v-for="option in timeSelect.list"
                         :key="option.id"
                         :id="option.id"
                         :name="option.name">
              </bk-option>
            </bk-select> -->
            <!-- 刷新按钮 -->
            <bk-button
              icon="icon-refresh"
              @click="getMonitorSource"
            />
          </div>
          <!-- 快捷标签栏 只有当过滤字段包含"related_id"时，会出现其他标签，正常默认只有 常用 标签 -->
          <div class="right-tag">
            <div
              v-for="item in tag.list"
              :key="getRenderKey(item)"
              class="tag-box"
              :class="{ 'tag-active': tag.value === item.id }"
              @click="handleChangeTag(item.id)"
            >
              {{ item.name }}
            </div>
          </div>
          <!-- 指标卡片展示区域 -->
          <div
            v-if="curData && curData.list.length"
            class="right-content"
          >
            <div
              v-for="(item, index) in curData.list"
              :key="index"
              class="right-content-card"
              :class="{ 'card-active': handleDetermineMetric(checkedMetric, item), 'card-disable': item.disabled }"
              @click="!item.disabled && handleCheckMertric(item)"
              @mouseenter="handleNameEnter($event, item)"
              @mouseleave="handleNameLeave"
            >
              <i class="bk-icon icon-check-1" />
              <!-- 有指标别名优先展示指标别名 -->
              <template v-if="handleMetricFieldName(item).alias">
                <span class="card-text card-desc">{{ handleMetricFieldName(item).alias }}</span>
                <span class="card-text">{{ handleMetricFieldName(item).id }}</span>
              </template>
              <!-- 没有别名展示三段式 -->
              <template v-else>
                <span class="card-text-one card-desc">{{ handleMetricFieldName(item).id }}</span>
              </template>
            </div>
            <div
              v-if="curData.list.length > 18"
              class="card-help"
              @click="handleGotoLink(paramsMap[leftActive])"
            >
              {{ $t('找不到相关的指标项？') }}
            </div>
          </div>
          <!-- 空数据情况 -->
          <bk-exception
            v-else
            class="exception-wrap-item right-empty"
            type="empty"
            scene="part"
          />
          <!-- help提示 -->
          <div
            v-if="curData && curData.list.length <= 18"
            class="card-help card-help-abs"
            @click="handleGotoLink(paramsMap[leftActive])"
          >
            {{ $t('找不到相关的指标项？') }}
          </div>
        </div>
      </div>
    </div>
    <template #footer>
      <bk-button
        class="footer-btn"
        theme="primary"
        :disabled="checkedMetric && Object.keys(checkedMetric).length === 0"
        @click="handleConfirm"
      >
        {{ $t('添加') }}
      </bk-button>
      <bk-button @click="handleCancel">
        {{ $t('取消') }}
      </bk-button>
    </template>
    <div v-show="false">
      <div
        ref="uptimecheckTips"
        class="uptimecheck-tips"
        @mouseleave="handleTipsLeave"
      >
        {{ $t('该指标需设置期望返回码/期望响应信息后才可选取') }}
        <span
          style="color: #3a9eff; cursor: pointer"
          class="set-uptimecheck"
          @click="handleToUptimcheck"
        >
          {{ $t('前往设置') }}
        </span>
      </div>
    </div>
  </monitor-dialog>
</template>
<script lang="ts">
import { Component, Mixins, Prop, Watch } from 'vue-property-decorator';

import SearchSelect from '@blueking/search-select-v3/vue2';
import { getMetricList } from 'monitor-api/modules/strategies';
import MonitorDialog from 'monitor-ui/monitor-dialog/monitor-dialog.vue';
import { debounce, throttle } from 'throttle-debounce';

import documentLinkMixin from '../../../../mixins/documentLinkMixin';

import type MonitorVue from '../../../../types/index';
import type {
  IDataSource,
  IDataSourceItem,
  IMetric,
  IPage,
  ISearchObj,
  ISearchOption,
  IStaticParams,
  ITag,
  ITimeSelect,
} from '../../../../types/strategy-config/strategy-metric';

import '@blueking/search-select-v3/vue2/vue2.css';

@Component({
  name: 'strategy-config-metric-new',
  components: {
    MonitorDialog,
    SearchSelect,
  },
} as any)
export default class StrategyConfigMetricNew extends Mixins(documentLinkMixin)<MonitorVue> {
  @Prop() // 是否显示dialog
  readonly isShow: boolean;
  @Prop({ default: 0 }) //
  readonly id: number | string;
  @Prop({ default: 'application_check' }) // 传进来的监控对象
  readonly monitorType: string;
  @Prop() // 编辑状态下选择的指标data
  readonly metric: IMetric;
  @Prop() // 是否编辑
  readonly isEdit: boolean;
  @Prop() // 监控对象列表
  readonly scenarioList: any[];
  // 指标多选
  @Prop({ default: false, type: Boolean }) multiple: boolean;
  // 只允许选择单监控对象指标
  @Prop({ default: false, type: Boolean }) singleMonitorType: boolean;
  // 只允许选择当前监控对象的指标
  @Prop({ default: '', type: String }) onlyMonitorType: string;

  paramsMap = {
    bk_monitor_time_series: 'fromMonitor', // 监控采集
    log_time_series: 'formLogPlatform', // 日志采集
    bk_data_time_series: 'fromDataSource', // 数据平台
    custom_time_series: 'fromCustomRreporting', // 自定义指标
  };
  loading = false;
  scenarioType = ''; // 当前选择的监控对象
  leftActive = 'bk_monitor_time_series'; // 左侧列表数据类型sourceType值
  checkedMetric: any = []; // 选种的指标
  dataSource: IDataSource; // 左侧数据列表
  page: IPage = {
    // 各个数据来源加载的页数
    bk_monitor_time_series: 1,
    bk_data_time_series: 1,
    custom_time_series: 1,
    log_time_series: 1,
  };
  searchObj: ISearchObj = {
    // 键值对搜索数据
    keyWord: [],
    data: [],
  };
  timeSelect: ITimeSelect; // 时间范围选择
  tag: ITag = {
    // 标签数据
    value: '',
    list: [],
  };
  uptimeCheckTaskId = -1; // 跳转到拨测任务所需的ID
  popoverInstance = null; // tipsElement
  hoverTimer = null; // tips延时展示的定时器
  scrollEl = null; //
  handleSearch: Function = () => {};
  throttledScroll: Function = () => {};

  @Watch('isShow')
  async onIsShowChanged(newV) {
    if (newV) {
      this.checkedMetric = [];
      this.scenarioType = this.onlyMonitorType || this.monitorType;
      this.searchObj.keyWord = [];
      this.tag.value = '';
      Object.keys(this.page).forEach(item => (this.page[item] = 1));
      if (!this.isEdit) {
        this.getMonitorSource();
      }
      if (this.scrollEl) {
        this.scrollEl.removeEventListener('scroll', this.throttledScroll);
      }
      // this.$nextTick(() => {
      //   this.handleBindScrollEvent()
      //   // this.disabledClearSeach = false
      // })
      if (this.isEdit) {
        const temp = await this.getMetric(this.metric);
        this.checkedMetric.push(temp);
      }
    }
  }

  //  处理监控对象数据结构
  get scenarioListAll() {
    let arr = [];
    const list = JSON.parse(JSON.stringify(this.scenarioList));
    list.reverse().forEach(item => {
      const child = item.children.map(one => ({ name: one.id, label: one.name }));
      arr = [...child, ...arr];
    });
    return arr;
  }

  // 生成后台所需要的搜索参数
  get seachParams() {
    let strValue = '';
    const objValue = {};
    this.searchObj.keyWord.forEach(item => {
      if (Array.isArray(item.values)) {
        item.values.forEach(v => {
          objValue[item.id] = v.id;
        });
      } else {
        strValue += `${item.id};`;
      }
    });
    strValue = strValue ? strValue.slice(0, strValue.length - 1) : '';
    return { strValue, objValue };
  }

  //  当前右侧CardList Data
  get curData(): IDataSourceItem {
    return this.dataSource[this.leftActive];
  }

  created() {
    this.searchObj.data = this.getSearchOptions();
    this.handleSearch = debounce(300, this.filterMetric);
    this.throttledScroll = throttle(300, this.handleScroll);
    this.dataSource = {
      bk_monitor_time_series: {
        count: 0,
        dataSourceLabel: 'bk_monitor',
        dataTypeLabel: 'time_series',
        sourceType: 'bk_monitor_time_series',
        sourceName: this.$tc('监控采集'),
        list: [],
      },
      log_time_series: {
        count: 0,
        dataSourceLabel: 'bk_log_search',
        dataTypeLabel: 'time_series',
        sourceType: 'log_time_series',
        sourceName: this.$tc('日志采集'),
        list: [],
      },
      bk_data_time_series: {
        count: 0,
        dataSourceLabel: 'bk_data',
        dataTypeLabel: 'time_series',
        sourceType: 'bk_data_time_series',
        sourceName: this.$tc('计算平台'),
        list: [],
      },
      custom_time_series: {
        count: 0,
        dataSourceLabel: 'custom',
        dataTypeLabel: 'time_series',
        sourceType: 'custom_time_series',
        sourceName: this.$tc('自定义指标'),
        list: [],
      },
      bk_monitor_log: {
        count: 0,
        dataSourceLabel: 'bk_monitor',
        dataTypeLabel: 'log',
        sourceType: 'bk_monitor_log',
        sourceName: this.$tc('其他'),
        list: [],
      },
    };
    this.timeSelect = {
      value: 7,
      list: [
        { id: 1, name: this.$tc('近 1 天') },
        { id: 3, name: this.$tc('近 3 天') },
        { id: 7, name: this.$tc('近 7 天') },
        { id: 15, name: this.$tc('近 15 天') },
        { id: 30, name: this.$tc('近 30 天') },
      ],
    };
  }

  destroyed() {
    this.handleNameLeave();
  }

  getRenderKey(item) {
    return `${this.leftActive}${item.id}`;
  }

  //  确定metric
  handleDetermineMetric(checkedMetric, item) {
    return checkedMetric.some(
      met =>
        met.metric_field === item.metric_field &&
        met.result_table_id === item.result_table_id &&
        met.related_id === item.related_id &&
        met.related_name === item.related_name
    );
  }

  async getMetric(metric) {
    this.scenarioType = this.monitorType;
    if (metric.dataSourceLabel === 'bk_log_search') {
      this.leftActive = 'log_time_series';
    } else {
      this.leftActive = `${metric.dataSourceLabel}_${metric.dataTypeLabel}`;
    }
    const isSame = (source, defaultSource = this.leftActive) => defaultSource === source;
    this.searchObj.keyWord = [];
    const conditions = [
      {
        id: 'metric_field',
        name: this.$tc('指标名'),
        values: [{ id: metric.metricName, name: metric.metricName }],
      },
    ];
    if (isSame('uptimecheck', this.scenarioType)) {
      conditions.push(
        { id: 'related_id', name: this.$tc('插件ID'), values: [{ id: metric.relatedId, name: metric.relatedId }] },
        { id: 'related_name', name: this.$tc('插件名'), values: [{ id: metric.relatedName, name: metric.relatedName }] }
      );
    }
    const resultTableIdParams = {
      id: 'result_table_id',
      name: this.$tc('分类ID'),
      values: [{ id: metric.resultTableId, name: metric.resultTableId }],
    };
    if (isSame('log_time_series')) {
      resultTableIdParams.name = this.$tc('索引');
    }
    if (isSame('bk_data_time_series') || isSame('custom_time_series')) {
      resultTableIdParams.name = this.$tc('表名');
    }
    conditions.push(resultTableIdParams);
    this.searchObj.keyWord = conditions;
    await this.getMonitorSource(metric.dataSourceLabel, metric.dataTypeLabel, null, false);
    return this.curData.list.length
      ? this.curData.list.find(
          item =>
            item.metric_field === metric.metricName &&
            item.result_table_id === metric.resultTableId &&
            item.data_source_label === metric.dataSourceLabel &&
            item.data_type_label === metric.dataTypeLabel
        ) || this.curData.list[0]
      : {};
  }
  //  切换监控对象 tabCard
  handleTabChang() {
    this.dataSource[this.leftActive].list = [];
    Object.keys(this.page).forEach(item => (this.page[item] = 1));
    this.tag.value = '';
    this.getMonitorSource();
  }

  //  切换数据类型 左侧列表
  handleChangeList(sourceType) {
    this.leftActive = sourceType;
    this.dataSource[this.leftActive].list = [];
    this.tag.value = '';
    this.searchObj.data = this.getSearchOptions();
    this.getMonitorSource();
  }

  //  切换标签
  handleChangeTag(id: string) {
    this.tag.value = this.tag.value === id ? '' : id;
    this.dataSource[this.leftActive].list = [];
    Object.keys(this.page).forEach(item => (this.page[item] = 1));
    this.getMonitorSource();
  }

  //  默认传参
  handleStaticParams(dataSourceLabel?: string, dataTypeLabel?: string, staticObj?): IStaticParams {
    if (staticObj) return staticObj;
    return {
      bk_biz_id: this.$store.getters.bizId,
      data_source_label: dataSourceLabel || this.curData.dataSourceLabel,
      data_type_label: dataTypeLabel || this.curData.dataTypeLabel,
      result_table_label: this.scenarioType,
    };
  }

  //  获取指标数据
  async getMonitorSource(dataSourceLabel?: string, dataTypeLabel?: string, staticObj?, needResultTableLabel = true) {
    this.loading = true;
    // 处理外部调用(仪表盘跳转)时传进来的参数
    const staticParams = this.handleStaticParams(dataSourceLabel, dataTypeLabel, staticObj);
    const params = {
      ...staticParams,
      search_fields: {
        ...this.seachParams.objValue,
      },
      search_value: this.seachParams.strValue,
      page_size: 24,
      page: this.page[this.leftActive] ? this.page[this.leftActive] : 1,
      tag: this.tag.value,
    };
    if (!needResultTableLabel) {
      delete params.result_table_label;
    }
    await getMetricList(params)
      .then(data => {
        this.tag.list = data.tag_list;
        data.count_list.forEach(item => {
          if (this.dataSource[item.source_type]) {
            this.dataSource[item.source_type].count = item.count;
          }
        });
        if (params.page === 1) {
          this.dataSource[this.leftActive].list = data.metric_list;
        } else {
          this.dataSource[this.leftActive].list = [...this.dataSource[this.leftActive].list, ...data.metric_list];
        }
        this.$nextTick(() => {
          this.handleBindScrollEvent();
        });
      })
      .finally(() => {
        this.loading = false;
      });
  }

  //  根据不同的sourceType生成不同的搜索选项
  getSearchOptions(): ISearchOption[] {
    const options = [
      // 公共项
      { id: 'metric_field', name: this.$tc('指标名'), children: [] },
      { id: 'metric_field_name', name: this.$tc('指标别名'), children: [] },
    ];
    const searchObj = {
      bk_monitor_time_series: [
        // 监控采集
        ...options,
        { id: 'related_id', name: this.$tc('插件ID'), children: [] },
        { id: 'related_name', name: this.$tc('插件名'), children: [] },
        { id: 'result_table_id', name: this.$tc('分类ID'), children: [] },
        { id: 'result_table_name', name: this.$tc('分类名'), children: [] },
        { id: 'description', name: this.$tc('含义'), children: [] },
        { id: 'collect_config', name: this.$tc('采集配置'), children: [] },
      ],
      log_time_series: [
        // 日志采集
        ...options,
        { id: 'related_name', name: this.$tc('索引集'), children: [] },
        { id: 'related_id', name: this.$tc('索引集ID'), children: [] },
        { id: 'result_table_id', name: this.$tc('索引'), children: [] },
        { id: 'scenario_name', name: this.$tc('数据源类别'), children: [] },
        { id: 'storage_cluster_name', name: this.$tc('数据源名'), children: [] },
      ],
      bk_data_time_series: [
        // 数据平台
        ...options,
        { id: 'result_table_id', name: this.$tc('表名'), children: [] },
      ],
      custom_time_series: [
        // 自定义指标
        ...options,
        { id: 'bk_data_id', name: this.$tc('数据ID'), children: [] },
        { id: 'result_table_name', name: this.$tc('数据名'), children: [] },
      ],
    };
    return searchObj[this.leftActive];
  }

  //  搜索事件
  filterMetric(v) {
    this.searchObj.keyWord = v;
    this.dataSource[this.leftActive].list = [];
    this.checkedMetric.length = [];
    this.page[this.leftActive] = 1;
    this.getMonitorSource();
  }

  //  选择指标
  handleCheckMertric(item: any) {
    if (this.multiple) {
      const index = this.checkedMetric.findIndex(m => m.id === item.id);
      if (index > -1) {
        this.checkedMetric.splice(index, 1);
      } else {
        this.checkedMetric.length < 10 && this.checkedMetric.push(item);
      }
    } else {
      this.checkedMetric = [item];
    }
  }

  //  hover卡片显示popover
  handleNameEnter(e: Event, data) {
    this.hoverTimer && window.clearTimeout(this.hoverTimer);
    if (this.monitorType === 'uptimecheck' && data.disabled) {
      this.uptimeCheckTaskId = Number(data.related_id);
    }
    this.hoverTimer = setTimeout(() => {
      this.popoverInstance = this.$bkPopover(e.target, {
        content: this.handleTips(data),
        trigger: 'manual',
        theme: 'tippy-metric',
        arrow: true,
        placement: 'auto',
        boundary: 'window',
      });
      this.popoverInstance.show();
    }, 1000);
  }

  //  划出卡片
  handleNameLeave() {
    this.handleTipsLeave();
    this.hoverTimer && window.clearTimeout(this.hoverTimer);
  }

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
        taskId: this.uptimeCheckTaskId.toString(),
      },
    });
  }

  //  卡片内容展示设置 根据不同的数据来源展示不同的数据
  handleTips(data) {
    if (this.monitorType === 'uptimecheck' && data.default_condition) {
      const response = data.default_condition.find(item => item.key === 'response_code' || item.key === 'message');
      if (response && !response.value) {
        return this.$refs.uptimecheckTips;
      }
    }
    const options = [
      // 公共展示项
      {
        label: this.$t('指标名'),
        val: data.metric_field,
      },
      {
        val: data.metric_field_name,
        label: this.$t('指标别名'),
      },
    ];
    const elList = {
      bk_monitor_time_series: [
        // 监控采集
        ...options,
        { val: data.related_id, label: this.$t('插件ID') },
        { val: data.related_name, label: this.$t('插件名') },
        { val: data.result_table_id, label: this.$t('分类ID') },
        { val: data.result_table_name, label: this.$t('分类名') },
        { val: data.description, label: this.$t('含义') },
      ],
      log_time_series: [
        // 日志采集
        ...options,
        { val: data.related_name, label: this.$t('索引集') },
        { val: data.result_table_id, label: this.$t('索引') },
        { val: data.extend_fields.scenario_name, label: this.$t('数据源类别') },
        { val: data.extend_fields.storage_cluster_name, label: this.$t('数据源名') },
      ],
      bk_data_time_series: [
        // 数据平台
        ...options,
        { val: data.result_table_id, label: this.$t('表名') },
      ],
      custom_time_series: [
        // 自定义指标
        ...options,
        { val: data.extend_fields.bk_data_id, label: this.$t('数据ID') },
        { val: data.result_table_name, label: this.$t('数据名') },
      ],
    };
    // 拨测指标融合后不需要显示插件id插件名
    const relatedId = data.related_id;
    const resultTableLabel = data.result_table_label;
    if (!relatedId && resultTableLabel === 'uptimecheck') {
      const list = elList.bk_monitor_time_series;
      elList.bk_monitor_time_series = list.filter(
        item => item.label !== this.$t('插件ID') && item.label !== this.$t('插件名')
      );
    }
    let content = '';
    const curElList = elList[this.leftActive];
    if (this.leftActive === 'log_time_series') {
      content = `<div class="item">${data.related_name}.${data.metric_field}</div>\n`;
    } else {
      content = `<div class="item">${data.result_table_id}.${data.metric_field}</div>\n`;
    }
    if (data.collect_config) {
      const collectorConfig = data.collect_config
        .split(';')
        .map(item => `<div>${item}</div>`)
        .join('');
      curElList.splice(0, 0, { label: this.$t('采集配置'), val: collectorConfig });
    }

    if (data.metric_field === data.metric_field_name) {
      curElList.forEach((item, index) => {
        if (item.label === this.$t('指标别名')) {
          curElList.splice(index, 1);
        }
      });
    }
    curElList.forEach(item => {
      content += `<div class="item"><div>${item.label}：${item.val || '--'}</div></div>\n`;
    });
    return content;
  }

  handleBindScrollEvent() {
    this.scrollEl = this.$el.querySelector('.right-content');
    this.scrollEl?.addEventListener('scroll', this.throttledScroll);
  }

  //  监听滚动加载 到底触发加载
  async handleScroll(e: any) {
    const { scrollHeight } = e.target;
    const { scrollTop } = e.target;
    const { clientHeight } = e.target;
    const isEnd = scrollHeight - scrollTop === clientHeight;
    const { count: metricCount, sourceType } = this.dataSource[this.leftActive];
    if (isEnd && this.page[sourceType] * 24 <= metricCount) {
      this.page[sourceType] += 1;
      await this.getMonitorSource();
    }
  }

  //  处理监控指标名列数据
  handleMetricFieldName(row) {
    const obj = {
      id: '',
      alias: '',
    };
    obj.id =
      this.leftActive === 'log_time_series'
        ? `${row.related_name}.${row.metric_field}`
        : `${row.result_table_id}.${row.metric_field}`;
    // 英文
    if (this.$store.getters.lang !== 'en') {
      obj.alias = !row.metric_field_name || row.metric_field_name === row.metric_field ? '' : row.metric_field_name;
    }
    return obj;
  }

  resetCurrentTypePage() {
    if (this.page[this.leftActive]) {
      this.page[this.leftActive] = 1;
    }
  }

  handleShowChange(v) {
    this.$emit('show-change', v);
  }

  //  确认btn
  handleConfirm() {
    const temp = this.multiple ? this.checkedMetric : this.checkedMetric[0];
    this.$emit('on-add', temp, this.leftActive);
    this.$emit('update:monitorType', this.scenarioType);
    this.$emit('hide-dialog', false);
  }

  //  取消btn
  handleCancel() {
    this.resetCurrentTypePage();
    this.$emit('hide-dialog', false);
  }

  disabledScenarioType(item) {
    if (this.onlyMonitorType) {
      return item.name !== this.onlyMonitorType;
    }
    if (this.singleMonitorType) {
      return item.name !== this.scenarioType && !!this.checkedMetric.length;
    }
    return false;
  }
}
</script>
<style lang="scss" scoped>
.strategy-config-metric-wrap {
  :deep(.monitor-dialog-close) {
    z-index: 3000;
  }

  :deep(.monitor-dialog-header) {
    display: none;
  }

  :deep(.monitor-dialog-footer) {
    justify-content: flex-end;
  }

  :deep(.metric-set) {
    .bk-tab-section {
      padding: 8px;
    }

    .bk-tab-label-wrapper {
      width: 1080px;
      padding-left: 11px;
      margin: -20px 0 0 -24px;
      border-bottom: 1px solid #dcdee5;
    }

    .set-content {
      display: flex;
      min-height: 468px;

      &-left {
        display: flex;
        flex: 0 0 192px;
        flex-direction: column;
        background: #f5f6fa;
        border-radius: 2px 0 0 0;

        .left-item {
          display: flex;
          flex: 0 0 42px;
          align-items: center;
          cursor: pointer;

          &.item-active {
            color: #fff;
            background: #3a84ff;
          }

          &-name {
            flex: 1;
            max-width: 110px;
            margin-left: 17px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }

          &-num {
            display: flex;
            align-items: center;
            justify-content: center;
            min-width: 24px;
            height: 16px;
            padding: 0 5px;
            margin-right: 16px;
            margin-left: auto;
            font-size: 12px;
            color: #fff;
            background: #dcdee5;
            border-radius: 16px;

            &.num-active {
              color: #3a84ff;
              background: #fff;
            }
          }
        }
      }

      &-right {
        flex: 1;
        margin-left: 20px;
        overflow-x: hidden;

        .right-header {
          display: flex;
          margin-bottom: 16px;

          .metric-search {
            flex-grow: 1;
            margin-right: 8px;
          }

          .metric-select {
            width: 120px;
            margin-right: 8px;
          }

          .bk-button.no-slot .left-icon {
            top: 0;
            font-size: 16px;
            color: #c4c6cc;
          }
        }

        .right-tag {
          display: flex;
          flex-wrap: wrap;
          margin-bottom: 1px;

          .tag-box {
            height: 24px;
            padding: 0 12px;
            margin: 0 6px 6px 0;
            line-height: 24px;
            background: #f0f1f5;
            border: 1px solid #f0f1f5;
            border-radius: 2px;

            &:hover {
              color: #3a84ff;
              cursor: pointer;
              background: #e1ecff;
              border-color: #a3c5fd;
            }
          }

          .tag-active {
            color: #3a84ff;
            background: #e1ecff;
            border-color: #a3c5fd;
          }
        }

        .right-content {
          display: flex;
          flex-wrap: wrap;
          max-height: 380px;
          overflow-y: scroll;

          &-card {
            display: flex;
            flex-direction: column;
            justify-content: center;
            width: 266px;
            height: 52px;
            padding: 0 20px 0 14px;
            margin: 0 8px 8px 0;
            line-height: 20px;
            color: #979ba5;
            background: #f5f6fa;
            border: 1px solid #f5f6fa;
            border-radius: 2px;

            &:nth-child(3n) {
              margin-right: 0;
            }

            &:hover {
              cursor: pointer;
              background: #fff;
              border: 1px solid #3a84ff;
              box-shadow: 0 1px 2px 0 rgba(0, 51, 136, 0.1);
            }

            .card-text {
              overflow: hidden;
              text-overflow: ellipsis;
              white-space: nowrap;
            }

            .card-text-one {
              /* stylelint-disable-next-line value-no-vendor-prefix */
              display: -webkit-box;
              overflow: hidden;
              text-overflow: ellipsis;
              word-break: break-all;

              /* stylelint-disable-next-line property-no-vendor-prefix */
              -webkit-box-orient: vertical;
              -webkit-line-clamp: 2;
            }

            .card-desc {
              font-weight: bold;
              color: #63656e;
            }

            .icon-check-1 {
              position: absolute;
              top: 0;
              right: -1px;
              font-size: 14px;
              font-weight: bold;
              color: #fff;
            }
          }

          .card-active {
            position: relative;
            background: #fff;
            border: 1px solid #3a84ff;
            box-shadow: 0 1px 2px 0 rgba(0, 51, 136, 0.1);

            &::before {
              position: absolute;
              top: 0px;
              right: 0;
              content: '';
              border-width: 24px;
              border-top: #3a84ff solid;
              border-left: transparent solid;
            }
          }

          .card-disable {
            color: #dedee5;
            cursor: not-allowed;
            background: #fafbfd;

            .card-desc {
              color: #dedee5;
            }
          }
        }

        .right-empty {
          flex: 1;
          height: 260px;
          padding-top: 48px;
        }

        .card-help {
          min-width: 816px;
          height: 24px;
          line-height: 24px;
          text-align: center;
          background: #f0f1f5;
          border-radius: 2px;

          &:hover {
            color: #3a84ff;
            cursor: pointer;
            background: #e1ecff;
          }
        }

        .card-help-abs {
          position: absolute;
          bottom: 8px;
          min-width: 820px;
        }
      }
    }
  }
}

.footer-btn {
  margin-right: 10px;
}
</style>
