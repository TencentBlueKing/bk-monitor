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
import { Component, InjectReactive, Vue } from 'vue-property-decorator';
import dayjs from 'dayjs';
import { toPng } from 'html-to-image';
import { getDataSourceConfig } from 'monitor-api/modules/grafana';
import { deepClone } from 'monitor-common/utils/utils';
import { TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import { handleTimeRange, ILogUrlParams, transformLogUrlQuery } from 'monitor-pc/utils';

import { IExtendMetricData, IViewOptions, PanelModel } from '../typings';
import { downFile, filterDictConvertedToWhere, queryConfigTransform, reviewInterval } from '../utils';
import { VariablesService } from '../utils/variable';

function removeUndefined(obj) {
  Object.keys(obj).forEach(key => {
    const value = obj[key];
    if (typeof value === 'object') {
      // 如果属性值为对象或数组，则递归调用该函数
      removeUndefined(value);
    } else if (value === undefined || (Array.isArray(obj) && value === 'undefined')) {
      // 如果属性值为undefined，则删除该属性
      if (Array.isArray(obj)) {
        const delIndex = obj.findIndex(v => v === value);
        if (delIndex > -1) {
          obj.splice(delIndex, 1);
        }
      } else {
        delete obj[key];
      }
    }
  });
  return obj; // 返回处理后的对象
}

@Component
export default class ToolsMixin extends Vue {
  // 图表的数据时间间隔
  @InjectReactive('timeRange') readonly toolTimeRange!: TimeRangeType;
  /**
   * @description: 下载图表为png图片
   * @param {string} title 图片标题
   * @param {HTMLElement} targetEl 截图目标元素 默认组件$el
   * @param {*} customSave 自定义保存图片
   */
  handleStoreImage(title: string, targetEl?: HTMLElement, customSave = false) {
    const el = targetEl || (this.$el as HTMLElement);
    return toPng(el)
      .then(dataUrl => {
        if (customSave) return dataUrl;
        downFile(dataUrl, `${title}.png`);
      })
      .catch(() => {});
  }

  /**
   * @description: 查看大图
   * @param {PanelModel} panel 图表配置信息
   */
  handleFullScreen(panel: PanelModel, compareValue?: any) {
    this.$emit('fullScreen', panel, compareValue);
  }
  /**
   * @description: 保存到仪表盘
   * @param {*}
   * @return {*}
   */
  handleCollectChart() {
    this.$emit('collectChart');
  }

  /**
   * @description: 跳转到检索
   * @param {PanelModel} panel 图表数据
   * @param {IViewOptions} scopedVars 变量值
   * @param {Boolean} autoNavTo 是否自动导航到检索 默认为true, 否则返回对应的targets
   * @return {*}
   */
  handleExplore(panel: PanelModel, scopedVars: IViewOptions & Record<string, any>, autoNavTo = true) {
    const targets: PanelModel['targets'] = JSON.parse(JSON.stringify(panel.targets));
    const variablesService = new VariablesService(scopedVars);
    const alertFilterable = panel.options?.alert_filterable;
    // 事件检索
    if (alertFilterable && alertFilterable.filter_type === 'event') {
      const {
        // eslint-disable-next-line @typescript-eslint/naming-convention
        bcs_cluster_id,
        // eslint-disable-next-line @typescript-eslint/naming-convention
        data_source_label,
        // eslint-disable-next-line @typescript-eslint/naming-convention
        data_type_label,
        where
      } = variablesService.transformVariables(panel.options.alert_filterable.data);
      const query = {
        result_table_id: '',
        data_source_label,
        data_type_label,
        where
      };
      getDataSourceConfig({
        data_source_label,
        data_type_label
      }).then(res => {
        query.result_table_id = res.find(item => item.name.includes(bcs_cluster_id))?.id;
        const url = `${location.origin}${location.pathname.toString().replace('fta/', '')}?bizId=${
          panel.targets?.[0]?.data?.bk_biz_id || panel.bk_biz_id || this.$store.getters.bizId
        }#/data-retrieval/?queryConfig=${encodeURIComponent(JSON.stringify(query))}&from=${this.toolTimeRange[0]}&to=${
          this.toolTimeRange[1]
        }&timezone=${(this as any).timezone || window.timezone}`;
        window.open(url);
      });
      return;
    }
    targets.forEach(target => {
      target.data.query_configs =
        target?.data?.query_configs.map(queryConfig =>
          queryConfigTransform(variablesService.transformVariables(queryConfig), scopedVars)
        ) || [];
    });
    /** 判断跳转日志检索 */
    const isLog = targets.some(item =>
      item.data.query_configs.some(set => set.data_source_label === 'bk_log_search' && set.data_type_label === 'log')
    );
    if (!autoNavTo) return targets;
    if (isLog) {
      const { startTime, endTime } = handleTimeRange((this as any).timeRange);
      const queryConfig = targets[0].data.query_configs[0];
      const retrieveParams: ILogUrlParams = {
        // 检索参数
        bizId: `${this.$store.getters.bizId}`,
        keyword: queryConfig.query_string, // 搜索关键字
        addition: queryConfig.where || [],
        start_time: startTime * 1000,
        end_time: endTime * 1000,
        time_range: 'customized'
      };
      const indexSetId = queryConfig.index_set_id;
      // eslint-disable-next-line vue/max-len
      const queryStr = transformLogUrlQuery(retrieveParams);
      const url = `${this.$store.getters.bkLogSearchUrl}#/retrieve/${indexSetId}${queryStr}`;
      window.open(url);
    } else {
      const url = `${location.origin}${location.pathname.toString().replace('fta/', '')}?bizId=${
        panel.targets?.[0]?.data?.bk_biz_id || panel.bk_biz_id || this.$store.getters.bizId
      }#/data-retrieval/?targets=${encodeURIComponent(JSON.stringify(removeUndefined(targets)))}&from=${
        this.toolTimeRange[0]
      }&to=${this.toolTimeRange[1]}&timezone=${(this as any).timezone || window.timezone}`;
      window.open(url);
    }
  }

  /**
   * @description: 跳转到策略
   * @param {PanelModel} panel
   * @param {IExtendMetricData} metric
   * @param {IViewOptions} viewOptions
   * @param {*} isAll
   * @return {*}
   */
  handleAddStrategy(
    panel: PanelModel,
    metric: IExtendMetricData,
    scopedVars: IViewOptions & Record<string, any>,
    isAll = false
  ) {
    try {
      let result: any = null;
      const targets: PanelModel['targets'] = JSON.parse(JSON.stringify(panel.targets));
      const [startTime, endTime] = handleTransformToTimestamp(this.toolTimeRange as any);
      const interval = reviewInterval(
        scopedVars.interval,
        dayjs.tz(endTime).unix() - dayjs.tz(startTime).unix(),
        panel.collect_interval
      );
      const variablesService = new VariablesService({ ...scopedVars, interval });
      if (isAll) {
        result = {
          expression: '',
          query_configs: []
        };
        targets.forEach(target => {
          target.data?.query_configs?.forEach(queryConfig => {
            const resultMetrics = result.query_configs.map(item => item.metrics[0].field);
            if (!resultMetrics.includes(queryConfig.metrics[0].field)) {
              let config = deepClone(queryConfig);
              config = variablesService.transformVariables(config);
              result.query_configs.push({ ...queryConfigTransform(filterDictConvertedToWhere(config), scopedVars) });
            }
          });
        });
      } else {
        targets.forEach(target => {
          target.data?.query_configs?.forEach(queryConfig => {
            if (queryConfig.metrics.map(item => item.field).includes(metric.metric_field) && !result) {
              let config = deepClone(queryConfig);
              config = variablesService.transformVariables(config);
              result = {
                ...target.data,
                query_configs: [queryConfigTransform(filterDictConvertedToWhere(config), scopedVars)]
              };
            }
          });
        });
      }
      const url = `${location.origin}${location.pathname.toString().replace('fta/', '')}?bizId=${
        panel.targets?.[0]?.data?.bk_biz_id || panel.bk_biz_id || this.$store.getters.bizId
      }#/strategy-config/add/?data=${JSON.stringify(result)}&from=${this.toolTimeRange[0]}&to=${
        this.toolTimeRange[1]
      }&timezone=${(this as any).timezone || window.timezone}`;
      window.open(url);
    } catch (e) {
      console.info(e);
    }
  }
}
