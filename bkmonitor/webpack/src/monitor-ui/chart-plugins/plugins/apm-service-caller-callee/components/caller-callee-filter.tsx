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

/** 主被调 - 左侧筛选 */
import { Component, Prop, Emit, InjectReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getFieldOptionValues } from 'monitor-api/modules/apm_metric';
import { Debounce } from 'monitor-common/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import { reviewInterval } from '../../../utils';
import { VariablesService } from '../../../utils/variable';
import { SYMBOL_LIST } from '../utils';

import type { PanelModel } from '../../../typings';
import type { CallOptions, IFilterData } from '../type';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import type { IViewOptions } from 'monitor-ui/chart-plugins/typings';

import './caller-callee-filter.scss';

interface ICallerCalleeFilterProps {
  panel: PanelModel;
  activeKey?: string;
}
interface ICallerCalleeFilterEvent {
  onReset?: () => void;
  onSearch?: (options: CallOptions['call_filter']) => void;
}
@Component({
  name: 'CallerCalleeFilter',
  components: {},
})
export default class CallerCalleeFilter extends tsc<ICallerCalleeFilterProps, ICallerCalleeFilterEvent> {
  @Prop({ required: true, type: Object }) panel: PanelModel;
  @Prop({ required: true, type: String, default: '' }) activeKey: string;

  @InjectReactive('viewOptions') readonly viewOptions!: IViewOptions;
  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;
  @InjectReactive('callOptions') readonly callOptions!: CallOptions;

  symbolList = SYMBOL_LIST;
  toggleKey = '';
  isLoading = false;
  filterData: IFilterData;
  filterTags = {};
  @Watch('activeKey', { immediate: true })
  handlePanelChange() {
    this.handleSearch();
  }
  @Emit('search')
  handleSearch() {
    const filter = (this.filterData[this.activeKey] || []).filter(item => item.value.length > 0);
    return this.handleRegData(filter);
  }

  @Emit('reset')
  handleReset() {
    const data = (this.filterData[this.activeKey] || []).map(item => Object.assign(item, { method: 'eq', value: [] }));
    this.filterData[this.activeKey] = data;
  }
  changeSelect(val, item) {
    return { val, item };
  }
  handleToggle(isOpen: boolean, key: string) {
    this.searchToggle({ isOpen, key });
    this.toggleKey = key;
  }
  get commonOptions() {
    return this.panel?.options?.common || {};
  }

  get variablesData() {
    return this.commonOptions?.variables?.data || {};
  }
  get angleData() {
    return this.commonOptions?.angle || {};
  }
  mounted() {
    this.initDefaultData();
  }
  initDefaultData() {
    const callFilter = this.callOptions.call_filter || [];
    if (callFilter.length > 0) {
      callFilter.map(item => this.handleToggle(true, item.key));
    }
    const { caller, callee } = this.angleData;
    const createFilterData = tags =>
      (tags || []).map(item => {
        const def = callFilter.find(ele => item.value === ele.key);
        if (def?.value && def.method === 'reg') {
          const firstValue = def.value[0];

          if (firstValue.startsWith('.*') || firstValue.endsWith('.*')) {
            def.method = firstValue.startsWith('.*') ? 'after_req' : 'before_req';
            def.value = def.value.map(item => item.replace(/^\.\*|\.\*$/g, ''));
          }
        }
        return {
          key: item.value,
          method: def?.method || 'eq',
          value: def?.value || [],
          condition: 'and',
        };
      });
    const createFilterTags = tags => (tags || []).map(item => ({ ...item, values: [] }));

    // 使用通用函数生成数据
    this.filterData = {
      caller: createFilterData(caller?.tags),
      callee: createFilterData(callee?.tags),
    };

    this.filterTags = {
      caller: createFilterTags(caller?.tags),
      callee: createFilterTags(callee?.tags),
    };
  }

  handleRegData(filter) {
    /** 前端处理数据：
     * 前匹配：调用后台、跳转数据检索时补成 example.*
     * 后匹配：调用后台、跳转数据检索时补成 .*example
     * */
    const updatedFilter = filter.map(item => {
      if (item.method === 'before_req' || item.method === 'after_req') {
        const prefix = item.method === 'before_req' ? '' : '.*';
        const suffix = item.method === 'before_req' ? '.*' : '';
        return {
          ...item,
          value: item.value.map(value => `${prefix}${value}${suffix}`),
          method: 'reg',
        };
      }
      return item;
    });
    return updatedFilter;
  }
  /** 动态获取左侧列表的下拉值 */
  @Debounce(300)
  searchToggle({ isOpen, key }) {
    if (!isOpen) {
      return;
    }
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const filter = (this.filterData[this.activeKey] || []).filter(item => item.value.length > 0);
    const interval = reviewInterval(this.viewOptions.interval, endTime - startTime, this.panel.collect_interval);
    const variablesService = new VariablesService({
      ...this.viewOptions,
      interval,
      ...this.callOptions,
    });
    const params = {
      start_time: startTime,
      end_time: endTime,
      field: key,
    };
    const newParams = {
      ...variablesService.transformVariables(this.variablesData, {
        ...this.viewOptions,
        interval,
      }),
      ...params,
    };
    newParams.where = [...newParams.where, ...this.handleRegData(filter)];
    this.isLoading = true;
    getFieldOptionValues(newParams)
      .then(res => {
        this.isLoading = false;
        const newFilter = this.filterTags[this.activeKey].map(item =>
          item.value === key ? { ...item, values: res } : item
        );
        this.$set(this.filterTags, this.activeKey, newFilter);
      })
      .catch(() => (this.isLoading = false));
  }
  render() {
    return (
      <div class='caller-callee-filter'>
        <div class='search-title'>{this.$t('筛选')}</div>
        <div class='search-main'>
          {(this.filterTags[this.activeKey] || []).map((item, ind) => {
            return (
              <div
                key={item.value}
                class='search-item'
              >
                <div class='search-item-label'>
                  <span>{item.text}</span>
                  {this.filterData[this.activeKey][ind] && (
                    <bk-select
                      class='item-label-select'
                      v-model={this.filterData[this.activeKey][ind].method}
                      clearable={false}
                      list={this.symbolList}
                      size='small'
                      onChange={val => this.changeSelect(val, item)}
                    >
                      {this.symbolList.map(opt => (
                        <bk-option
                          id={opt.value}
                          key={opt.value}
                          name={opt.label}
                        />
                      ))}
                    </bk-select>
                  )}
                </div>
                {this.filterData[this.activeKey][ind] && (
                  <bk-select
                    v-model={this.filterData[this.activeKey][ind].value}
                    loading={item.value === this.toggleKey && this.isLoading}
                    placeholder={item.text}
                    allow-create
                    collapse-tag
                    display-tag
                    multiple
                    onToggle={(val: boolean) => this.handleToggle(val, item.value)}
                  >
                    {(item.values || []).map(opt => (
                      <bk-option
                        id={opt.value}
                        key={opt.value}
                        name={opt.value}
                      />
                    ))}
                  </bk-select>
                )}
              </div>
            );
          })}
        </div>
        <div class='search-btn-group'>
          <bk-button
            theme='primary'
            onClick={this.handleSearch}
          >
            {this.$t('查询')}
          </bk-button>
          <bk-button onClick={this.handleReset}>{this.$t('重置')}</bk-button>
        </div>
      </div>
    );
  }
}
