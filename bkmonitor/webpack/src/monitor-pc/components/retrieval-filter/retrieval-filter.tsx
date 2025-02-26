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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import ResidentSetting from './resident-setting';
import UiSelector from './ui-selector';
import {
  ECondition,
  type EMethod,
  EMode,
  getCacheUIData,
  type IFilterField,
  type IFilterItem,
  type IGetValueFnParams,
  type IWhereItem,
  type IWhereValueOptionsItem,
  METHOD_MAP,
  MODE_LIST,
  setCacheUIData,
} from './utils';

import './retrieval-filter.scss';

interface IProps {
  fields: IFilterField[];
  where?: IWhereItem[];
  queryString?: string;
  getValueFn?: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;
  onWhereChange?: (v: IWhereItem[]) => void;
  onQueryStringChange?: (v: string) => void;
}

@Component
export default class RetrievalFilter extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) fields: IFilterField[];
  @Prop({
    type: Function,
    default: () =>
      Promise.resolve({
        count: 0,
        list: [],
      }),
  })
  getValueFn: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;
  /* ui部分where条件 */
  @Prop({ type: Array, default: () => [] }) where: IWhereItem[];
  /* 语句模式数据 */
  @Prop({ type: String, default: '' }) queryString: string;

  /* 展示常驻设置 */
  showResidentSetting = false;
  /* 当前查询模式 */
  mode = EMode.ui;
  /* 是否展开常驻设置 */
  residentSettingActive = false;
  uiValue: IFilterItem[] = [];
  cacheWhereStr = '';

  handleChangeMode() {
    this.mode = this.mode === EMode.ui ? EMode.ql : EMode.ui;
  }
  handleShowResidentSetting() {
    this.residentSettingActive = !this.residentSettingActive;
  }

  @Watch('where', { immediate: true })
  handleWatchValue() {
    const whereStr = JSON.stringify(this.where);
    if (this.cacheWhereStr === whereStr) {
      /* 避免重复渲染 */
      return;
    }
    this.cacheWhereStr = whereStr;
    const fieldsMap: Map<string, IFilterField> = new Map();
    for (const item of this.fields) {
      fieldsMap.set(item.name, item);
    }
    const uiCacheData = getCacheUIData();
    const localValue: IFilterItem[] = [];
    const uiCacheDataMap: Map<string, IFilterItem> = new Map();
    const uiCacheDataHideList: { value: IFilterItem; index: number }[] = [];
    let index = -1;
    for (const item of uiCacheData) {
      index += 1;
      uiCacheDataMap.set(item.key.id, item);
      if (item.hide) {
        uiCacheDataHideList.push({
          value: item,
          index: index,
        });
      }
    }
    for (const w of this.where) {
      const cacheItem = uiCacheDataMap.get(w.key);
      if (cacheItem) {
        const methodName = cacheItem.method.id === w.method ? cacheItem.method.name : METHOD_MAP[w.method];
        const cacheValueMap = new Map();
        for (const v of cacheItem.value) {
          cacheValueMap.set(v.id, v.name);
        }
        localValue.push({
          key: cacheItem.key,
          condition: { id: ECondition.and, name: 'AND' },
          method: { id: w.method as EMethod, name: methodName },
          options: w.options || { is_wildcard: false },
          value: w.value.map(v => ({
            id: v,
            name: cacheValueMap.get(v) || v,
          })),
        });
      } else {
        const keyItem = {
          id: w.key,
          name: fieldsMap.get(w.key)?.alias || w.key,
        };
        localValue.push({
          key: keyItem,
          condition: { id: ECondition.and, name: 'AND' },
          method: { id: w.method as EMethod, name: METHOD_MAP[w.method] },
          options: w.options || { is_wildcard: false },
          value: w.value.map(v => ({
            id: v,
            name: v,
          })),
        });
      }
    }
    /* 将上一次隐藏的条件回填 */
    let hideIndex = 0;
    for (const item of uiCacheDataHideList) {
      const len = localValue.length - 1;
      if (item.index > len) {
        localValue.splice(len, 0, item.value);
      } else {
        localValue.splice(item.index + hideIndex, 0, item.value);
      }
      hideIndex += 1;
    }
    this.uiValue = localValue;
  }

  /**
   * @description ui部分值变化
   * @param value
   */
  handleUiValueChange(value: IFilterItem[]) {
    this.uiValue = value;
    const where = [];
    setCacheUIData(value);
    for (const item of value) {
      if (!item?.hide) {
        where.push({
          key: item.key.id,
          condition: ECondition.and,
          value: item.value.map(v => v.id),
          ...(item?.options?.is_wildcard ? { options: { is_wildcard: true } } : {}),
          method: item.method.id,
        });
      }
    }
    this.$emit('whereChange', where);
  }

  render() {
    return (
      <div class='retrieval-filter__component'>
        <div class='retrieval-filter__component-main'>
          <div
            class='component-left'
            onClick={() => this.handleChangeMode()}
          >
            {MODE_LIST.filter(item => item.id === this.mode).map(item => [
              <span
                key={`${item.id}_0`}
                class='text'
              >
                {item.name}
              </span>,
              <div
                key={`${item.id}_1`}
                class='mode-icon'
              >
                <span class='icon-monitor icon-switch' />
              </div>,
            ])}
          </div>
          <div class='filter-content'>
            {this.mode === EMode.ui ? (
              <UiSelector
                fields={this.fields}
                getValueFn={this.getValueFn}
                onChange={this.handleUiValueChange}
              />
            ) : undefined}
          </div>
          <div class='component-right'>
            {this.mode === EMode.ui && (
              <div
                class={['setting-btn', { 'btn-active': this.residentSettingActive }]}
                v-bk-tooltips={{
                  content: window.i18n.tc('常驻筛选'),
                  delay: 300,
                }}
                onClick={() => this.handleShowResidentSetting()}
              >
                <span class='icon-monitor icon-tongyishezhi' />
              </div>
            )}
            {false && (
              <div class='favorite-btn'>
                <span class='icon-monitor icon-mc-uncollect' />
              </div>
            )}
            <div class='search-btn'>
              <span class='icon-monitor icon-mc-search' />
            </div>
          </div>
        </div>
        {this.residentSettingActive && <ResidentSetting fields={this.fields} />}
      </div>
    );
  }
}
