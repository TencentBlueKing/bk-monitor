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
import { Component, Emit, InjectReactive, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getFieldOptionValues } from 'monitor-api/modules/apm_metric';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import { VariablesService } from '../../../utils/variable';
import { type CallOptions, type IFilterCondition, type IFilterOption, type IListItem, EKind } from '../type';
import { SYMBOL_LIST } from '../utils';

import type { PanelModel } from '../../../typings';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import type { IViewOptions } from 'monitor-ui/chart-plugins/typings';

import './caller-callee-filter.scss';

interface ICallerCalleeFilterEvent {
  onReset?: () => void;
  onSearch?: (options: CallOptions['call_filter']) => void;
}
interface ICallerCalleeFilterProps {
  callOptions?: Partial<CallOptions>;
  callType?: EKind;
  panel: PanelModel;
}
const filterOption: IListItem = {
  text: '- 空 -',
  value: '',
};
@Component({
  name: 'CallerCalleeFilter',
  components: {},
})
export default class CallerCalleeFilter extends tsc<ICallerCalleeFilterProps, ICallerCalleeFilterEvent> {
  @Prop({ required: true, type: Object }) panel: PanelModel;
  @Prop({ required: true, type: Object }) callOptions: CallOptions;
  @Prop({ required: true, type: String, default: '' }) callType: EKind;

  @InjectReactive('viewOptions') viewOptions!: IViewOptions;
  @InjectReactive('timeRange') timeRange!: TimeRangeType;

  symbolList = SYMBOL_LIST;
  callerFilter: IFilterOption[] = [];
  calleeFilter: IFilterOption[] = [];
  callerNameMap: Record<string, string> = {};
  calleeNameMap: Record<string, string> = {};
  // 变量对应
  get scopedVars() {
    return {
      ...(this.viewOptions || {}),
      ...(this.viewOptions?.filters || {}),
      ...(this.viewOptions?.variables || {}),
    };
  }
  get commonOptions() {
    return this.panel?.options?.common || {};
  }
  get variablesData() {
    return this.commonOptions?.variables?.data || {};
  }
  get callFilter() {
    if (this.callType === EKind.caller) return this.callerFilter;
    return this.calleeFilter;
  }
  get callFilterMap() {
    if (this.callType === EKind.caller) return this.callerNameMap;
    return this.calleeNameMap;
  }

  created() {
    this.initCallFilter(EKind.caller);
    this.initCallFilter(EKind.callee);
    this.$nextTick(() => {
      this.initFilterOptions();
    });
  }
  getDefaultTags(callType: EKind) {
    if (callType === EKind.caller) return this.commonOptions?.angle?.caller?.tags;
    return this.commonOptions?.angle?.callee?.tags;
  }
  initCallFilter(callType: EKind) {
    const callList: IFilterOption[] = [];
    const callNameMap = {};
    const tags = this.getDefaultTags(callType);
    for (const item of tags) {
      const defaultItem =
        this.callType === callType ? this.callOptions?.call_filter?.find(opt => opt.key === item.value) : undefined;
      const value = defaultItem?.value?.slice() || [];
      const method = defaultItem?.method || 'eq';
      // if (defaultItem?.method === 'reg') {
      //   value = [];
      //   for (const v of defaultItem.value || []) {
      //     if (v.startsWith('.*')) {
      //       method = 'after_req';
      //       value.push(v.replace(/^\.\*/, ''));
      //       continue;
      //     }
      //     if (v.endsWith('.*')) {
      //       method = 'before_req';
      //       value.push(v.replace(/\.\*$/, ''));
      //       continue;
      //     }
      //     value.push(v);
      //   }
      // }
      callList.push({
        key: item.value,
        method,
        value,
        condition: 'and',
        options: this.callFilter.find(c => c.key === item.value)?.options || [],
        loading: false,
      });
      callNameMap[item.value] = item.text;
    }
    if (callType === EKind.caller) {
      this.callerFilter = callList;
      this.callerNameMap = callNameMap;
      return;
    }
    this.calleeFilter = callList;
    this.calleeNameMap = callNameMap;
  }
  initFilterOptions() {
    for (const item of this.callFilter) {
      if (item.value?.length) {
        this.getOptionListByKey(item.key);
      }
    }
  }
  @Watch('callOptions.call_filter')
  handleCallFilterChange() {
    this.initCallFilter(this.callType);
    this.$nextTick(() => {
      this.initFilterOptions();
    });
  }

  @Emit('search')
  handleSearch() {
    return this.callFilter
      .filter(item => item.value.length > 0)
      .map(({ key, method, condition, value }) => {
        return {
          key,
          method,
          condition,
          value,
        };
      });
  }

  @Emit('reset')
  handleReset() {
    return [];
  }
  handleToggle(key: string, isOpen: boolean) {
    if (!isOpen) return;
    this.getOptionListByKey(key);
  }

  handleRegexData(filter: IFilterOption[]): IFilterCondition[] {
    /** 前端处理数据：
     * 前匹配：调用后台、跳转数据检索时补成 example.*
     * 后匹配：调用后台、跳转数据检索时补成 .*example
     * */
    if (!filter?.length) return [];
    return filter.map(({ method, value, condition, key }) => {
      if (method === 'before_req' || method === 'after_req') {
        const list = value.map(value => {
          if (method === 'before_req' && !value.endsWith('.*')) {
            return `${value}.*`;
          }
          if (method === 'after_req' && !value.startsWith('.*')) {
            return `.*${value}`;
          }
          return value;
        });
        return {
          value: list,
          method: 'reg',
          condition,
          key,
        };
      }
      return { method, value, condition, key };
    });
  }
  /** 动态获取左侧列表的下拉值 */
  async getOptionListByKey(key: string) {
    const curOption = this.callFilter.find(item => item.key === key);
    if (!curOption) return;
    curOption.loading = true;
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const variablesService = new VariablesService({
      ...this.scopedVars,
      ...this.callFilter,
    });
    const newParams = {
      ...variablesService.transformVariables(this.variablesData, {
        ...this.callOptions,
      }),
      start_time: startTime,
      end_time: endTime,
      field: key,
    };
    const data = await getFieldOptionValues({
      ...newParams,
      where: [
        ...newParams.where,
        ...this.handleRegexData(this.callFilter.filter(item => key !== item.key && item.value.length > 0)),
      ],
    }).catch(() => false);
    curOption.loading = false;
    const options = data?.length ? [{ ...filterOption }, ...data] : [];
    if (curOption.value?.length) {
      // let value = curOption.value;
      // if(curOption.method === 'reg') {
      //   value= this.resetBeforeOrAfterReg(value).value;
      // }
      for (const val of curOption.value) {
        const opt = options.find(opt => opt.value === val);
        if (!opt) {
          options.push({ text: val, value: val });
        }
      }
    }
    curOption.options = options;
  }
  resetBeforeOrAfterReg(values: string[]) {
    let method: 'after_req' | 'before_req' = 'before_req';
    const valueList = [];
    for (const val of values) {
      if (val.startsWith('.*')) {
        method = 'after_req';
        valueList.push(val.replace(/^\.\*/, ''));
        continue;
      }
      if (val.endsWith('.*')) {
        method = 'before_req';
        valueList.push(val.replace(/\.\*$/, ''));
        continue;
      }
      valueList.push(val);
    }
    return { method, value: valueList };
  }
  handleValueChange(value: string[], item: IFilterOption) {
    item.value = value;
  }
  render() {
    return (
      <div class='caller-callee-filter'>
        <div class='search-title'>{this.$t('筛选')}</div>
        <div class='search-main'>
          {this.callFilter.map(item => {
            return (
              <div
                key={item.key}
                class='search-item'
              >
                <div class='search-item-label'>
                  <span>{this.callFilterMap[item.key]}</span>
                  <bk-select
                    class='item-label-select'
                    v-model={item.method}
                    clearable={false}
                    list={this.symbolList}
                    size='small'
                  >
                    {this.symbolList.map(opt => (
                      <bk-option
                        id={opt.value}
                        key={opt.value}
                        name={opt.label}
                      />
                    ))}
                  </bk-select>
                </div>
                <bk-select
                  key={item.key}
                  ref={item.key}
                  display-tag={true}
                  loading={item.loading}
                  placeholder={this.callFilterMap[item.key]}
                  showEmpty={!item.loading && !item.options.length}
                  value={item.value}
                  allow-create
                  collapse-tag
                  multiple
                  searchable
                  onChange={v => this.handleValueChange(v, item)}
                  onToggle={open => open && this.getOptionListByKey(item.key)}
                >
                  {!item.loading ? (
                    (item.options || []).map(opt => (
                      <bk-option
                        id={opt.value}
                        key={opt.value}
                        name={opt.text}
                      />
                    ))
                  ) : (
                    <span class='select-loading'>{this.$t('正在加载中...')}</span>
                  )}
                </bk-select>
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
