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
  <bk-dialog
    :title="mericType === 'event' ? $t('选择事件') : $t('选择监控指标')"
    :value="isShow"
    :ok-text="$t('添加')"
    :width="950"
    :mask-close="false"
    header-position="left"
    @after-leave="handleAfterLeave"
    @cancel="handleCancel"
    @confirm="handleConfirm"
  >
    <div
      class="strategy-config-metric"
      v-bkloading="{ isLoading: loading }"
    >
      <bk-tab
        :active.sync="scenarioType"
        type="unborder-card"
        @tab-change="handleTabChang"
      >
        <bk-tab-panel
          v-for="(panel, index) in scenarioListAll"
          v-bind="panel"
          :key="index"
        />
      </bk-tab>
      <bk-search-select
        :show-popover-tag-change="false"
        ref="searchSelect"
        :popover-zindex="2600"
        class="metric-search"
        @change="handleSearch"
        :data="searchObj.data"
        v-model="searchObj.keyWord"
        :placeholder="$t('搜索')"
      />
      <div class="metric-content">
        <ul class="metric-content-left">
          <template v-for="(item, index) in monitorSource[scenarioType]">
            <li
              v-if="
                (item.data_type_label === 'event' && mericType === 'event') ||
                  (item.data_type_label !== 'event' && item.data_type_label !== 'log' && mericType !== 'event')
              "
              class="left-item"
              :key="index"
              :class="{ 'item-active': item.source_type === left.active }"
              @click="handleSelectSource(item.source_type)"
            >
              <span class="left-item-name">{{ item.source_name }}</span>
              <span
                class="left-item-num"
                :class="{ 'num-active': item.source_type === left.active }"
              >{{
                item.count
              }}</span>
            </li>
          </template>
        </ul>
        <div class="metric-content-right">
          <bk-table
            ref="metricTable"
            :class="{ 'hidden-header': mericType === 'time_series' }"
            :key="`${left.active}${scenarioType}${isShow}`"
            :data="right.data"
            :empty-text="$t('无数据')"
            max-height="400"
            :row-class-name="getRowClassName"
            @row-click="handleRadioChange"
          >
            <template>
              <bk-table-column
                :width="item.type === 'radio' ? 52 : ''"
                v-for="(item, index) in right.columns"
                :key="index"
                :label="item.label"
              >
                <template slot-scope="scope">
                  <bk-radio
                    v-if="item.type === 'radio'"
                    :disabled="scope.row.disabled"
                    :value="scope.row.select"
                    name="metric"
                    @change="handleRadioChange(scope.row)"
                  />
                  <span
                    class="col-name"
                    v-if="item.type === 'related_id'"
                    @mouseenter="handleNameEnter($event, scope.row)"
                    @mouseleave="handleNameLeave($event, scope.row)"
                  >
                    {{ scope.row.related_id }}
                  </span>
                  <span
                    class="col-name"
                    v-if="item.type === 'result_table_id'"
                    @mouseenter="handleNameEnter($event, scope.row)"
                    @mouseleave="handleNameLeave($event, scope.row)"
                  >
                    {{ scope.row.result_table_id }}
                  </span>
                  <span
                    v-if="item.type === 'result_table_name'"
                    @mouseenter="handleNameEnter($event, scope.row)"
                    @mouseleave="handleNameLeave($event, scope.row)"
                  >
                    {{ scope.row.result_table_name }}
                  </span>
                  <span
                    v-if="item.type === 'related_name'"
                    @mouseenter="handleNameEnter($event, scope.row)"
                    @mouseleave="handleNameLeave($event, scope.row)"
                  >
                    {{ scope.row.related_name }}
                  </span>
                  <span
                    v-if="item.type === 'metric_field'"
                    style="cursor: pointer"
                    @mouseenter="handleNameEnter($event, scope.row)"
                    @mouseleave="handleNameLeave($event, scope.row)"
                  >
                    {{ scope.row.metric_field }}
                  </span>
                  <span
                    v-if="item.type === 'metric_field_name'"
                    style="cursor: pointer"
                    @mouseenter="handleNameEnter($event, scope.row)"
                    @mouseleave="handleNameLeave($event, scope.row)"
                  >
                    <template v-if="mericType === 'time_series'">
                      <template v-if="handleMetricFieldName(scope.row).alias">
                        {{ handleMetricFieldName(scope.row).alias
                        }}<span class="result-table-id">( {{ handleMetricFieldName(scope.row).id }} )</span>
                      </template>
                      <template v-else>
                        {{ handleMetricFieldName(scope.row).id }}
                      </template>
                    </template>
                    <template v-else>
                      {{ scope.row.metric_field_name }}
                    </template>
                  </span>
                </template>
              </bk-table-column>
            </template>
            <template #append>
              <div
                v-show="right.scrollLoading"
                class="footer-loading"
              >
                <img src="../../../../static/images/svg/spinner.svg"  alt=''> {{ $t('正加载更多内容…') }}
              </div>
            </template>
          </bk-table>
        </div>
      </div>
    </div>
    <template #footer>
      <bk-button
        theme="primary"
        :disabled="!right.value"
        @click="handleConfirm"
      > {{ $t('添加') }} </bk-button>
      <bk-button @click="handleCancel">
        {{ $t('取消') }}
      </bk-button>
    </template>
    <div v-show="false">
      <div
        @mouseleave="handleTipsLeave"
        class="uptimecheck-tips"
        ref="uptimecheckTips"
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
  </bk-dialog>
</template>
<script>
import { createNamespacedHelpers } from 'vuex';
import { debounce, throttle } from 'throttle-debounce';

import { getMetricList } from '../../../../../monitor-api/modules/strategies';

const { mapGetters } = createNamespacedHelpers('strategy-config');

const PAGE = {
  bk_monitor_time_series: 1,
  bk_data_time_series: 1,
  custom_event: 1,
  custom_time_series: 1,
  bk_monitor_event: 1,
  log_time_series: 1
};
export default {
  name: 'StrategyConfigMetric',
  props: {
    isShow: Boolean,
    id: {
      type: [String, Number],
      default: 0
    },
    monitorType: {
      type: String,
      default: 'service_module'
    },
    metric: Object,
    isEdit: Boolean,
    // 新增编辑策略区分事件及普通的指标选择
    mericType: {
      type: String,
      validator(v) {
        return ['event', 'time_series'].includes(v);
      },
      required: true
    }
  },
  data() {
    return {
      lang: this.$store.getters.lang,
      loading: true,
      requestCount: 0, // 编辑拨测指标时，对后台数据再次过滤，得到唯一数据，requestCount变量识别是否是第一次
      searchObj: {
        keyWord: [],
        data: []
      },
      left: {
        active: this.mericType === 'event' ? 'bk_monitor_event' : 'bk_monitor_time_series'
      },
      monitorSource: {},
      metricList: {},
      right: {
        data: [],
        columns: [],
        scrollLoading: false,
        page: {},
        value: null
      },
      handleSearch: () => {},
      throttledScroll: () => {},
      scrollEl: null,
      popoverInstance: null,
      popoverData: null,
      hoverTimer: null,
      uptimeCheckTaskId: null,
      disabledClearSeach: true,
      scenarioType: ''
    };
  },
  computed: {
    ...mapGetters(['scenarioList']),
    seachParams() {
      let strValue = '';
      const objValue = {};
      // 生成后台所需要的搜索参数
      this.searchObj.keyWord.forEach((item) => {
        if (Array.isArray(item.values)) {
          item.values.forEach((v) => {
            objValue[item.id] = v.id;
          });
        } else {
          strValue += `${item.id};`;
        }
      });
      strValue = strValue ? strValue.slice(0, strValue.length - 1) : '';
      return { strValue, objValue };
    },
    COLUMNS() {
      return {
        bk_monitor_time_series: [
          { label: '', type: 'radio' },
          { label: this.$t('指标名'), type: 'metric_field_name' },
          { label: this.$t('指标分类'), type: 'result_table_name' },
          { label: this.$t('插件名'), type: 'related_id' }
        ],
        bk_data_time_series: [
          { label: '', type: 'radio' },
          { label: this.$t('表名'), type: 'result_table_name' },
          { label: this.$t('指标名'), type: 'metric_field_name' }
        ],
        custom_event: [
          { label: '', type: 'radio' },
          { label: this.$t('事件名称'), type: 'metric_field_name' },
          { label: this.$t('数据ID'), type: 'result_table_id' },
          { label: this.$t('数据名称'), type: 'result_table_name' }
        ],
        custom_time_series: [
          { label: '', type: 'radio' },
          { label: this.$t('事件名称'), type: 'metric_field_name' },
          { label: this.$t('特性ID') },
          { label: this.$t('英文名') }
        ],
        bk_monitor_event: [
          { label: '', type: 'radio' },
          { label: this.$t('事件名称'), type: 'metric_field_name' }
        ],
        log_time_series: [
          { label: '', type: 'radio' },
          { label: this.$t('指标名'), type: 'metric_field_name' },
          { label: this.$t('索引'), type: 'result_table_name' },
          { label: this.$t('索引集'), type: 'related_name' }
        ]
      };
    },
    scenarioListAll() {
      let arr = [];
      const list = JSON.parse(JSON.stringify(this.scenarioList));
      list.reverse().forEach((item) => {
        const child = item.children.map(one => ({ name: one.id, label: one.name }));
        arr = [...child, ...arr];
      });
      return arr;
    }
  },
  watch: {
    isShow(v) {
      if (v) {
        this.loading = true;
        this.scenarioType = this.monitorType;
        this.requestCount = 1;
        for (const key in this.metricList[this.scenarioType]) {
          this.metricList[this.scenarioType][key] = null;
        }
        if (this.scrollEl) {
          this.scrollEl.removeEventListener('scroll', this.throttledScroll);
        }
        this.$nextTick(() => {
          this.getMonitorSource(this.scenarioType, this.left.active);
          this.handleBindScrollEvent();
          // this.disabledClearSeach = true
        });
      } else {
        this.searchObj.keyWord = [];
        this.right.value = null;
      }
    },
    metric(v) {
      if (!v) {
        this.metricList[this.scenarioType][this.left.active] = [];
      }
    },
    scenarioType(v) {
      this.left.active = this.mericType === 'event' ? 'bk_monitor_event' : 'bk_monitor_time_series';
      if (v === 'uptimecheck') {
        this.COLUMNS.bk_monitor_time_series = [
          { label: '', type: 'radio' },
          { label: this.$t('指标名'), type: 'metric_field_name' },
          { label: this.$t('指标分类'), type: 'result_table_name' },
          { label: this.$t('任务名'), type: 'related_name' }
        ];
      } else {
        this.COLUMNS.bk_monitor_time_series = [
          { label: '', type: 'radio' },
          { label: this.$t('指标名'), type: 'metric_field_name' },
          { label: this.$t('指标分类'), type: 'result_table_name' },
          { label: this.$t('插件ID'), type: 'related_id' }
        ];
      }
      if (!this.disabledClearSeach) {
        this.searchObj.keyWord = [];
      }
      this.handleScenarioList();
    },
    /**
     *  @description
     *  { String } sourceKey 数据源键值
     */
    isEdit(v) {
      if (v) {
        const sourceKey = `${this.metric.dataSourceLabel}|${this.metric.dataTypeLabel}`;
        this.left.active = this.getEditSourceType(sourceKey);
        const isSame = (source, defaultSource = this.left.active) => defaultSource === source;
        this.searchObj.keyWord = [];
        const conditions = [
          {
            id: 'metric_field',
            name: isSame('custom_event') ? '事件ID' : this.$t('指标名'),
            values: [{ id: this.metric.metricName, name: this.metric.metricName }]
          }
        ];
        if (isSame('uptimecheck', this.scenarioType) && !isSame('custom_event') && !isSame('log_time_series')) {
          conditions.push(
            {
              id: 'task_id',
              name: this.$t('任务ID'),
              values: [{ id: this.metric.relatedId, name: this.metric.relatedId }]
            },
            {
              id: 'task_name',
              name: this.$t('任务名'),
              values: [{ id: this.metric.relatedName, name: this.metric.relatedName }]
            }
          );
        }
        if (!isSame('bk_monitor_event') && !isSame('log_time_series')) {
          conditions.push({
            id: 'result_table_id',
            name: isSame('custom_event') ? this.$t('数据ID') : this.$t('表名'),
            values: [{ id: this.metric.resultTableId, name: this.metric.resultTableId }]
          });
        } else if (isSame('log_time_series')) {
          conditions.push({
            id: 'related_id',
            name: this.$t('索引集'),
            values: [{ id: this.metric.relatedId, name: this.metric.relatedId }]
          });
        }
        this.searchObj.keyWord = conditions;
      }
    },
    mericType() {
      this.left.active = this.mericType === 'event' ? 'bk_monitor_event' : 'bk_monitor_time_series';
    }
  },
  created() {
    this.initOperations();
    this.handleSearch = debounce(300, this.filterMetric);
    this.throttledScroll = throttle(300, this.handleScroll);
  },
  mounted() {
    this.handleBindScrollEvent();
  },
  activated() {
    /**
     * 指标选择器组件第一次渲染时不会触发activated
     */
    this.initOperations();
  },
  beforeDestroy() {
    this.popoverInstance?.detory();
    this.scrollEl.removeEventListener('scroll', this.throttledScroll);
  },
  methods: {
    // 清理缓存的搜索条件
    clearSearchKeyWord() {
      this.searchObj.keyWord = [];
    },
    //  切换监控对象 tabCard
    async handleTabChang() {
      this.loading = true;
      // change事件优先于scenarioType watch函数
      await this.getMonitorSource(
        this.scenarioType,
        this.mericType === 'event' ? 'bk_monitor_event' : 'bk_monitor_time_series'
      );
      this.loading = false;
    },
    initOperations() {
      this.left.active = this.mericType === 'event' ? 'bk_monitor_event' : 'bk_monitor_time_series';
      this.handleScenarioList();
      this.handleCollectorConfig();
      this.searchObj.data = this.getSearchOptions(this.left.active);
    },
    /**
     * 根据不同的sourceType生成不同的搜索选项
     * @param {String} sourceType
     */
    getSearchOptions(sourceType) {
      const options = [
        { id: 'plugin_id', name: this.$t('插件ID'), children: [] },
        { id: 'plugin_name', name: this.$t('插件名'), children: [] },
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
        bk_monitor_event: [...options],
        custom_time_series: [...options],
        log_time_series: [...options, { id: 'releated_id', name: this.$t('索引集'), children: [] }],
        custom_event: [
          { id: 'result_table_name', name: this.$t('数据名称'), children: [] },
          { id: 'metric_field_name', name: this.$t('事件名称'), children: [] },
          { id: 'result_table_id', name: this.$t('数据ID'), children: [] },
          { id: 'metric_field', name: this.$t('事件ID'), children: [] }
        ]
      };
      const searchList = searchObj[sourceType];
      if (sourceType === 'custom_event') {
        return searchList;
      }
      if (sourceType === 'log_time_series') {
        searchList.find(item => item.id === 'result_table_name').name = this.$t('索引');
      }
      if (this.scenarioType === 'uptimecheck') {
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
      return searchList;
    },
    handleCancel() {
      this.resetCurrentTypePage();
      this.$emit('hide-dialog', false);
    },
    handleConfirm() {
      this.$emit('on-add', this.right.value, this.left.active);
      this.resetCurrentTypePage();
      this.$emit('update:monitorType', this.scenarioType);
      this.$emit('hide-dialog', false);
    },
    handleCollectorConfig() {
      if (this.$route.params.strategyName) {
        this.searchObj.keyWord = [];
        const { strategyName } = this.$route.params;
        this.searchObj.keyWord.push({
          id: 'collect_config',
          name: this.$t('采集配置'),
          values: [
            {
              id: strategyName,
              name: strategyName
            }
          ]
        });
        // this.disabledClearSeach = true
      }
    },
    handleAfterLeave() {
      if (this.$refs.searchSelect?.popperMenuInstance) {
        this.$refs.searchSelect.popperMenuInstance.destroy(true);
      }
      this.resetCurrentTypePage();
      // dialog bug需手动销毁popperMenuInstance
      if (this.$refs.searchSelect.popperMenuInstance) {
        this.$refs.searchSelect.popperMenuInstance = null;
      }
      this.$emit('hide-dialog', false);
    },
    handleScenarioList() {
      this.scenarioList.forEach((item) => {
        item.children.forEach((source) => {
          this.monitorSource[source.id] = [];
          this.metricList[source.id] = {};
          this.right.page[source.id] = { ...PAGE };
        });
      });
    },
    handleNameEnter(e, data) {
      this.hoverTimer && window.clearTimeout(this.hoverTimer);
      if (this.popoverInstance) {
        this.popoverInstance.hide(0);
        this.popoverInstance.destroy();
        this.popoverInstance = null;
      }
      const options = {
        content: this.handleTips(data),
        trigger: 'manual',
        theme: 'tippy-metric',
        interactive: true,
        arrow: true,
        placement: 'right',
        maxWidth: 200,
        followCursor: false,
        flip: false
      };
      if (this.scenarioType === 'uptimecheck' && data.disabled) {
        this.uptimeCheckTaskId = Number(data.related_id);
      }
      this.hoverTimer = setTimeout(() => {
        this.popoverInstance = this.$bkPopover(e.target, options);
        this.popoverInstance.show();
      }, 1000);
    },
    handleNameLeave() {
      this.hoverTimer && window.clearTimeout(this.hoverTimer);
    },
    handleTipsLeave() {
      if (this.popoverInstance) {
        this.popoverInstance.hide(0);
        this.popoverInstance.destroy();
        this.popoverInstance = null;
      }
    },
    handleToUptimcheck() {
      this.handleTipsLeave();
      this.$router.push({
        name: 'uptime-check',
        params: {
          taskId: this.uptimeCheckTaskId
        }
      });
    },
    handleTips(data) {
      if (this.scenarioType === 'uptimecheck' && data.default_condition) {
        const response = data.default_condition.find(item => item.key === 'response_code' || item.key === 'message');
        if (response && !response.value) {
          return this.$refs.uptimecheckTips;
        }
      }
      let elList = [
        { label: `${this.$t('英文名')}:`, val: data.metric_field },
        { label: `${this.$t('含义')}:`, val: data.description },
        { label: `${this.$t('插件ID')}:`, val: data.related_name },
        { label: `${this.$t('分类')}:`, val: data.result_table_label }
      ];
      let content = '';
      if (data.collect_config) {
        const collectorConfig = data.collect_config
          .split(';')
          .map(item => `<div>${item}</div>`)
          .join('');
        elList.splice(0, 0, { label: this.$t('采集配置'), val: collectorConfig });
      }
      if (this.left.active === 'log_time_series') {
        elList = [
          { label: `${this.$t('数据源')}:`, val: data.extend_fields.scenario_name },
          { label: `${this.$t('存储集群')}:`, val: data.extend_fields.storage_cluster_id }
        ];
      }
      elList.forEach((item) => {
        content += `<div class="item"><div>${item.label}</div>${item.val}</div>\n`;
      });
      return content;
    },
    handleRadioChange(data) {
      if (data.disabled) return;
      const tableData = this.right.data;
      const isUptimeCheck = this.scenarioType === 'uptimecheck';
      const dataKey = isUptimeCheck
        ? `${data.metric_field}-${data.result_table_id}-${data.related_id}`
        : `${data.metric_field}-${data.result_table_id}`;
      tableData.forEach((item) => {
        const itemKey = isUptimeCheck
          ? `${item.metric_field}-${item.result_table_id}-${item.related_id}`
          : `${item.metric_field}-${item.result_table_id}`;
        if (itemKey === dataKey) {
          data.select = true;
          this.right.value = data;
        } else {
          item.select = false;
        }
      });
    },
    /**
     * 处理添加监控指标要现实的表格数据列
     * @param {Array} columns
     */
    handleTableHeader(columns) {
      const typeMap = ['radio', 'metric_field_name'];
      return columns.filter(item => typeMap.includes(item.type));
    },
    /**
     * 获取sourceType下的数据源
     * @param {String} type
     */
    async handleSelectSource(type) {
      this.scrollEl.removeEventListener('scroll', this.throttledScroll);
      this.left.active = type;
      this.searchObj.data = this.getSearchOptions(this.left.active);
      if (this.metricList[this.scenarioType][type] && this.monitorSource[this.scenarioType].length) {
        this.right.columns =          this.mericType === 'time_series' ? this.handleTableHeader(this.COLUMNS[type]) : this.COLUMNS[type];
        this.right.data = this.metricList[this.scenarioType][type];
      } else {
        this.loading = true;
        await this.getMonitorSource(this.scenarioType, this.left.active);
      }
      this.right.value = this.right.data.find(item => item.select) || null;
      this.$nextTick(() => {
        this.handleBindScrollEvent();
      });
    },
    async handleScroll(e) {
      const { scrollHeight } = e.target;
      const { scrollTop } = e.target;
      const { clientHeight } = e.target;
      const isEnd = scrollHeight - scrollTop === clientHeight;
      const source = this.monitorSource[this.scenarioType].find(item => item.source_type === this.left.active) || {
        count: 0
      };
      const metricCount = source.count;
      if (
        isEnd
        && !this.right.scrollLoading
        && this.right.page[this.scenarioType][this.left.active] * 10 <= metricCount
      ) {
        this.right.page[this.scenarioType][this.left.active] += 1;
        this.right.scrollLoading = true;
        await this.getMonitorSource(this.scenarioType, this.left.active);
        this.right.scrollLoading = false;
      }
    },
    /**
     * 生成左侧列表和右侧表头
     */
    handleSourceMetric(data, page, scenarioType, sourceType) {
      this.monitorSource[scenarioType] = data.count_list || [];
      this.handleSetMetric(data || [], page, scenarioType, sourceType);
      this.right.columns =        this.mericType === 'time_series' ? this.handleTableHeader(this.COLUMNS[sourceType]) : this.COLUMNS[sourceType];
      this.right.data = this.metricList[scenarioType][sourceType];
      this.$nextTick(() => {
        this.$refs.metricTable.doLayout();
      });
    },
    handleSetMetric(data, page, scenarioType, sourceType) {
      let alreadySelected = false;
      const metricList = data.metric_list.map((item) => {
        item.name = item.metric_field_name;
        item.select = false;
        // 匹配到则不再进行选中设置
        if (this.isEdit && !alreadySelected) {
          this.handleEditSelect(item);
          alreadySelected = item.select;
          this.right.value = item;
        }
        return item;
      });
      const arr = this.metricList[scenarioType][sourceType];
      if (Array.isArray(arr)) {
        arr.push(...metricList);
      } else {
        this.metricList[scenarioType][sourceType] = metricList;
      }
    },
    handleEditSelect(item) {
      const isUptimeCheck = this.scenarioType === 'uptimecheck';
      const isBaseAlarm = this.left.active === 'bk_monitor_event';
      const filterKey = isBaseAlarm ? `${this.metric.name}` : `${this.metric.name}|${this.metric.resultTableId}`;
      if (isUptimeCheck) {
        const str = `${item.metric_field_name}|${item.result_table_id}|${item.related_name}`;
        item.select = str === `${filterKey}|${this.metric.relatedName}`;
      } else if (isBaseAlarm) {
        item.select = `${item.metric_field_name}` === filterKey;
      } else {
        item.select = `${item.metric_field_name}|${item.result_table_id}` === filterKey;
      }
    },
    handleBindScrollEvent() {
      this.scrollEl = this.$refs.metricTable.$el.querySelector('.bk-table-body-wrapper');
      this.scrollEl.addEventListener('scroll', this.throttledScroll);
    },
    handleStaticParams(staticParams) {
      if (staticParams) return staticParams;
      const source = this.monitorSource[this.scenarioType].find(item => item.source_type === this.left.active) || {};
      return {
        bk_biz_id: this.$store.getters.bizId,
        data_source_label:
          this.isEdit && this.requestCount === 1
            ? this.metric.dataSourceLabel
            : source.data_source_label || 'bk_monitor',
        data_type_label:
          this.isEdit && this.requestCount === 1
            ? this.metric.dataTypeLabel
            : source.data_type_label || (this.mericType === 'event' ? 'event' : 'time_series'),
        result_table_label: this.scenarioType,
        page_size: 10
      };
    },
    filterMetric() {
      for (const key in this.metricList[this.scenarioType]) {
        this.metricList[this.scenarioType][key] = null;
      }
      this.right.data = [];
      this.right.value = null;
      this.loading = true;
      this.right.page[this.scenarioType][this.left.active] = 1;
      this.loading = true;
      this.getMonitorSource(this.scenarioType, this.left.active);
    },
    getMonitorSource(scenarioType, sourceType, staticObj) {
      // 处理外部调用(仪表盘跳转)时传进来的参数
      const staticParams = this.handleStaticParams(staticObj);
      const params = {
        ...staticParams,
        search_fields: {
          ...this.seachParams.objValue
        },
        page: this.right.page[scenarioType] ? this.right.page[scenarioType][sourceType] : 1,
        search_value: this.seachParams.strValue
      };
      params.task_id && (params.task_id = `${params.task_id}`);
      return getMetricList(params)
        .then((data) => {
          // const newSourceType = `${staticParams.data_source_label}_${staticParams.data_type_label}`
          if (this.isEdit && scenarioType === 'uptimecheck' && this.requestCount === 1) {
            data.metric_list = data.metric_list.filter((item) => {
              const str = `${item.related_id}|${item.metric_field}`;
              const res = str === `${this.metric.relatedId}|${this.metric.metricName}`;
              return res;
            });
            const source = data.count_list.find(item => item.source_type === sourceType);
            if (source) {
              source.count = 1;
            }
          }
          this.requestCount += 1;
          this.handleSourceMetric(data, params.page, scenarioType, sourceType);
          return Promise.resolve(data);
        })
        .finally(() => {
          this.loading = false;
        });
    },
    getRowClassName({ row }) {
      return row.disabled ? 'disabled' : 'normal';
    },
    getEditSourceType(key) {
      const types = {
        'bk_monitor|time_series': 'bk_monitor_time_series',
        'bk_monitor|event': 'bk_monitor_event',
        'bk_data|time_series': 'bk_data_time_series',
        'custom|event': 'custom_event',
        'custom|time_series': 'custom_time_series',
        'bk_log_search|time_series': 'log_time_series'
      };
      return types[key];
    },
    resetCurrentTypePage() {
      if (this.right.page[this.scenarioType]) {
        this.right.page[this.scenarioType][this.left.active] = 1;
      }
    },
    /**
     * 处理监控指标名列数据
     * @param {Object} row
     */
    handleMetricFieldName(row) {
      const obj = {
        id: '',
        alias: ''
      };
      // 英文
      if (this.lang === 'en') {
        obj.id = `${row.result_table_id}.${row.metric_field}`;
      } else {
        // 中文
        obj.id = `${row.result_table_id}.${row.metric_field}`;
        obj.alias = !row.metric_field_name || row.metric_field_name === row.metric_field ? '' : row.metric_field_name;
      }
      return obj;
    }
  }
};
</script>
<style lang="scss" scoped>
@import '../../../../theme/index.scss';

.strategy-config-metric {
  :deep(.bk-tab-section) {
    padding: 8px;
  }

  .metric-search {
    margin-top: -8px;
    margin-bottom: 10px;
  }

  .metric-content {
    display: flex;
    min-height: 400px;

    &-left {
      display: flex;
      flex: 0 0 185px;
      flex-direction: column;
      font-size: 14px;
      background-image: linear-gradient(180deg, #dcdee5 1px, rgba(0, 0, 0, 0) 1px, rgba(0, 0, 0, 0) 100%),
        linear-gradient(90deg, #dcdee5 1px, rgba(0, 0, 0, 0) 1px, rgba(0, 0, 0, 0) 100%),
        linear-gradient(-90deg, #dcdee5 1px, rgba(0, 0, 0, 0) 1px, rgba(0, 0, 0, 0) 100%);
      background-size: 100% 100%;
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
          background: #c4c6cc;
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
      max-width: 717px;
      background-image: linear-gradient(180deg, #dcdee5 1px, rgba(0, 0, 0, 0) 1px, rgba(0, 0, 0, 0) 100%),
        linear-gradient(-90deg, #dcdee5 1px, rgba(0, 0, 0, 0) 1px, rgba(0, 0, 0, 0) 100%);
      background-size: 100% 100%;
      border-radius: 0 2px 0 0;

      :deep(.bk-table) {
        border-left: 0;

        .disabled {
          color: #c4c6cc;
          background: #fafbfd;
        }

        .normal {
          color: #63656e;
          background: #fff;
        }

        &::before {
          width: 0;
        }
      }

      .col-name {
        cursor: pointer;
      }

      .footer-loading {
        z-index: 100;
        display: flex;
        align-items: center;
        justify-content: center;
        height: 32px;
        padding-left: 22px;
        color: #979ba5;
        background: #ebedf0;
        border-radius: 2px;

        img {
          width: 14px;
          margin-right: 6px;
        }
      }

      .result-table-id {
        color: $slightFontColor;
      }

      :deep(.hidden-header) {
        .bk-table-header-wrapper {
          display: none;
        }
      }
    }
  }
}
</style>
<style lang="scss" scoped>
:deep(.bk-dialog) {
  .bk-dialog-wrapper .bk-dialog-header {
    padding: 3px 24px 18px;
  }

  .bk-dialog-body {
    padding-top: 0;
    padding-bottom: 0;
  }

  .bk-dialog-footer {
    font-size: 0;

    .bk-button {
      margin-right: 10px;

      &:last-child {
        margin-right: 0;
      }
    }

    .uptimecheck-tips {
      padding: 10px 10px 5px 10px;
      font-size: 12px;
      color: #fff;
      word-break: break-all;

      .set-uptimecheck {
        color: #3a9eff;
        cursor: pointer;
      }
    }
  }
}
</style>
