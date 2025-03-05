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

import _ from 'lodash';
import { getCustomTsMetricGroups } from 'monitor-api/modules/scene_view_new';
import { makeMap } from 'monitor-common/utils/make-map';

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
  onChange: (value: {
    metricsList: TCustomTsMetricGroups['metric_groups'][number]['metrics'];
    commonDimensionList: TCustomTsMetricGroups['common_dimensions'];
  }) => void;
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
export default class IndexSelect extends tsc<IProps, IEmit> {
  @Prop({ type: String, default: '' }) readonly searchKey: IProps['searchKey'];

  commonDimensonList: Readonly<TCustomTsMetricGroups['common_dimensions']> = [];
  metricGroupList: Readonly<TCustomTsMetricGroups['metric_groups']> = [];
  renderMetricGroupList: Readonly<TCustomTsMetricGroups['metric_groups']> = [];
  localCheckedMetricNameList: string[] = [];
  isLoading = true;
  handleSearch = () => {};

  @Watch('searchKey', { immediate: true })
  searchKeyChange() {
    this.handleSearch();
  }

  async fetchData() {
    try {
      const result = await getCustomTsMetricGroups();
      this.metricGroupList = Object.freeze(result.metric_groups);
      this.commonDimensonList = Object.freeze(result.common_dimensions);
      this.renderMetricGroupList = this.metricGroupList;
      this.$emit('change', {
        metricsList: [],
        commonDimensionList: this.commonDimensonList,
      });
    } finally {
      this.isLoading = false;
    }
  }

  resetMetricChecked() {
    this.localCheckedMetricNameList = [];
    this.$emit('change', {
      metricsList: [],
      commonDimensionList: this.commonDimensonList,
    });
  }

  handleChange(value: string[]) {
    const metricKeyMap = makeMap(value);

    const result = this.metricGroupList.reduce<IMetric[]>((result, groupItem) => {
      groupItem.metrics.forEach(metricsItem => {
        if (metricKeyMap[metricsItem.metric_name]) {
          result.push(metricsItem);
        }
      });
      return result;
    }, []);

    this.$emit('change', {
      metricsList: result,
      commonDimensionList: this.commonDimensonList,
    });
  }

  created() {
    this.fetchData();
    this.handleSearch = _.throttle(() => {
      if (!this.searchKey) {
        this.renderMetricGroupList = this.metricGroupList;
        return;
      }
      const searchReg = new RegExp(encodeRegexp(this.searchKey), 'i');
      this.renderMetricGroupList = this.metricGroupList.reduce((result, metricGroupItem) => {
        if (searchReg.test(metricGroupItem.name)) {
          result.push(metricGroupItem);
        } else {
          const metricList = metricGroupItem.metrics.filter(metricItem => searchReg.test(metricItem.alias));
          if (metricList.length > 0) {
            result.push({
              ...metricGroupItem,
              metrics: metricList,
            });
          }
        }
        return result;
      }, []);
    }, 300);
  }

  render() {
    return (
      <div
        class='new-metric-view-metrics-group'
        v-bkloading={{ isLoading: this.isLoading }}
      >
        <bk-checkbox-group
          v-model={this.localCheckedMetricNameList}
          onChange={this.handleChange}
        >
          {this.renderMetricGroupList.map(groupItem => (
            <div
              key={groupItem.name}
              class='metrics-select-box'
            >
              <div class='metrics-select-item-header'>
                <i class='icon-monitor icon-mc-file-open' />
                {groupItem.name}
                <div class='metrics-select-item-header-count'>{groupItem.metrics.length}</div>
              </div>
              <div class='metrics-select-item-content'>
                {groupItem.metrics.map(metricsItem => (
                  <div
                    key={metricsItem.metric_name}
                    class='metrics-select-item-content-item'
                  >
                    <bk-checkbox value={metricsItem.metric_name}>{metricsItem.alias}</bk-checkbox>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </bk-checkbox-group>
        {!this.isLoading && this.metricGroupList.length < 1 && (
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
