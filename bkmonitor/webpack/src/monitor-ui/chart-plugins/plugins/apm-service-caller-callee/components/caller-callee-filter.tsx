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
import { Component, Emit, InjectReactive, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getFieldOptionValues } from 'monitor-api/modules/apm_metric';
import ValueTagSelector, { type IValue } from 'monitor-pc/components/retrieval-filter/value-tag-selector';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import { VariablesService } from '../../../utils/variable';
import { type CallOptions, type IFilterCondition, type IFilterOption, type IListItem, EKind } from '../type';
import { SYMBOL_LIST } from '../utils';

import type { PanelModel } from '../../../typings';
import type {
  IGetValueFnParams,
  IOptionsInfo,
  TGetValueFn,
} from 'monitor-pc/components/retrieval-filter/value-selector-typing';
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
  /** 按「视角:字段」记录最近一次搜索词，避免主调/被调同名字段互相覆盖 */
  latestValueSearch: Record<string, string> = {};
  /** 按「视角:字段」记录候选项请求序号，过期响应不再写回 */
  optionRequestSeq: Record<string, number> = {};
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
  filtersOf(callType: EKind) {
    if (callType === EKind.caller) return this.callerFilter;
    return this.calleeFilter;
  }
  get callFilter() {
    return this.filtersOf(this.callType);
  }
  get callFilterMap() {
    if (this.callType === EKind.caller) return this.callerNameMap;
    return this.calleeNameMap;
  }

  created() {
    this.initCallFilter(EKind.caller);
    this.initCallFilter(EKind.callee);
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
  @Watch('callOptions.call_filter')
  handleCallFilterChange() {
    this.initCallFilter(this.callType);
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
  /** 动态获取左侧列表的下拉值。请求绑定发起时的视角，返回时丢弃过期响应 */
  async getOptionListByKey(key: string, callType: EKind = this.callType) {
    const listOf = () => this.filtersOf(callType);
    const curOption = listOf().find(item => item.key === key);
    if (!curOption) return;
    const seqKey = `${callType}:${key}`;
    const seq = (this.optionRequestSeq[seqKey] = (this.optionRequestSeq[seqKey] ?? 0) + 1);
    curOption.loading = true;
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const variablesService = new VariablesService({
      ...this.scopedVars,
      ...listOf(),
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
        ...this.handleRegexData(listOf().filter(item => key !== item.key && item.value.length > 0)),
      ],
    }).catch(() => false);
    if (this.optionRequestSeq[seqKey] !== seq) {
      // 更新的请求仍在使用当前对象时，不能把 loading 提前关掉
      if (!listOf().includes(curOption)) {
        curOption.loading = false;
      }
      return;
    }
    // 点击查询会重建筛选项，结果写回该视角当前列表中的对象
    const target = listOf().find(item => item.key === key) || curOption;
    if (target !== curOption) {
      curOption.loading = false;
    }
    target.loading = false;
    // 接口失败时保留已有候选项，避免把重建时拷贝来的缓存清掉
    if (!Array.isArray(data)) return;
    const options = data.length ? [{ ...filterOption }, ...data] : [];
    if (target.value?.length) {
      // let value = curOption.value;
      // if(curOption.method === 'reg') {
      //   value= this.resetBeforeOrAfterReg(value).value;
      // }
      for (const val of target.value) {
        const opt = options.find(opt => opt.value === val);
        if (!opt) {
          options.push({ text: val, value: val });
        }
      }
    }
    target.options = options;
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
  /**
   * @description 值选择器候选数据：下拉展开时请求接口并缓存到 item.options，输入搜索时仅本地过滤
   */
  getValueCallback(item: IFilterOption): TGetValueFn {
    const callType = this.callType;
    const field = item.key;
    const searchKey = `${callType}:${field}`;
    return async (params: IGetValueFnParams & { isInit__?: boolean }): Promise<IOptionsInfo> => {
      this.latestValueSearch[searchKey] = params.search ?? '';
      if (params.isInit__) {
        await this.getOptionListByKey(field, callType);
      }
      // 视角已切换时，这次结果属于已卸载的下拉，不能读到另一侧
      if (this.callType !== callType) {
        return { count: 0 as const, list: [] };
      }
      const current = this.filtersOf(callType).find(opt => opt.key === field);
      const search = (this.latestValueSearch[searchKey] ?? '').toLocaleLowerCase();
      return {
        count: 0 as const,
        list: (current?.options || []).reduce<IValue[]>((results, opt) => {
          if (
            !search ||
            String(opt.value).toLocaleLowerCase().includes(search) ||
            String(opt.text).toLocaleLowerCase().includes(search)
          ) {
            results.push({ id: opt.value, name: opt.text });
          }
          return results;
        }, []),
      };
    };
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
                key={`${this.callType}-${item.key}`}
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
                <ValueTagSelector
                  key={`${this.callType}-${item.key}`}
                  class='search-item-value'
                  fieldInfo={{
                    field: item.key,
                    alias: this.callFilterMap[item.key],
                    methods: [],
                    isEnableOptions: true,
                  }}
                  getValueFn={this.getValueCallback(item)}
                  value={item.value.map(v => ({ id: v, name: v === '' ? filterOption.text : v }))}
                  tippy-mode
                  onChange={v =>
                    this.handleValueChange(
                      (v as IValue[]).map(opt => opt.id),
                      item
                    )
                  }
                />
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
