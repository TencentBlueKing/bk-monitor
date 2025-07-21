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
import { Component, Watch, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import customEscalationViewStore from '@store/modules/custom-escalation-view';
import _ from 'lodash';
import { makeMap } from 'monitor-common/utils/make-map';

import { getCustomTsMetricGroups } from '../../../services/scene_view_new';
import RenderMetric from './render-metric';

import './render-metrics-group.scss';

export interface IMetric {
  alias: string;
  dimensions: {
    alias: string;
    name: string;
  }[];
  metric_name: string;
}

type TCustomTsMetricGroups = ServiceReturnType<typeof getCustomTsMetricGroups>;

interface IProps {
  searchKey?: string;
}
interface IEmit {
  onChange: (value: string[]) => void;
}

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

  isLoading = false;
  renderMetricGroupList: Readonly<TCustomTsMetricGroups['metric_groups']> = [];
  localCheckedMetricNameList: string[] = [];
  groupExpandMap: Readonly<Record<string, boolean>> = {};
  groupCheeckMap: Readonly<Record<string, boolean>> = {};
  handleSearch = () => {};

  get metricGroupList() {
    return customEscalationViewStore.metricGroupList;
  }

  get currentSelectedMetricNameList() {
    return customEscalationViewStore.currentSelectedMetricNameList;
  }

  @Watch('searchKey', { immediate: true })
  searchKeyChange() {
    this.handleSearch();
  }

  @Watch('currentSelectedMetricNameList', { immediate: true })
  currentSelectedMetricListChange() {
    this.groupCheeckMap = Object.freeze(makeMap(this.currentSelectedMetricNameList));
  }

  @Watch('metricGroupList', { immediate: true })
  metricGroupListChange() {
    this.renderMetricGroupList = Object.freeze(this.metricGroupList);
    if (this.renderMetricGroupList.length > 0) {
      this.groupExpandMap = Object.freeze({
        [this.metricGroupList[0].name]: true,
      });
    }
  }

  async fetchData() {
    this.isLoading = true;
    try {
      const result = await getCustomTsMetricGroups({
        time_series_group_id: Number(this.$route.params.id),
      });
      customEscalationViewStore.updateCommonDimensionList(result.common_dimensions);
      customEscalationViewStore.updateMetricGroupList(result.metric_groups);
    } finally {
      this.isLoading = false;
    }
  }

  // 实例方法
  resetMetricChecked() {
    this.groupCheeckMap = {};
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

  triggerChange() {
    const currentSelectedMetricNameList = Object.keys(this.groupCheeckMap);
    customEscalationViewStore.updateCurrentSelectedMetricNameList(currentSelectedMetricNameList);
    this.$emit('change', currentSelectedMetricNameList);
  }

  handleGroupToggleExpand(metricGroupName: string) {
    const latestGroupFlodMap = { ...this.groupExpandMap };
    latestGroupFlodMap[metricGroupName] = !latestGroupFlodMap[metricGroupName];
    this.groupExpandMap = Object.freeze(latestGroupFlodMap);
  }

  handleGroupChecked(checked: boolean, group: TCustomTsMetricGroups['metric_groups'][number]) {
    const latestGroupCheeckMap = { ...this.groupCheeckMap };
    for (const metricItem of group.metrics) {
      if (checked) {
        latestGroupCheeckMap[metricItem.metric_name] = true;
      } else {
        delete latestGroupCheeckMap[metricItem.metric_name];
      }
    }
    this.groupCheeckMap = Object.freeze(latestGroupCheeckMap);
    this.triggerChange();
  }

  handleMetricSelectChange(
    checked: boolean,
    metricData: TCustomTsMetricGroups['metric_groups'][number]['metrics'][number]
  ) {
    const latestGroupCheeckMap = { ...this.groupCheeckMap };
    if (checked) {
      latestGroupCheeckMap[metricData.metric_name] = true;
    } else {
      delete latestGroupCheeckMap[metricData.metric_name];
    }
    this.groupCheeckMap = Object.freeze(latestGroupCheeckMap);
    this.triggerChange();
  }

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
      const isChecked = _.every(groupItem.metrics, item => this.groupCheeckMap[item.metric_name]);
      const isIndeterminateChecked = isChecked
        ? false
        : _.some(groupItem.metrics, item => this.groupCheeckMap[item.metric_name]);

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
              {groupItem.name}
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
                key={metricsItem.metric_name}
                checked={this.groupCheeckMap[metricsItem.metric_name]}
                data={metricsItem}
                onCheckChange={(value: boolean) => this.handleMetricSelectChange(value, metricsItem)}
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
