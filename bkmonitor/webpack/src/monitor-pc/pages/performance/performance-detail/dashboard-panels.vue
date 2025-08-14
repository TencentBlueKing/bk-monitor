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
  <!-- 主机视图 -->
  <ul class="dashboard-panels">
    <div
      v-if="searchTipsObj.show"
      class="total-tips"
    >
      <div class="tips-text">
        <span>{{
          `${$t('找到 {count} 条结果 , 耗时  {time} ms', { count: totalCount, time: searchTipsObj.time })}`
        }}</span>
        <span v-if="searchTipsObj.showAddStrategy"
          >,
          <span
            class="add-strategy-btn"
            @click="handleQueryAddStrategy"
            >{{ $t('添加监控策略') }}</span
          >
        </span>
      </div>
      <div
        v-if="searchTipsObj.showSplit"
        class="split-btn-wrapper"
      >
        <span class="btn-text">{{ $t('合并视图') }}</span>
        <bk-switcher
          :value="!searchTipsObj.value"
          size="small"
          theme="primary"
          @change="changeSplit"
        />
      </div>
    </div>
    <li
      v-for="group in groupList"
      :key="group.key"
    >
      <template v-if="group.type === 'row' && group.id !== '__UNGROUP__'">
        <bk-collapse v-model="activeName">
          <bk-collapse-item
            :key="group.id"
            class="mb10"
            hide-arrow
            :name="group.id"
          >
            <div class="group-item-title">
              <i :class="['icon-monitor icon-arrow-right', { expand: activeName.includes(group.id) }]" />
              <!-- 分组名称 -->
              <span class="ml5">{{ group.title }}</span>
            </div>
            <template #content>
              <div class="chart-wrapper-old">
                <template v-for="(item, index) in group.panels">
                  <div
                    v-if="!item.hidden && showPanel(item.show)"
                    :key="item.key"
                    :class="[
                      `chart-type-${chartType}`,
                      'group-type',
                      {
                        'border-bottom':
                          group.panels.length - index <= chartType + 1 &&
                          group.panels.length - index <= (group.panels.length % (chartType + 1) || chartType + 1),
                      },
                      { 'border-right': chartType > 0 && (index + 1) % (chartType + 1) },
                      {
                        'is-collect': needCollect && getHasCollected(item.id),
                        'is-collect-row': needCollect && getHasCollected(item.id),
                        'collect-wrapper': needCollect,
                      },
                    ]"
                  >
                    <monitor-echarts
                      :height="chartType > 0 ? 210 : onlyChartHeight"
                      :options="handleChartOptions(item)"
                      :chart-type="getPanelChartType(item)"
                      :title="item.title"
                      :subtitle="item.subTitle"
                      :get-series-data="getSeriesData(item)"
                      :refresh-interval="compareValue.tools.refreshInterval"
                      :get-alarm-status="getAlarmStatus"
                      :group-id="groupId"
                      :has-resize="chartType === 0"
                      :has-table="isOnlyChart"
                      @relate-alert="handleRelateAlert(item)"
                      @add-strategy="handleAddStrategy(item)"
                      @export-data-retrieval="handleExportToRetrieval(item)"
                      @collect-chart="handleCollectSingleChart(item)"
                      @on-yaxis-set-scale="needScale => handleOnYAxisSetScale(item, needScale)"
                      @on-transform-area="isArea => handleTransformArea(item, isArea)"
                      @full-screen="handleFullScreen(item)"
                    />
                    <span
                      v-if="!readonly"
                      v-authority="{ active: !authority.GRAFANA_MANAGE_AUTH }"
                      class="collect-wrapper-mark"
                      @click="
                        authority.GRAFANA_MANAGE_AUTH
                          ? handleCollectChart(item)
                          : handleShowAuthorityDetail(authorityMap.GRAFANA_MANAGE_AUTH)
                      "
                    />
                  </div>
                </template>
              </div>
            </template>
          </bk-collapse-item>
        </bk-collapse>
      </template>
      <div
        v-else
        :key="group.key"
        class="chart-wrapper-old"
      >
        <template v-for="(item, index) in group.panels">
          <div
            v-if="!item.hidden && showPanel(item.show)"
            :id="!!item.group ? `${item.group}${!!item.index ? '-' + item.index : ''}` : `${item.index}`"
            :key="item.key"
            class="common-chart"
            :class="[
              `chart-type-${chartType}`,
              {
                'is-collect': needCollect && item.type === 'graph' && getHasCollected(item.id),
                'collect-wrapper': needCollect && item.type === 'graph',
                'has-child': item.panels && item.panels.length,
              },
            ]"
          >
            <div
              v-if="item.panels && item.panels.length"
              :class="{ 'column-wrapper': chartType > 0 }"
              class="child-wrapper"
            >
              <div
                v-for="child in item.panels"
                :key="child.key"
                class="child-chart"
              >
                <monitor-echarts
                  v-if="!child.hidden"
                  :height="chartType > 0 ? 130 : onlyChartHeight"
                  :chart-type="getPanelChartType(child)"
                  :options="chartOptions"
                  :title="child.title"
                  :subtitle="child.subTitle"
                  :error-msg="errorMsg"
                  :get-series-data="getSeriesData(child)"
                  :refresh-interval="compareValue.tools.refreshInterval"
                  :get-alarm-status="getAlarmStatus"
                  :group-id="groupId"
                  :has-resize="chartType === 0"
                  :has-table="isOnlyChart"
                  @relate-alert="handleRelateAlert(item)"
                  @add-strategy="handleAddStrategy(child)"
                  @export-data-retrieval="handleExportToRetrieval(child)"
                  @collect-chart="handleCollectSingleChart(child)"
                  @on-yaxis-set-scale="needScale => handleOnYAxisSetScale(item, needScale)"
                  @on-transform-area="isArea => handleTransformArea(item, isArea)"
                  @full-screen="handleFullScreen(child)"
                />
              </div>
            </div>
            <monitor-echarts
              v-else-if="!item.hidden"
              :height="chartType > 0 ? 230 : onlyChartHeight"
              :options="handleChartOptions(item)"
              :chart-type="getPanelChartType(item)"
              :title="item.title"
              :subtitle="item.subTitle"
              :error-msg="errorMsg[index]"
              :get-series-data="getSeriesData(item, index)"
              :refresh-interval="compareValue.tools.refreshInterval"
              :get-alarm-status="getAlarmStatus"
              :group-id="groupId"
              :has-resize="chartType === 0"
              :has-table="isOnlyChart"
              @relate-alert="handleRelateAlert(item)"
              @add-strategy="handleAddStrategy(item)"
              @export-data-retrieval="handleExportToRetrieval(item)"
              @collect-chart="handleCollectSingleChart(item)"
              @on-yaxis-set-scale="needScale => handleOnYAxisSetScale(item, needScale)"
              @on-transform-area="isArea => handleTransformArea(item, isArea)"
              @full-screen="handleFullScreen(item)"
            />
            <span
              v-if="!readonly && item.type === 'graph'"
              v-authority="{ active: !authority.GRAFANA_MANAGE_AUTH }"
              class="collect-wrapper-mark"
              @click="
                authority.GRAFANA_MANAGE_AUTH
                  ? handleCollectChart(item)
                  : handleShowAuthorityDetail(authorityMap.GRAFANA_MANAGE_AUTH)
              "
            />
          </div>
        </template>
      </div>
    </li>
    <template v-if="groupList.length">
      <collect-chart
        :is-single="isSingleChart"
        :show="collectShow"
        :collect-list="collectList"
        :total-count="totalCount"
        @collect-all="handleCollectionAll"
        @close="handleCloseCollect"
        @view-detail="handleGotoViewDetail"
        @data-retrieval="handleGotoDataRetrieval"
      />
    </template>
    <template v-else>
      <bk-exception
        style="margin-top: 15%"
        type="empty"
      >
        <span>{{ $t('查无数据') }}</span>
      </bk-exception>
    </template>
    <template v-if="showViewDetail">
      <view-detail
        :show-modal="showViewDetail"
        :view-config="viewQueryConfig"
        @close-modal="closeViewDetail"
      />
    </template>
  </ul>
</template>
<script lang="ts">
import { Component, Inject, InjectReactive, Prop, Vue, Watch } from 'vue-property-decorator';

import dayjs from 'dayjs';
import deepMerge from 'deepmerge';
// import { handleTimeRange } from '../../../utils/index';
import { graphUnifyQuery, logQuery } from 'monitor-api/modules/grafana';
import { fetchItemStatus } from 'monitor-api/modules/strategies';
import { deepClone, random } from 'monitor-common/utils/utils.js';
import { handleRelateAlert } from 'monitor-ui/chart-plugins/utils';
import MonitorEcharts from 'monitor-ui/monitor-echarts/monitor-echarts-new.vue';
import { echartsConnect, echartsDisconnect } from 'monitor-ui/monitor-echarts/utils';

import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import authorityStore from '../../../store/modules/authority';
import { getCollectVariable, setCollectVariable } from '../../collector-config/collector-view/variable-set';
import CollectChart from '../../data-retrieval/components/collect-chart.vue';

import type { ChartType, IHostGroup, IQueryOption, ISearchTipsObj } from '../performance-type';

@Component({
  name: 'dashboard-panels',
  components: {
    MonitorEcharts,
    CollectChart,
    ViewDetail: () => import(/* webpackChunkName: "view-detail" */ '../../view-detail/view-detail.vue'),
  },
})
export default class DashboardPanels extends Vue {
  // dashboard配置数据
  @Prop({ required: true }) readonly groupsData: IHostGroup[];
  // 图表样式
  @Prop({ default: 1 }) readonly chartType: ChartType;
  // 变量数据 属性以 $开始
  @Prop() readonly variableData: {};
  // 对比工具栏数据
  @Prop({ required: true }) readonly compareValue: IQueryOption;
  // 是否需要收藏功能
  @Prop({ default: true }) readonly needCollect: boolean;
  // 图表配置设置
  @Prop() readonly chartOption: object;
  // 搜索提示数据
  @Prop({
    default: () => ({
      value: true,
      show: false,
      time: 0,
      showSplit: true,
      showAddStrategy: false,
    }),
    type: Object,
  })
  searchTipsObj: ISearchTipsObj;

  @Prop({ default: '' }) keyword: string;
  @Prop({ default: () => ({}), type: Object }) saveActiveParams;
  @Prop({ default: false, type: Boolean }) isPrecisionFilter: boolean; // 是否精准过滤
  /** 分组id */
  @Prop({ type: String }) groupId: string;

  @Inject('authority') authority;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;
  @Inject('authorityMap') authorityMap;
  @InjectReactive('downSampleRange') downSampleRange;
  @InjectReactive('readonly') readonly;
  activeName = [];
  groupList = [];
  collectList = [];
  collectShow = false;
  totalCount = 0;
  isSingleChart = false;
  showViewDetail = false;
  viewQueryConfig = {};
  errorMsg = [];
  onlyChartHeight = 210;
  get chartOptions() {
    return deepMerge(
      {
        tool: {
          list: ['save', 'screenshot', 'fullscreen', 'explore', 'set', 'strategy', 'area', 'relate-alert'],
        },
        legend: {
          asTable: this.chartType === 0,
          toTheRight: this.chartType === 0,
          maxHeight: 50,
        },
      },
      this.chartOption || {},
      {
        arrayMerge: (destinationArray, sourceArray) => sourceArray,
      }
    );
  }

  /** 是否只有一个图表 */
  get isOnlyChart() {
    const total = this.groupList.reduce((pre, cur) => {
      if (cur.panels?.length) {
        const num = cur.panels.filter(panel => panel.type !== 'row').length;
        pre += num;
      }
      return pre;
    }, 0);
    return total === 1;
  }

  mounted() {
    this.onlyChartHeight = this.getOnlyChartHeight();
    echartsConnect(this.groupId);
  }
  destroyed() {
    echartsDisconnect(this.groupId);
  }
  getTimerange() {
    const { tools } = this.compareValue;
    // const { startTime, endTime } = handleTimeRange(tools.timeRange);
    const [startTime, endTime] = handleTransformToTimestamp(tools.timeRange);
    return {
      start_time: startTime,
      end_time: endTime,
    };
  }

  @Watch('activeName')
  handleActiveName(active) {
    if (this.saveActiveParams.id && this.saveActiveParams.sceneName) {
      const { id, sceneName, routeType } = this.saveActiveParams;
      setCollectVariable(id, sceneName, { type: 'dashboard', active }, routeType);
    }
  }

  @Watch('groupsData', { immediate: true })
  onGroupDataChange(v) {
    this.handleGroupDataChange(v);
  }
  @Watch('keyword')
  onKeywordChange() {
    this.handleGroupDataChange(this.groupsData);
  }
  @Watch('downSampleRange', { immediate: true })
  onItervalChange() {
    this.handleGroupDataChange(this.groupsData);
  }

  @Watch('isOnlyChart')
  isOnlyChartChange() {
    this.onlyChartHeight = this.getOnlyChartHeight();
  }

  getOnlyChartHeight() {
    const height = (document.querySelector('.dashboard-panels') as HTMLDivElement)?.offsetHeight || 0;
    return this.isOnlyChart ? Math.max(height / 2 - 54, 210) : 210;
  }
  // 获取图表数据
  getSeriesData(config, index) {
    return async (startTime?, endTime?) => {
      const dataList = await Promise.all(
        (config.targets || []).map(async item => {
          let params = item.data;
          let timerange = this.getTimerange();
          if (this.variableData) {
            params = this.compileVariableData(params);
          }
          if (startTime && endTime) {
            timerange = {
              start_time: dayjs(startTime).unix(),
              end_time: dayjs(endTime).unix(),
            };
          }
          if (item.datasourceId === 'log') {
            return await logQuery({
              ...params,
              ...timerange,
            }).catch(() => ({
              columns: [],
              rows: [],
            }));
          }
          return await graphUnifyQuery(
            {
              ...params,
              ...timerange,
              slimit: window.slimit || 500,
              // interval: reviewInterval(params.interval, ),
              down_sample_range: this.downSampleRangeComputed(this.downSampleRange, Object.values(timerange)),
            },
            { needRes: true, needMessage: false }
          )
            .then(({ data, tips }) => {
              if (data?.length >= window.slimit) {
                this.$bkNotify({
                  theme: 'warning',
                  title: this.$t('注意：单图中的数据量过多!!!'),
                  limitLine: 0,
                  message: `${this.$t('[{title}] 单图中的数据条数过多，为了避免查询和使用问题只显示了{slimit}条。', {
                    title: config.title,
                    slimit: window.slimit || 500,
                  })}${this.$route.name === 'data-retrieval' ? this.$t('可以改变查询方式避免单图数量过大。') : ''}`,
                });
              }
              if (tips?.length) {
                this.$bkMessage({
                  theme: 'warning',
                  message: tips,
                });
              }
              this.$set(this.errorMsg, index, '');
              const series = data?.series || [];
              return series.map(({ target, datapoints, ...setData }) => ({
                datapoints,
                ...setData,
                target:
                  this.handleBuildLegend(item.alias, {
                    ...setData,
                    tag: {
                      ...setData.dimensions,
                      ...setData.dimensions_translation,
                    },
                    metric: setData.metric,
                    formula: params.method,
                    ...params,
                  }) || target,
              }));
            })
            .catch(err => {
              this.$set(this.errorMsg, index, err.message || err.msg);
            });
        })
      );
      const sets = dataList.reduce<any[]>((data, item) => data.concat(item), []);
      return sets;
    };
  }
  downSampleRangeComputed(downSampleRange: string, timeRange: number[]) {
    if (downSampleRange === 'raw') {
      return undefined;
    }
    if (downSampleRange === 'auto') {
      const size = (timeRange[1] - timeRange[0]) / this.$el.querySelector('.common-chart').clientWidth;
      return size > 0 ? `${Math.ceil(size)}s` : undefined;
    }
    return downSampleRange;
  }
  // 获取告警状态信息
  async getAlarmStatus(id) {
    const data = await fetchItemStatus({ metric_ids: [id] }).catch(() => ({ [id]: 0 }));
    return data?.[id];
  }
  handleChartOptions(item) {
    if (item.type === 'table') {
      return deepMerge(
        this.chartOptions,
        {
          tool: {
            list: ['save', 'screenshot'],
          },
        },
        {
          arrayMerge: (destinationArray, sourceArray) => sourceArray,
        }
      );
    }
    // 跳转数据检索、新增策略不支持多指标
    if (item.targets && item.targets.length > 1 && this.chartOptions?.tool?.list) {
      const { list } = this.chartOptions.tool;
      return deepMerge(
        this.chartOptions,
        {
          tool: {
            list: list.filter(item => item !== 'strategy'),
          },
        },
        {
          arrayMerge: (destinationArray, sourceArray) => sourceArray,
        }
      );
    }
    return this.chartOptions;
  }
  handleBuildLegend(alia: string, compareData = {}) {
    if (!alia) return alia;
    let alias = alia;
    Object.keys(compareData).forEach(key => {
      const val = compareData[key] || {};
      if (key === 'time_offset') {
        if (val && alias.match(/\$time_offset/g)) {
          const timeMatch = val.match(/(-?\d+)(\w+)/);
          const hasMatch = timeMatch && timeMatch.length > 2;
          alias = alias.replace(
            /\$time_offset/g,
            hasMatch
              ? dayjs.tz().add(-timeMatch[1], timeMatch[2]).fromNow().replace(/\s*/g, '')
              : val.replace('current', this.$t('当前'))
          );
        }
      } else if (typeof val === 'object') {
        Object.keys(val)
          .sort((a, b) => b.length - a.length)
          .forEach(valKey => {
            const variate = `$${key}_${valKey}`;
            alias = alias.replace(new RegExp(`\\${variate}`, 'g'), val[valKey]);
          });
      } else {
        alias = alias.replace(`$${key}`, val);
      }
    });
    while (/\|\s*\|/g.test(alias)) {
      alias = alias.replace(/\|\s*\|/g, '|');
    }
    return alias.replace(/\|$/g, '');
  }
  // 变量替换
  compileVariableData(data) {
    let params = JSON.stringify(data);
    this.variableData &&
      Object.keys(this.variableData).forEach(key => {
        params = params.replace(new RegExp(`\\${key}`, 'g'), this.variableData[key]);
      });
    params = JSON.parse(params);
    return params;
  }

  // 多选跳转大图
  handleGotoViewDetail() {
    const config = this.collectList.reduce((config, item) => {
      if (!config) {
        config = item;
      } else {
        config.targets.push(...item.targets);
        config.title = this.$t('对比');
        config.subTitle = '';
      }
      return config;
    }, null);
    this.viewQueryConfig = {
      config,
      compareValue: this.compareValue,
    };
    this.showViewDetail = true;
  }

  // 多选跳转数据检索
  handleGotoDataRetrieval() {
    if (this.$route?.name === 'data-retrieval') return;

    const targets = this.collectList.reduce((pre, item) => {
      pre.push(...item.targets);
      return pre;
    }, []);

    window.open(
      `${location.href.replace(location.hash, '#/data-retrieval')}?targets=${encodeURIComponent(JSON.stringify(targets))}`
    );
  }

  //  跳转数据大图
  handleFullScreen(item) {
    const query = deepClone(item);
    if (this.variableData) {
      query.targets = query.targets.map(item => this.compileVariableData(item));
    }
    this.viewQueryConfig = {
      config: query,
      compareValue: this.compareValue,
    };
    this.showViewDetail = true;
  }

  // 关闭查看大图弹窗
  closeViewDetail() {
    this.showViewDetail = false;
    this.viewQueryConfig = {};
  }

  // 导出到数据检索
  handleExportToRetrieval(item) {
    if (this.$route?.name === 'data-retrieval') return;
    let { targets } = item;
    if (this.variableData) {
      targets = this.compileVariableData(targets);
    }

    window.open(
      `${location.href.replace(location.hash, '#/data-retrieval')}?targets=${encodeURIComponent(JSON.stringify(targets))}`
    );
  }
  // 跳转新增策略
  handleAddStrategy(item) {
    const { targets } = item;
    if (targets.length === 1) {
      let [{ data }] = targets;
      if (this.variableData) {
        data = this.compileVariableData(data);
      }
      if (data?.where?.length) {
        data.where.forEach((where, index) => {
          if (index > 0 && where && !where.condition) {
            where.condition = 'and';
          }
        });
      }
      window.open(`${location.href.replace(location.hash, '#/strategy-config/add')}?data=${JSON.stringify(data)}`);
    }
  }
  handleRelateAlert(item) {
    handleRelateAlert(item, this.compareValue.tools.timeRange);
  }
  //  全部收藏
  handleCollectionAll() {
    let setList = [];
    this.groupList.forEach(item => {
      if (item.panels) {
        setList = [...setList, ...item.panels];
      } else {
        setList.push(item);
      }
    });
    this.collectList = setList.filter(item => !item.hidden).map(item => this.compileVariableData(item));
  }

  //   点击收藏
  handleCollectChart(item) {
    const index = this.collectList.findIndex(set => set.id === item.id);
    index === -1 ? this.collectList.push(this.compileVariableData(item)) : this.collectList.splice(index, 1);
    this.isSingleChart = false;
    this.collectShow = true;
    if (!this.collectList.length) this.collectShow = false;
  }

  async handleCollectSingleChart(item) {
    if (!this.authority.GRAFANA_MANAGE_AUTH) {
      authorityStore.getAuthorityDetail(this.authorityMap.GRAFANA_MANAGE_AUTH);
      return;
    }
    if (this.collectShow) {
      this.collectShow = false;
      this.collectList = [];
    }
    await this.$nextTick();
    this.collectList.push(this.compileVariableData(item));
    this.isSingleChart = true;
    this.collectShow = true;
  }

  handleTransformArea(item: any, isArea: boolean) {
    item.fill = isArea;
  }

  handleOnYAxisSetScale(item: any, needScale: boolean) {
    item.min_y_zero = !needScale;
  }

  //   点击关闭收藏
  handleCloseCollect(v: boolean) {
    this.collectShow = v;
    this.collectList = [];
  }

  //  是否已经被收藏
  getHasCollected(id) {
    return this.collectList.some(item => item.id === id);
  }

  changeSplit(val) {
    this.$emit('split-change', !val);
  }

  handleQueryAddStrategy() {
    this.$emit('add-strategy');
  }
  handleGroupDataChange(v) {
    this.collectList = [];
    this.collectShow = false;
    this.groupList = [];
    const groupsData = JSON.parse(JSON.stringify(v));
    let setList = [];
    let count = 0;
    const specialGroup = {
      type: 'special',
      panels: [],
    };
    const hasKeyword = item => {
      this.keyword.trim() &&
        item.panels.forEach(child => {
          const keyword = (this.keyword ?? '').trim().toLocaleLowerCase();
          const isShow =
            (child.title ?? '').toLocaleLowerCase().indexOf(keyword) !== -1 ||
            (child.targets || []).some(item =>
              item.data?.query_configs.some(
                set => (set.metrics?.[0]?.field ?? '').toLocaleLowerCase().indexOf(keyword) !== -1
              )
            );
          child.hidden = !isShow;
        });
    };
    this.activeName = [];
    if (this.saveActiveParams.id && this.saveActiveParams.sceneName) {
      const { id, sceneName, routeType } = this.saveActiveParams;
      const active = getCollectVariable(id, sceneName, 'dashboard', routeType);
      if (active?.length) {
        this.activeName = active;
      } else {
        this.activeName = this.groupsData.filter(item => item.type === 'row').map(item => item.id);
      }
    } else {
      this.activeName = this.groupsData.filter(item => item.type === 'row').map(item => item.id);
    }

    groupsData.forEach(item => {
      if (item.type === 'row') {
        if (item.id !== '__UNGROUP__') {
          setList.length &&
            this.groupList.push({
              type: 'list',
              panels: setList,
              key: random(10),
            });
          setList = [];
          this.groupList.push(item);
          hasKeyword(item);
          count += item.panels.filter(set => !set.hidden).length;
        } else {
          setList = setList.concat(item.panels);
          hasKeyword(item);
          count += item.panels.filter(set => !set.hidden).length;
        }
      } else if (['status', 'text'].includes(item.type)) {
        specialGroup.panels.push(item);
      } else {
        setList.push(item);
        item.hidden =
          (item.title || '').toLocaleLowerCase().indexOf(this.keyword) === -1 ||
          (item.targets || []).every(
            set => (set?.data.metric_field || '').toLocaleLowerCase().indexOf(this.keyword) === -1
          );
        count += !item.hidden ? 1 : 0;
      }
    });
    setList.length &&
      this.groupList.push({
        type: 'list',
        panels: setList,
        key: random(10),
      });
    specialGroup.panels.length && this.groupList[0].panels.unshift(specialGroup);
    this.totalCount = count;
    this.$emit('chart-count-change', count);
  }
  getPanelChartType(panel) {
    return panel.type === 'graph' ? 'line' : panel.type;
  }
  showPanel(show) {
    if (show === undefined) {
      return true;
    }
    return this.isPrecisionFilter ? !!show : true;
  }
}
</script>
<style lang="scss" scoped>
.group-item-title {
  display: flex;
  align-items: center;

  .icon-arrow-right {
    font-size: 24px;
    color: #979ba5;
    transition: transform 0.2s ease-in-out;

    &.expand {
      transform: rotate(90deg);
    }
  }
}

.dashboard-panels {
  position: relative;
  margin-bottom: 25px;

  :deep(.bk-collapse-item-hover) {
    background: #fff;
    border-radius: 2px;
    box-shadow: 0px 1px 2px 0px rgba(0, 0, 0, 0.05);

    &:hover {
      color: #63656e;
    }
  }

  :deep(.bk-collapse-item-content) {
    padding: 0;
    margin-top: 1px;
    background: #fff;
    box-shadow: 0px 1px 2px 0px rgba(0, 0, 0, 0.1);
  }

  .chart-wrapper-old {
    display: flex;
    flex-wrap: wrap;
    width: calc(100% + 10px);
    margin-right: -10px;

    @for $i from 0 through 4 {
      .chart-type-#{$i} {
        padding: 10px;
        background-color: white;
        border-bottom: 1px solid #ddd;

        $w: calc(100% / ($i + 1));

        @if $i == 1 {
          flex: 0 0 calc($w - 10px);
          width: calc($w - 10px);

          &.group-type {
            flex: 0 0 calc($w - 5px);
            width: calc($w - 5px);
          }
        } @else {
          flex: 0 0 calc($w - 10px);
          width: calc($w - 10px);
        }

        &.border-bottom {
          border-bottom: 0;
        }

        &.border-right {
          border-right: 1px solid #ddd;
        }
      }
    }

    .common-chart {
      display: flex;
      margin-right: 10px;
      margin-bottom: 10px;
      border: 2px solid transparent;
      border-radius: 2px;
      box-shadow: 0px 1px 2px 0px rgba(0, 0, 0, 0.1);

      &.scroll-in {
        /* stylelint-disable-next-line declaration-no-important */
        border-color: #3a84ff !important;
      }

      &.has-child {
        padding-right: 0;
        background: transparent;
        box-shadow: none;
      }

      .child-wrapper {
        display: flex;
        width: 100%;
        margin: -10px;

        .child-chart {
          display: flex;
          flex: 1;
          height: 100px;
          padding: 10px;
          margin-right: -10px;
          background: white;
          border: 0;
          border-radius: 2px;
          box-shadow: 0px 1px 2px 0px rgba(0, 0, 0, 0.1);

          &:first-child {
            margin-right: 10px;
          }
        }

        &.column-wrapper {
          flex-direction: column;

          .child-chart {
            &:first-child {
              margin-right: -10px;
              margin-bottom: 10px;
            }
          }
        }
      }
    }

    .collect-wrapper {
      position: relative;
      // border: 1px solid transparent;
      &:hover {
        box-shadow: 0px 2px 2px 0px rgba(0, 0, 0, 0.1);

        .collect-wrapper-mark {
          display: block;
        }
      }

      /* stylelint-disable-next-line no-descending-specificity */
      &-mark {
        position: absolute;
        top: 0;
        right: 0;
        display: none;
        border-color: #dcdee5 #dcdee5 transparent transparent;
        border-style: solid;
        border-width: 12px;
        border-radius: 2px;

        &::after {
          position: absolute;
          top: -12px;
          right: -9px;
          width: 4px;
          height: 8px;
          content: ' ';
          border-right: 2px solid white;
          border-bottom: 2px solid white;
          transform: rotate(45deg) scaleY(1);
        }
      }

      &.is-collect {
        box-shadow: 0px 1px 2px 0px rgba(0, 0, 0, 0.1);

        .collect-wrapper-mark {
          display: block;
          border-color: #3a84ff #3a84ff transparent transparent;
          border-width: 12px;

          &::after {
            top: -10px;
            right: -8px;
          }
        }
      }
    }
  }

  .total-tips {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 0 10px 0;
    font-size: 12px;
    line-height: 20px;

    .split-btn-wrapper {
      display: flex;
      align-items: center;

      .btn-text {
        margin-right: 7px;
      }
    }

    .tips-text {
      .add-strategy-btn {
        color: #3a84ff;
        cursor: pointer;
      }
    }
  }

  :deep(.monitor-echart-wrap) .echart-header .sub-title {
    font-weight: normal;
  }
}
</style>
