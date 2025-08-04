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
import { Component, InjectReactive, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';
import { fetchAiSetting } from 'monitor-api/modules/aiops';
import { isShadowEqual, reviewInterval } from 'monitor-ui/chart-plugins/utils';
import { VariablesService } from 'monitor-ui/chart-plugins/utils/variable';
import { type FormattedValue, getValueFormat } from 'monitor-ui/monitor-echarts/valueFormats';

import { handleTransformToTimestamp } from '../../../../components/time-range/utils';
import ViewDetail from '../../../view-detail/view-detail-new';

import type { TimeRangeType } from '../../../../components/time-range/time-range';
import type { IQueryOption } from '../../../performance/performance-type';
import type { PanelToolsType } from '../../typings/panel-tools';
import type { IViewOptions, PanelModel } from 'monitor-ui/chart-plugins/typings';

import './ai-panel.scss';

interface IAiPanelResData {
  anomaly_info: Omit<IAiPanelTableItem, 'name'>[];
  metrics: {
    data_source_label: string;
    data_type_label: string;
    metric_field: string;
    metric_field_name: string;
    metric_id: string;
    result_table_id: string;
    unit?: string;
  }[];
}
interface IAiPanelTableItem {
  dtEventTime: number | string;
  id?: string;
  metric_id?: string;
  name: string;
  panel?: any;
  score: number;
  value: number | string;
}
interface ICommonListProps {
  allPanelId?: string[];
  // panel实例
  panel: PanelModel;
}

@Component
export default class Aipanel extends tsc<ICommonListProps> {
  @Prop({ type: Object }) panel: PanelModel;
  @Prop({ type: String }) text: string;
  @Prop({ type: String }) tips: string;
  // 所有的图表id
  @Prop({ default: () => [], type: Array }) allPanelId: string[];
  // 当前场景id
  @Prop({ default: '', type: String }) sceneId: string;
  @Ref('table') tableRef: any;
  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;
  @InjectReactive('viewOptions') readonly viewOptions!: IViewOptions;
  // 图表刷新间隔
  @InjectReactive('refreshInterval') readonly refreshInterval!: number;
  // 时间对比的偏移量
  @InjectReactive('timeOffset') readonly timeOffset: string[];
  // 对比类型
  @InjectReactive('compareType') compareType: PanelToolsType.CompareId;
  cancelToken = null;
  // 表格数据
  tableData: IAiPanelTableItem[] = [];
  filtersData = {};
  // 历史parmas
  oldParams = null;

  showViewDetail = false;
  viewConfig = null;

  aiSettings = null;

  // scoped 变量
  get scopedVars() {
    return {
      ...(this.viewOptions || {}),
      ...(this.viewOptions?.filters || {}),
      ...(this.viewOptions?.current_target || []),
    };
  }

  /* 异常指标筛选 */
  get nameFilterOptions() {
    const map = new Map();
    return this.tableData.reduce((total, item) => {
      if (!map.get(item.name)) {
        total.push({
          text: item.name,
          value: item.name,
        });
        map.set(item.name, true);
      }
      return total;
    }, []);
  }

  get filterTabelData() {
    return this.tableData.filter(item => {
      const filterList = Object.entries(this.filtersData);
      const isFilter = filterList.length
        ? filterList.every(filter => {
            const [key, values] = filter as any;
            const itemValue = item[key];
            if (Array.isArray(itemValue)) {
              // 数组类型
              const itemValues = itemValue.map(item => item.id);
              return itemValues.some(val => values.includes(val));
            } // 非数组
            return values.includes(itemValue);
          })
        : true;
      return isFilter;
    });
  }

  /** 对比工具栏数据 */
  get compareValue(): IQueryOption {
    return {
      compare: {
        type: this.compareType !== 'time' ? 'none' : this.compareType,
        value: this.compareType === 'time' ? this.timeOffset : '',
      },
      tools: {
        timeRange: this.timeRange,
        refreshInterval: this.refreshInterval,
        searchValue: [],
      },
    };
  }

  /** 是否开启主机智能异常检测 */
  get isOpenDetection() {
    return this.aiSettings?.multivariate_anomaly_detection?.host?.is_enabled;
  }

  mounted() {
    this.getAiSettings();
  }

  async getAiSettings() {
    this.aiSettings = await fetchAiSetting().catch(() => null);
  }

  @Watch('timeRange')
  // 数据时间间隔
  handleTimeRangeChange() {
    this.getPanelData();
  }

  @Watch('viewOptions')
  // 用于配置后台图表数据的特殊设置
  handleFieldDictChange(val: IViewOptions, old: IViewOptions) {
    if (!this.panel || !val) return;
    if (JSON.stringify(val) === JSON.stringify(old)) return;
    if (isShadowEqual(val, old)) return;
    this.cancelToken?.();
    this.getPanelData();
  }

  @Watch('panel', { immediate: true })
  handlePanelChange(val: PanelModel, old: PanelModel | undefined) {
    if (val && JSON.stringify(val) !== JSON.stringify(old)) {
      if (isShadowEqual(val, old)) return;
      this.cancelToken?.();
      this.getPanelData();
    }
  }

  async getPanelData() {
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const variablesService = new VariablesService(this.scopedVars);
    const [target] = this.panel.targets;
    const { apiFunc, apiModule } = target;
    const params = {
      ...variablesService.transformVariables(target.data),
      start_time: startTime,
      end_time: endTime,
    };
    if (this.oldParams && isShadowEqual(params, this.oldParams)) {
      return;
    }
    this.oldParams = params;
    const data: IAiPanelResData = await this.$api[apiModule][apiFunc](params).catch(() => ({}));
    if (data?.metrics?.length) {
      this.tableData = data.anomaly_info.map(info => {
        const metric = data.metrics.find(item => item.metric_id === info.metric_id);
        let { value } = info;
        if (metric?.unit) {
          const unitFormatter = getValueFormat(metric?.unit);
          const set: FormattedValue = unitFormatter(+value);
          value = set.text + (set.suffix || '');
        }
        return {
          ...info,
          name: metric.metric_field_name,
          value,
          id: `${metric.data_source_label}.${metric.data_type_label}.${metric.result_table_id}.${metric.metric_field}`,
          score: +info.score.toFixed(4),
          dtEventTime: dayjs.tz(info.dtEventTime).format('YYYY-MM-DD HH:mm:ss'),
        };
      });
    } else {
      this.tableData = [];
    }
  }
  handlerGoAiSettings() {
    this.$router.push({ name: 'ai-settings' });
  }
  handleSetMetricIndex(row: IAiPanelTableItem) {
    if (this.allPanelId.includes(row.id)) {
      const dom = document.getElementById(`${row.id}__key__`);
      dom?.scrollIntoView();
    } else {
      // 如视图没有此图表则打开大图
      if (row.panel) {
        let copyPanel = JSON.parse(JSON.stringify(row.panel));
        const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
        const variablesService = new VariablesService({
          ...this.viewOptions.filters,
          ...(this.viewOptions.filters?.current_target || {}),
          ...this.viewOptions,
          ...this.viewOptions.variables,
          interval: reviewInterval(
            this.viewOptions.interval,
            dayjs.tz(endTime).unix() - dayjs.tz(startTime).unix(),
            row.panel.collect_interval
          ),
        });
        copyPanel = variablesService.transformVariables(copyPanel);
        copyPanel.targets.forEach((t, tIndex) => {
          const queryConfigs = row.panel.targets[tIndex].data.query_configs;
          t.data.query_configs.forEach((q, qIndex) => {
            q.functions = JSON.parse(JSON.stringify(queryConfigs[qIndex].functions));
          });
        });
        this.viewConfig = {
          config: copyPanel,
          compareValue: JSON.parse(JSON.stringify(this.compareValue)),
        };
        this.showViewDetail = true;
      }
    }
  }

  handleCloseViewDetail() {
    this.showViewDetail = false;
    this.viewConfig = null;
  }

  handleToAddStrategy() {
    window.open(`${location.href.replace(location.hash, '#/strategy-config/add')}?scene_id=${this.sceneId}`);
  }

  handleToOpen() {
    this.$router.push({
      name: 'ai-settings-set',
    });
  }

  /** 主机智能异常检测结果 */
  renderResultContent() {
    if (!this.isOpenDetection)
      return (
        <bk-exception
          class='no-data'
          scene='part'
          type='empty'
        >
          <div class='no-data-text'>{this.$t('暂未开启主机智能异常检测')}</div>
          <bk-button
            class='open-btn'
            title='primary'
            text
            onClick={this.handleToOpen}
          >
            {this.$t('前往开启')}
          </bk-button>
        </bk-exception>
      );

    if (this.tableData.length)
      return (
        <div class='ai-panel-list'>
          {this.tableData.map(item => (
            <div
              class='ai-panel-list-item'
              v-bk-tooltips={{
                content: item.id,
                placements: ['left'],
                allowHTML: false,
              }}
              onClick={() => this.handleSetMetricIndex(item)}
            >
              <div class='metric-name'>{item.name}</div>
              <div class='count-info'>
                <div class='left'>{`${this.$t('指标值')}: ${item.value}`}</div>
                <div class='right'>
                  <span>{this.$t('异常得分')}: </span>
                  <span class='red'>{Number(item.score || 0).toFixed(2)}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      );

    return (
      <div class='no-data'>
        <div class='no-data-img' />
        <div class='no-data-text'>{this.$t('智能检测一切正常')}</div>
      </div>
    );
  }

  render() {
    return (
      <div class='ai-panel-component'>
        <div class='ai-panel-title'>
          {this.$t('主机智能异常检测结果')}
          <i
            class='icon-monitor icon-hint'
            v-bk-tooltips={{
              content: this.$t('异常分值范围从0～1，越大越异常'),
              placements: ['top'],
            }}
          />
          <span
            class='icon-monitor icon-mc-add-strategy'
            v-bk-tooltips={{
              content: this.$t('添加策略'),
              delay: 200,
            }}
            onClick={this.handleToAddStrategy}
          />
          <i
            class='bk-icon icon-cog-shape setting-icon'
            v-bk-tooltips={{
              content: this.$t('AI设置'),
              delay: 200,
            }}
            onClick={this.handlerGoAiSettings}
          />
        </div>
        {this.tableData?.length > 0 && (
          <div class='ai-panel-subtitle'>
            {this.$t('最后一次异常时间')}： {this.tableData[0]?.dtEventTime}
          </div>
        )}
        {this.renderResultContent()}
        {this.showViewDetail && (
          <ViewDetail
            show={this.showViewDetail}
            viewConfig={this.viewConfig}
            on-close-modal={this.handleCloseViewDetail}
          />
        )}
      </div>
    );
  }
}
