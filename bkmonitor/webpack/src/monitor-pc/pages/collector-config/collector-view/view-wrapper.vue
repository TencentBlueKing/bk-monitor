/* eslint-disable @typescript-eslint/naming-convention */
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
  <div class="view-wrapper">
    <view-settings
      :id="id"
      :order-list="defaultOrderList"
      :scene-list="sceneList"
      :route-type="routeType"
      :view-setting-params="viewSettingParams"
      :scene-name="sceneName"
      :dimensions="metricDimension.dimensionList"
      :view-sort-hide="hideOption.viewSortHide"
      @updateSceneList="handleUpdateSceneList"
      @change="viewSettingsChange"
      @delScene="handleDelScene"
      @addScene="handleAddScene"
    />
    <!-- 工具栏 -->
    <compare-panel
      :need-search-select="!hideOption.searchHide"
      :need-split="false"
      :search-select-list="searchSelectList"
      :value="compareValue"
      :refresh-list="refreshList"
      :timerange-list="timerangeList"
      :chart-type="chartType"
      :target-list="targetList"
      :timeshift-list="timeshiftList"
      :cur-host="curHost"
      :compare-list="compareList"
      :compare-hide="hideOption.compareHide"
      :has-view-change-icon="!hideOption.chartTypeHide"
      @add-timerange-option="addTimerangeOption"
      @add-timeshift-option="addTimeshiftOption"
      @change="handleChangeCompare"
      @chart-change="handleChartChange"
      @on-immediate-refresh="handleImmediateRefresh"
    >
      <template #append>
        <span
          v-authority="{ active: !authority.MANAGE_AUTH }"
          class="chart-tool-setting"
          @click="authority.MANAGE_AUTH ? handleShowChartSort() : handleShowAuthorityDetail(authorityMap.MANAGE_AUTH)"
        >
          <i class="icon-monitor icon-setting" />
        </span>
      </template>
      <template #pre>
        <span
          v-show="!leftShow"
          class="tool-icon right"
          @click="handleLeftShow"
        >
          <i class="arrow-right icon-monitor icon-double-up" />
        </span>
        <div
          v-if="['overview', 'topo_node'].includes(viewType) && !hideOption.convergeHide"
          class="tool-method"
        >
          <span class="label">{{ $t('汇聚') }}：</span>
          <drop-down-menu
            class="content"
            :value="defaultMethod"
            :list="aggMethods"
            @change="handleAggMethodChange"
          />
        </div>
      </template>
    </compare-panel>
    <div :class="['dashboard-wrapper', { 'no-dashboard': hideOption.dashboardHide }]">
      <variable-settings
        v-if="!hideOption.dashboardHide"
        :id="parseInt(id)"
        ref="variableSettings"
        :style="{ marginRight: `${precisionFilterWidth}px` }"
        :metric-dimension="metricDimension"
        :scene-name="sceneName"
        :scene-list="sceneList"
        :order-list="orderList"
        :route-type="routeType"
        @resultChange="handleVariableResult"
        @saveChange="handleVariableSave"
      />
      <div
        v-if="needPrecisionFilter"
        ref="precisionFilter"
        v-bk-tooltips="{ content: $t('勾选后会精准过滤，不会显示没有该维度的指标图表。'), boundary: 'window' }"
        class="precision-filter"
      >
        <bk-checkbox
          v-model="isPrecisionFilter"
          :true-value="true"
          :false-value="false"
          >{{ $t('精准过滤') }}</bk-checkbox
        >
      </div>
      <!-- 图表组件 -->
      <dashboard-panels
        v-if="!hideOption.dashboardHide"
        :groups-data="handleGroupsData"
        :variable-data="variableData"
        :compare-value="compareValue"
        :chart-option="chartOption"
        :chart-type="chartType"
        :save-active-params="{ id, sceneName, routeType }"
        :is-precision-filter="isPrecisionFilter"
      />
      <!-- 事件检索图表 -->
      <event-retrieval-view
        v-else
        :compare-value="compareValue"
        :event-metric-params="logEventRetrievalParams || null"
        :show-tip="false"
        :chart-interval="chartInterval"
        ext-cls="collect-log-view-wrapper"
        :screenshot="['screenshot']"
        :more-checked="['explore', 'strategy']"
        need-tools
        @intervalChange="interval => (chartInterval = interval)"
        @addStrategy="handleAddStrategyOfEvent"
        @exportDataRetrieval="handleExportToRetrievalOfEvent"
      >
        <template #header>
          <variable-settings
            :id="parseInt(id)"
            ref="variableSettings"
            :metric-dimension="metricDimension"
            :scene-name="sceneName"
            :scene-list="sceneList"
            :order-list="orderList"
            :route-type="routeType"
            @resultChange="handleVariableResult"
            @saveChange="handleVariableSave"
          />
        </template>
      </event-retrieval-view>
    </div>
    <!-- 图表排序组件 -->
    <!-- <sort-panel
      v-if="routeType === 'custom'"
      v-model="showChartSort"
      :groups-data="orderList"
      :need-group="true"
      @save="handleSortChange"
      @undo="handleUndo">
    </sort-panel> -->
    <view-settings-side
      :id="id"
      :is-edit="true"
      :show="showChartSort"
      :order-list="orderList"
      :route-type="routeType"
      :scene-list="sceneList"
      :scene-name="sceneName"
      :view-setting-params="viewSettingParams"
      :default-order-list="defaultOrderList"
      :view-sort-hide="hideOption.viewSortHide"
      @change="showChartSortChange"
      @editChange="handleEditScene"
    />
  </div>
</template>

<script lang="ts">
import { Component, Emit, Inject, Prop, Ref, Vue, Watch } from 'vue-property-decorator';

import { saveScenePanelConfig } from 'monitor-api/modules/data_explorer';
// import PerformanceModule from '../../../store/modules/performance'
import { deepClone } from 'monitor-common/utils/utils';

import { COLLECT_CHART_TYPE } from '../../../constant/constant';
import EventRetrievalView from '../../data-retrieval/event-retrieval/event-retrieval-view';
import ComparePanel from '../../performance/performance-detail/compare-panel.vue';
import DashboardPanels from '../../performance/performance-detail/dashboard-panels.vue';
import DropDownMenu from '../../performance/performance-detail/dropdown-menu.vue';
import SortPanel from '../../performance/performance-detail/sort-panel.vue';
import { type hideOptions, logEventRetrievalParams } from './log-handle';
import VariableSettings from './variable-settings';
import ViewSettings from './view-settings';
import ViewSettingsSide from './view-settings-side';

import type { IFilterCondition } from '../../data-retrieval/typings';
import type {
  ChartType,
  ICompareOption,
  IHostGroup,
  IOption,
  IQueryOption,
  ISearchSelectList,
} from '../../performance/performance-type';
import type { IDetailInfo, IVariableData } from '../collector-config-type';
import type { addSceneResult, metric, orderList } from './type';

@Component({
  name: 'view-wrapper',
  components: {
    ComparePanel,
    SortPanel,
    DashboardPanels,
    DropDownMenu,
    ViewSettings,
    VariableSettings,
    ViewSettingsSide,
    EventRetrievalView,
  },
})
export default class ViewWrapper extends Vue {
  @Prop({ default: '' }) id: number;
  // 图表所需数据
  @Prop({ default: () => [], type: Array }) readonly groupsData: any;
  // 图表渲染变量
  @Prop({ default: null, type: Object }) readonly variableData: IVariableData;
  // 排序数据
  @Prop({ default: () => [], type: Array }) readonly orderList: orderList[];
  // 采集详情
  @Prop({ required: true, type: Object }) readonly detailInfo: IDetailInfo;
  // 搜索下拉选择数据
  @Prop({ default: () => [], required: true, type: Array }) readonly searchSelectList: ISearchSelectList[];
  // 目标数据
  @Prop({ default: () => [], type: Array }) readonly targetList: IOption;
  // 展开左侧操作栏
  @Prop({ required: true, default: false, type: Boolean }) readonly leftShow: boolean;
  // 对比数据
  @Prop({ default: () => ({ type: 'none', value: '' }), type: Object }) readonly compare: ICompareOption;
  // 当前调用的路由页面
  @Prop({ type: String }) readonly routeType: 'collect' | 'custom';
  @Prop({ type: Object }) readonly curHost;
  @Prop({ default: 'leaf_node', type: String }) readonly viewType: 'leaf_node' | 'overview' | 'topo_node';
  @Prop({ default: 'avg', type: String }) readonly defaultMethod!: string;
  @Prop({ default: () => [], type: Array }) sceneList: any[];
  @Prop({ default: () => '', type: String }) sceneName: string;
  @Prop({ default: () => ({}), type: Object }) metricDimension: {
    dimensionList: metric[];
    metricList: { id: string; metrics: metric[] }[];
    variableParams?: any;
  };
  @Prop({ default: () => [], type: Array }) defaultOrderList: any[];
  // 日志采集及自定义事件特殊处理(需隐藏部分)
  @Prop({
    type: Object,
    default: () => ({
      chartTypeHide: false,
      viewSortHide: false,
      compareHide: false,
      searchHide: false,
      dashboardHide: false,
      convergeHide: false,
    }),
  })
  hideOption: hideOptions;

  @Prop({ default: false, type: Boolean }) needPrecisionFilter: boolean;

  @Inject('authority') authority;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;
  @Inject('authorityMap') authorityMap;

  @Ref('variableSettings') variableSettingsRef;
  @Ref('precisionFilter') precisionFilterRef: HTMLDivElement;
  private compareValue: IQueryOption = {
    compare: { type: 'none', value: '' },
    tools: {
      timeRange: 1 * 60 * 60 * 1000,
      refreshInterval: -1,
      searchValue: [],
    },
  };
  private cacheCompareValue: { [propName: string]: IQueryOption } = {};

  private chartOption: any = {
    annotation: {
      show: true,
      list: ['strategy'],
    },
  };

  private showChartSort = false;

  private timerangeList: IOption[] = [];
  private refreshList: IOption[] = [
    {
      name: window.i18n.t('刷新'),
      id: -1,
    },
    {
      name: '1m',
      id: 60 * 1000,
    },
    {
      name: '5m',
      id: 5 * 60 * 1000,
    },
    {
      name: '15m',
      id: 15 * 60 * 1000,
    },
    {
      name: '30m',
      id: 30 * 60 * 1000,
    },
    {
      name: '1h',
      id: 60 * 60 * 1000,
    },
    {
      name: '2h',
      id: 60 * 2 * 60 * 1000,
    },
    {
      name: '1d',
      id: 60 * 24 * 60 * 1000,
    },
  ];
  private timeshiftList: IOption[] = [
    {
      id: '1h',
      name: window.i18n.t('1 小时前'),
    },
    {
      id: '1d',
      name: window.i18n.t('昨天'),
    },
    {
      id: '1w',
      name: window.i18n.t('上周'),
    },
    {
      id: '1M',
      name: window.i18n.t('一月前'),
    },
  ];
  private chartType: ChartType = +localStorage.getItem(COLLECT_CHART_TYPE) % 3;

  private sortLoading = false;

  private searchTypeMap: string[] = [];
  private aggMethods: IOption[] = [
    {
      id: 'AVG',
      name: 'AVG',
    },
    {
      id: 'SUM',
      name: 'SUM',
    },
    {
      id: 'MIN',
      name: 'MIN',
    },
    {
      id: 'MAX',
      name: 'MAX',
    },
  ];
  private variableResult = []; // 变量结果
  private chartInterval = 'auto';

  /** 自定义事件、日志类型图表配置 */
  private eventChartOption = {
    tool: {
      list: ['screenshot', 'strategy', 'explore'],
    },
  };

  private isPrecisionFilter = false;
  private precisionFilterWidth = 0;

  @Watch('compare')
  handleCompareValue() {
    this.compareValue.compare = this.compare;
  }
  @Watch('sceneName')
  handleSceneName(sceneName: string) {
    if (sceneName) {
      this.compareValue = this.cacheCompareValue[sceneName] || {
        compare: { type: 'none', value: '' },
        tools: {
          timeRange: 1 * 60 * 60 * 1000,
          refreshInterval: -1,
          searchValue: [],
        },
      };
    } else {
      this.cacheCompareValue = {};
    }
  }

  get compareList() {
    const list = [
      {
        id: 'none',
        name: this.$t('不对比'),
      },
      {
        id: 'time',
        name: this.$t('时间对比'),
      },
    ];

    if (this.viewType === 'leaf_node') {
      list.push({
        id: 'target',
        name: this.$t('目标对比'),
      });
    }
    return list;
  }

  get handleGroupsData() {
    const data = deepClone(this.groupsData);
    // if (this.variableResult.length === 0) return []
    if (!data.length) return [];
    const len = this.searchTypeMap.length;
    if (len && this.groupsData.length) {
      data.forEach(item => {
        item.panels = item.panels.filter(pan =>
          this.searchTypeMap.some(keywordItem => {
            const keywords = keywordItem.split('.').map(item => item.trim().toLocaleLowerCase());
            const id = (pan.id ?? '').trim().toLocaleLowerCase();
            if (keywords.length > 1) {
              // 含有组的搜索
              return id.indexOf(keywords[0]) > -1 && id.indexOf(keywords[1]) > -1;
            }
            const title = (pan.title ?? '').trim().toLocaleLowerCase();
            return title.indexOf(keywords[0]) > -1 || id.indexOf(keywords[0]) > -1;
          })
        );
      });
    }
    return data;
  }

  get logEventRetrievalParams() {
    if (this.hideOption.dashboardHide && this.handleGroupsData.length) {
      return logEventRetrievalParams(this.handleGroupsData, this.variableData, this.defaultMethod);
    }
    return null;
  }

  // 传入图表的参数
  get collectConfigParams() {
    return {
      dimensionsPreviews: this.variableSettingsRef?.dimensionsPreviews,
      variableResult: this.variableResult, // 变量结果
      metricGroup: this.metricDimension.metricList, // 指标集
      type: 'collect-config',
    };
  }
  // 传入视图设置
  get viewSettingParams() {
    const { variableResult } = this.collectConfigParams;
    return {
      variableResult: variableResult || [],
    };
  }

  created() {
    this.timerangeList = [
      {
        name: `${this.$t('近{n}分钟', { n: 5 })}`,
        value: 5 * 60 * 1000,
      },
      {
        name: `${this.$t('近{n}分钟', { n: 15 })}`,
        value: 15 * 60 * 1000,
      },
      {
        name: `${this.$t('近{n}分钟', { n: 30 })}`,
        value: 30 * 60 * 1000,
      },
      {
        name: `${this.$t('近{n}小时', { n: 1 })}`,
        value: 1 * 60 * 60 * 1000,
      },
      {
        name: `${this.$t('近{n}小时', { n: 3 })}`,
        value: 3 * 60 * 60 * 1000,
      },
      {
        name: `${this.$t('近{n}小时', { n: 6 })}`,
        value: 6 * 60 * 60 * 1000,
      },
      {
        name: `${this.$t('近{n}小时', { n: 12 })}`,
        value: 12 * 60 * 60 * 1000,
      },
      {
        name: `${this.$t('近{n}小时', { n: 24 })}`,
        value: 24 * 60 * 60 * 1000,
      },
      {
        name: `${this.$t('近 {n} 天', { n: 2 })}`,
        value: 2 * 24 * 60 * 60 * 1000,
      },
      {
        name: `${this.$t('近 {n} 天', { n: 7 })}`,
        value: 7 * 24 * 60 * 60 * 1000,
      },
      {
        name: `${this.$t('近 {n} 天', { n: 30 })}`,
        value: 30 * 24 * 60 * 60 * 1000,
      },
      {
        name: `${this.$t('今天')}`,
        value: 'today',
      },
      {
        name: `${this.$t('昨天')}`,
        value: 'yesterday',
      },
      {
        name: `${this.$t('前天')}`,
        value: 'beforeYesterday',
      },
      {
        name: `${this.$t('本周')}`,
        value: 'thisWeek',
      },
    ];
  }

  mounted() {
    if (this.needPrecisionFilter) {
      this.precisionFilterWidth = this.precisionFilterRef.clientWidth;
    }
  }

  // 点击显示左侧栏
  @Emit('show-left')
  handleLeftShow() {
    return !this.leftShow;
  }

  // 图表排序
  handleShowChartSort() {
    this.showChartSort = true;
  }

  handleChangeCompare(v: IQueryOption) {
    this.compareValue = v;
    if (v.type === 'compare' || v.type === 'timeRange') {
      this.$emit('on-compare-change', v);
    } else if (v.type === 'search') {
      if (v.tools.searchValue.length) {
        v.tools.searchValue.forEach(item => {
          if (item.values) {
            item.values.forEach(v => {
              if (!this.searchTypeMap.includes(`${item.id}.${v.id}`)) {
                this.searchTypeMap.push(`${item.id}.${v.id}`);
              }
            });
          } else {
            if (!this.searchTypeMap.includes(item.id)) {
              this.searchTypeMap.push(item.id);
            }
          }
        });
      } else {
        this.searchTypeMap = [];
      }
    }
  }

  //   // 获取compare-config参数
  //   handleGetCompareParams() {
  //     const { compare: { value, type } } = this.compareValue
  //     const compareParams: any = { type }
  //     if (type === 'time') {
  //       compareParams.time_offset = value || '1h'
  //     } else if (type === 'target') {
  //       if (this.detailInfo.targetObjectType === 'HOST') {
  //         compareParams.hosts = Array.isArray(value) ? value.map((item) => {
  //           const val = item.split('-')
  //           return {
  //             bk_target_ip: val[1],
  //             bk_target_cloud_id: val[0]
  //           }
  //         }) : []
  //       } else if (this.detailInfo.targetObjectType === 'SERVICE') {
  //         compareParams.service_instance_ids = Array.isArray(value) ? value.map((item) => {
  //           const val = item.split('-')
  //           return {
  //             bk_target_instance_id: val[0]
  //           }
  //         }) : []
  //       }
  //     }
  //     return compareParams
  //   }

  handleChartChange(v: ChartType) {
    this.chartType = v;
  }

  @Emit('sort-change')
  async handleSortChange(data: IHostGroup[]) {
    await this.saveScenePanelConfig(data);
  }

  @Emit('sort-change')
  async handleUndo() {
    await this.saveScenePanelConfig(this.defaultOrderList);
  }

  /**
   * @description: 保存场景
   * @param {*} order
   * @return {*}
   */
  async saveScenePanelConfig(order) {
    let id;
    if (this.routeType === 'collect') {
      id = `collect_config_${this.detailInfo.id}`;
    } else {
      id = `custom_report_${this.$route.params.id}`;
    }
    this.sortLoading = true;
    const success = await saveScenePanelConfig({
      id,
      config: {
        order,
        variables: this.viewSettingParams.variableResult.map(item => ({ id: item.key, name: item.name })),
        name: this.sceneName,
      },
    });
    this.sortLoading = false;
    if (success) {
      this.showChartSort = false;
    }
  }

  addTimeshiftOption(val: string) {
    this.timeshiftList.push({
      id: val,
      name: val,
    });
  }

  addTimerangeOption(val: IOption) {
    this.timerangeList.push(val);
  }
  /**
   * @description: 获取变量结果
   * @param {*} val
   * @param {*} value
   * @param {*} groupId 所属指标集
   * @return {*}
   */
  handleVariableResult(val: { groupId: string; key: string; name: string; value: string[] }[]) {
    if (JSON.stringify(val) === JSON.stringify(this.variableResult)) return;
    this.variableResult = JSON.parse(JSON.stringify(val));
    this.handleImmediateRefresh();
  }
  /**
   * @description: 是否显示侧栏
   * @param {*} val
   * @return {*}
   */
  showChartSortChange(val: boolean) {
    this.showChartSort = val;
  }

  @Emit('on-immediate-refresh')
  handleImmediateRefresh() {}
  @Emit('method-change')
  handleAggMethodChange(method) {
    return method;
  }
  /**
   * @description: 切换场景
   * @param {*}
   * @return {*}
   */
  @Emit('scene-change')
  viewSettingsChange(val) {
    this.variableResult = [];
    this.cacheCompareValue[this.sceneName] = deepClone(this.compareValue);
    return val;
  }
  @Emit('updateSceneList')
  handleUpdateSceneList() {}
  /**
   * @description: 保存变量
   * @param {*}
   * @return {*}
   */
  @Emit('variable-save')
  handleVariableSave(val) {
    return val;
  }
  /**
   * @description: 删除场景
   * @param {*}
   * @return {*}
   */
  @Emit('del-scene')
  handleDelScene(sceneName: string) {
    return sceneName;
  }
  /**
   * @description: 添加场景
   * @param {*}
   * @return {*}
   */
  @Emit('add-scene')
  handleAddScene(result: addSceneResult) {
    return result;
  }
  /**
   * @description: 编辑场景
   * @param {*}
   * @return {*}
   */
  @Emit('edit-scene')
  handleEditScene(result: addSceneResult) {
    this.showChartSort = false;
    return result;
  }

  /**
   * @description: 自定义事件、日志类型图表跳转策略
   */
  handleAddStrategyOfEvent(data: IFilterCondition.VarParams) {
    const {
      data_source_label,
      data_type_label,
      result_table_id,
      where,
      method,
      metric_field,
      group_by: groupBy,
    } = data;
    const queryConfigs = [
      {
        data_source_label,
        data_type_label,
        filter_dict: {},
        functions: [],
        group_by: groupBy || [],
        index_set_id: '',
        interval: 60,
        table: result_table_id,
        item: '',
        where: where || [],
        metrics: [{ alias: 'a', field: metric_field, method: method || 'COUNT' }],
      },
    ];
    const queryData = {
      expression: 'a',
      query_configs: queryConfigs,
    };

    window.open(
      `${location.href.replace(location.hash, '#/strategy-config/add')}?data=${encodeURIComponent(JSON.stringify(queryData))}`
    );
  }
  /**
   * @description: 自定义事件、日志类型图表跳转检索
   */
  handleExportToRetrievalOfEvent(data: IFilterCondition.VarParams) {
    const {
      data_source_label,
      data_type_label,
      result_table_id,
      where,
      method,
      metric_field,
      group_by: groupBy,
    } = data;
    const targets = [
      {
        data: {
          expression: '',
          query_configs: [
            {
              data_source_label,
              data_type_label,
              filter_dict: {},
              functions: [],
              group_by: groupBy || [],
              index_set_id: '',
              interval: 60,
              result_table_id,
              item: '',
              where: where || [],
              metric_field,
              method,
            },
          ],
        },
      },
    ];

    window.open(
      `${location.href.replace(location.hash, '#/data-retrieval')}?targets=${encodeURIComponent(JSON.stringify(targets))}&type=event`
    );
  }
}
</script>

<style lang="scss" scoped>
.view-wrapper {
  height: 100%;

  .dashboard-wrapper {
    position: relative;
    height: calc(100% - 91px);
    padding: 16px;
    overflow-y: scroll;

    &.no-dashboard {
      height: calc(100% - 90px);
      padding: 0;
      overflow-y: hidden;
    }

    .collect-log-view-wrapper {
      width: 100%;
    }

    .precision-filter {
      position: absolute;
      top: 24px;
      right: 24px;
    }
  }

  .chart-tool-setting {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 48px;
    height: 42px;
    font-size: 14px;
    color: #979ba5;
    cursor: pointer;
    border-left: 1px solid #f0f1f5;
  }

  .tool-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 48px;
    height: 42px;
    font-size: 14px;
    color: #979ba5;
    cursor: pointer;
    border-left: 1px solid #f0f1f5;

    &.right {
      border-right: 1px solid #f0f1f5;
    }

    .arrow-right {
      font-size: 24px;
      color: #979ba5;
      cursor: pointer;
      transform: rotate(90deg);
    }
  }

  .tool-method {
    padding-left: 14px;
    border-right: 1px solid #f0f1f5;
  }

  :deep(.bk-sideslider-wrapper) {
    padding-top: 50px;
  }
}
</style>
