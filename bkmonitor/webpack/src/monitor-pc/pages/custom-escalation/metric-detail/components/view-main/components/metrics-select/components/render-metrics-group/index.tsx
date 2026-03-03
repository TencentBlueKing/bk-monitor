/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { Component, InjectReactive, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import _ from 'lodash';
import { makeMap } from 'monitor-common/utils/make-map';
import customEscalationViewStore from 'monitor-pc/store/modules/custom-escalation-view';

import RenderMetric from './render-metric';

import type { RequestHandlerMap } from '../../../../../../type';

import './index.scss';

export interface IMetric {
  alias: string;
  metric_name: string;
  dimensions: {
    alias: string;
    name: string;
  }[];
}

interface GroupItem {
  groupName: string;
  metricsCheckMap: Record<string, boolean>;
}

interface IEmit {
  onChange: (value: string[]) => void;
}

interface IProps {
  searchKey?: string;
}
type TCustomTsMetricGroups = ServiceReturnType<RequestHandlerMap['getCustomTsMetricGroups']>;

/**
 * @desc 正则表达式关键字符转换
 * @param { String } paramStr
 * @returns { String }
 */
export const encodeRegexp = (paramStr: string) => {
  const regexpKeyword = ['\\', '.', '*', '-', '{', '}', '[', ']', '^', '(', ')', '$', '+', '?', '|'];
  const res = regexpKeyword.reduce(
    (result, charItem) => result.replace(new RegExp(`\\${charItem}`, 'g'), `\\${charItem}`),
    paramStr
  );
  return res;
};

@Component
export default class RenderMetricsGroup extends tsc<IProps, IEmit> {
  @Prop({ type: String, default: '' }) readonly searchKey: IProps['searchKey'];
  @InjectReactive('requestHandlerMap') readonly requestHandlerMap!: RequestHandlerMap;
  @InjectReactive('timeSeriesGroupId') readonly timeSeriesGroupId: number;
  @InjectReactive('isApm') readonly isApm: boolean;
  @InjectReactive('appName') readonly appName: string;
  @InjectReactive('serviceName') readonly serviceName: string;

  isLoading = false;
  renderMetricGroupList: Readonly<TCustomTsMetricGroups['metric_groups']> = [];
  localCheckedMetricNameList: string[] = [];
  groupExpandMap: Readonly<Record<string, boolean>> = {};
  // groupCheeckMap: Readonly<Record<string, boolean>> = {};
  cheeckedMap: GroupItem[] = [];
  handleSearch = () => {};

  get metricGroupList() {
    return customEscalationViewStore.metricGroupList;
  }

  // get currentSelectedMetricNameList() {
  //   return customEscalationViewStore.currentSelectedMetricNameList;
  // }

  // 选中的指标和归属分组名称列表
  get currentSelectedGroupAndMetricNameList() {
    return customEscalationViewStore.currentSelectedGroupAndMetricNameList;
  }

  // 默认分组名称。其他地方也有使用默认分组，但英文翻译与此处不同
  get defaultGroupNameMap() {
    return window.i18n.locale === 'zhCN' ? '默认分组' : 'Default';
  }

  @Watch('searchKey', { immediate: true })
  searchKeyChange() {
    this.handleSearch();
  }

  // @Watch('currentSelectedMetricNameList', { immediate: true })
  // currentSelectedMetricListChange() {
  //   this.groupCheeckMap = Object.freeze(makeMap(this.currentSelectedMetricNameList));
  // }

  @Watch('currentSelectedGroupAndMetricNameList', { immediate: true })
  currentSelectedMetricListChange() {
    this.cheeckedMap = this.currentSelectedGroupAndMetricNameList.map(group => {
      return {
        groupName: group.groupName,
        metricsCheckMap: Object.freeze(makeMap(group.metricsName)),
      };
    });
  }

  @Watch('metricGroupList', { immediate: true })
  metricGroupListChange(newV, oldV) {
    this.renderMetricGroupList = Object.freeze(newV);
    // 初始化时默认选中第一个分组的第一个指标
    if (!oldV?.length && newV.length > 0) {
      this.groupExpandMap = Object.freeze({
        [this.metricGroupList[0].name]: true,
      });
    }
  }

  async fetchData() {
    this.isLoading = true;
    try {
      const params = {
        time_series_group_id: Number(this.timeSeriesGroupId),
      };
      if (this.isApm) {
        delete params.time_series_group_id;
        Object.assign(params, {
          apm_app_name: this.appName,
          apm_service_name: this.serviceName,
        });
      }
      const result = await this.requestHandlerMap.getCustomTsMetricGroups(params);
      customEscalationViewStore.updateMetricGroupList(result.metric_groups);
    } finally {
      this.isLoading = false;
    }
  }

  // 实例方法
  resetMetricChecked() {
    this.cheeckedMap = [];
    this.triggerChange();
  }
  // 实例方法
  foldAll() {
    const latestGroupFlodMap = { ...this.groupExpandMap };
    for (const item of this.renderMetricGroupList) {
      latestGroupFlodMap[item.name] = false;
    }
    this.groupExpandMap = Object.freeze(latestGroupFlodMap);
  }
  expandAll(flag: boolean) {
    if (flag) {
      const latestGroupFlodMap = { ...this.groupExpandMap };
      for (const item of this.renderMetricGroupList) {
        latestGroupFlodMap[item.name] = true;
      }
      this.groupExpandMap = Object.freeze(latestGroupFlodMap);
    } else {
      this.groupExpandMap = {};
    }
  }

  // triggerChange() {
  //   const currentSelectedMetricNameList = Object.keys(this.groupCheeckMap);
  //   customEscalationViewStore.updateCurrentSelectedMetricNameList(currentSelectedMetricNameList);
  //   this.$emit('change', currentSelectedMetricNameList);
  // }
  triggerChange() {
    const currentSelectedGroupAndMetricNameList = this.cheeckedMap.reduce((acc, item) => {
      // metricsCheckMap是否有数据存在
      if (Object.keys(item.metricsCheckMap).length) {
        // 有效选中，累加
        acc.push({
          groupName: item.groupName,
          metricsName: Object.keys(item.metricsCheckMap),
        });
      }
      return acc;
    }, []);
    customEscalationViewStore.updateCurrentSelectedGroupAndMetricNameList(currentSelectedGroupAndMetricNameList);
  }

  handleGroupToggleExpand(metricGroupName: string) {
    const latestGroupFlodMap = { ...this.groupExpandMap };
    latestGroupFlodMap[metricGroupName] = !latestGroupFlodMap[metricGroupName];
    this.groupExpandMap = Object.freeze(latestGroupFlodMap);
  }

  // 全选
  handleGroupChecked(checked: boolean, group: TCustomTsMetricGroups['metric_groups'][number]) {
    // 获取操作选中/取消的分组数据
    let handleTargetData = this.cheeckedMap.find(item => item.groupName === group.name);
    // 首次选中目标分组
    if (!handleTargetData) {
      this.cheeckedMap.push({
        groupName: group.name,
        metricsCheckMap: {},
      });
      handleTargetData = this.cheeckedMap[this.cheeckedMap.length - 1];
    }
    // 获取全选/反选分组数据下的选中映射数据
    const latestGroupCheeckMap = { ...handleTargetData.metricsCheckMap };
    for (const metricItem of group.metrics) {
      if (checked) {
        latestGroupCheeckMap[metricItem.metric_name] = true;
      } else {
        delete latestGroupCheeckMap[metricItem.metric_name];
      }
    }
    // 更新选中的数据
    handleTargetData.metricsCheckMap = Object.freeze(latestGroupCheeckMap);
    this.triggerChange();
  }

  // 单选
  handleMetricSelectChange(
    checked: boolean,
    groupName: string,
    metricData: TCustomTsMetricGroups['metric_groups'][number]['metrics'][number]
  ) {
    // 获取操作选中/取消的分组数据
    let handleTargetData = this.cheeckedMap.find(item => item.groupName === groupName);
    // 首次选中目标分组下的复选框
    if (!handleTargetData) {
      this.cheeckedMap.push({
        groupName,
        metricsCheckMap: {
          [metricData.metric_name]: checked,
        },
      });
      handleTargetData = this.cheeckedMap[this.cheeckedMap.length - 1];
    }
    // 获取全选/反选分组数据下的选中映射数据
    const latestGroupCheeckMap = { ...handleTargetData.metricsCheckMap };
    if (checked) {
      latestGroupCheeckMap[metricData.metric_name] = true;
    } else {
      delete latestGroupCheeckMap[metricData.metric_name];
    }
    handleTargetData.metricsCheckMap = Object.freeze(latestGroupCheeckMap);
    this.triggerChange();
  }

  // handleGroupChecked(checked: boolean, group: TCustomTsMetricGroups['metric_groups'][number]) {
  //   const latestGroupCheeckMap = { ...this.groupCheeckMap };
  //   for (const metricItem of group.metrics) {
  //     if (checked) {
  //       latestGroupCheeckMap[metricItem.metric_name] = true;
  //     } else {
  //       delete latestGroupCheeckMap[metricItem.metric_name];
  //     }
  //   }
  //   this.groupCheeckMap = Object.freeze(latestGroupCheeckMap);
  //   this.triggerChange();
  // }

  // handleMetricSelectChange(
  //   checked: boolean,
  //   metricData: TCustomTsMetricGroups['metric_groups'][number]['metrics'][number]
  // ) {
  //   const latestGroupCheeckMap = { ...this.groupCheeckMap };
  //   if (checked) {
  //     latestGroupCheeckMap[metricData.metric_name] = true;
  //   } else {
  //     delete latestGroupCheeckMap[metricData.metric_name];
  //   }
  //   this.groupCheeckMap = Object.freeze(latestGroupCheeckMap);
  //   this.triggerChange();
  // }

  created() {
    this.handleSearch = _.throttle(() => {
      if (!this.searchKey) {
        this.renderMetricGroupList = Object.freeze(this.metricGroupList);
        return;
      }
      const searchReg = new RegExp(encodeRegexp(this.searchKey), 'i');
      const filterResult = this.metricGroupList.reduce((result, metricGroupItem) => {
        if (searchReg.test(metricGroupItem.name)) {
          result.push(metricGroupItem);
        } else {
          const metricList = metricGroupItem.metrics.filter(
            metricItem => searchReg.test(metricItem.alias) || searchReg.test(metricItem.metric_name)
          );
          if (metricList.length > 0) {
            result.push({
              ...metricGroupItem,
              metrics: metricList,
            });
          }
        }
        return result;
      }, []);
      this.renderMetricGroupList = Object.freeze(filterResult);
    }, 100);
  }

  render() {
    const renderGroup = (groupItem: TCustomTsMetricGroups['metric_groups'][number]) => {
      // const isChecked = _.every(groupItem.metrics, item => this.groupCheeckMap[item.metric_name]);
      // const isIndeterminateChecked = isChecked
      //   ? false
      //   : _.some(groupItem.metrics, item => this.groupCheeckMap[item.metric_name]);

      let isChecked = false; // 是否全选
      let isIndeterminateChecked = false; // 是否半选
      const targetData = this.cheeckedMap.find(item => item.groupName === groupItem.name);
      if (targetData) {
        isChecked = _.every(groupItem.metrics, item => targetData.metricsCheckMap[item.metric_name]);
        isIndeterminateChecked = isChecked
          ? false
          : _.some(groupItem.metrics, item => targetData.metricsCheckMap[item.metric_name]);
      }

      return (
        <div
          key={groupItem.name}
          class='metrics-select-box'
        >
          <div class='metrics-select-item-header'>
            <div
              class={{
                'group-expand-flag': true,
                'is-expanded': this.groupExpandMap[groupItem.name],
              }}
              onClick={() => this.handleGroupToggleExpand(groupItem.name)}
            >
              <i
                style='font-size: 12px;'
                class='icon-monitor icon-mc-arrow-right'
              />
            </div>
            <bk-checkbox
              checked={isChecked}
              indeterminate={isIndeterminateChecked}
              onChange={(value: boolean) => this.handleGroupChecked(value, groupItem)}
            />
            <div
              class='metric-group-name'
              v-bk-overflow-tips
              onClick={() => this.handleGroupToggleExpand(groupItem.name)}
            >
              {groupItem.name === 'default' ? this.defaultGroupNameMap : groupItem.name}
            </div>
            <div class='metric-demension-count'>
              <div>{groupItem.metrics.length}</div>
            </div>
          </div>
          <div
            style={{
              display: this.groupExpandMap[groupItem.name] ? '' : 'none',
            }}
            class='metrics-select-item-content'
          >
            {groupItem.metrics.map(metricsItem => (
              <RenderMetric
                key={`${metricsItem.field_id}-${metricsItem.metric_name}`}
                checked={targetData?.metricsCheckMap[metricsItem.metric_name] || false}
                data={metricsItem}
                scopeId={groupItem.scope_id}
                scopeName={groupItem.name}
                onCheckChange={(value: boolean) => this.handleMetricSelectChange(value, groupItem.name, metricsItem)}
                onEditSuccess={this.fetchData}
              />
            ))}
          </div>
        </div>
      );
    };

    return (
      <div
        class='new-metric-view-metrics-group'
        v-bkloading={{ isLoading: this.isLoading }}
      >
        <div>{this.renderMetricGroupList.map(renderGroup)}</div>
        {this.metricGroupList.length < 1 && (
          <bk-exception
            scene='part'
            type='empty'
          />
        )}
        {this.searchKey && this.metricGroupList.length > 0 && this.renderMetricGroupList.length < 1 && (
          <bk-exception
            scene='part'
            type='search-empty'
          />
        )}
      </div>
    );
  }
}
