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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { copyText, deepClone, random } from 'monitor-common/utils';

import { APIType } from '../../pages/event-explore/api-utils';
import QsSelector from './qs-selector';
import ResidentSetting from './resident-setting';
import UiSelector from './ui-selector';
import {
  type EMethod,
  type IFavoriteListItem,
  type IFilterField,
  type IFilterItem,
  type IGetValueFnParams,
  type IWhereItem,
  type IWhereValueOptionsItem,
  ECondition,
  EMode,
  getCacheUIData,
  METHOD_MAP,
  MODE_LIST,
  setCacheUIData,
} from './utils';

import type { IFavList } from '../../pages/data-retrieval/typings';

import './retrieval-filter.scss';

interface IEvent {
  onCommonWhereChange?: (where: IWhereItem[]) => void;
  onCopyWhere: (v: IWhereItem[]) => void;
  onFavorite: (isEdit: boolean) => void;
  onModeChange?: (v: EMode) => void;
  onQueryStringChange?: (v: string) => void;
  onQueryStringInputChange?: (v: string) => void;
  onSearch: () => void;
  onShowResidentBtnChange?: (v: boolean) => void;
  onWhereChange?: (v: IWhereItem[]) => void;
}

interface IProps {
  commonWhere?: IWhereItem[];
  dataId?: string;
  defaultShowResidentBtn?: boolean;
  favoriteList?: IFavoriteListItem[];
  fields: IFilterField[];
  filterMode?: EMode;
  // isQsOperateWrapBottom?: boolean;
  isShowFavorite?: boolean;
  queryString?: string;
  residentSettingOnlyId?: string;
  selectFavorite?: IFavList.favList;
  source?: APIType;
  where?: IWhereItem[];
  getValueFn?: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;
}

@Component
export default class RetrievalFilter extends tsc<IProps, IEvent> {
  @Prop({ type: Array, default: () => [] }) fields: IFilterField[];
  @Prop({ type: Object, default: null }) selectFavorite: IFavList.favList;
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
  @Prop({ type: Array, default: () => [] }) commonWhere: IWhereItem[];
  /* 语句模式数据 */
  @Prop({ type: String, default: '' }) queryString: string;
  /** 常驻筛选唯一ID,用于保存常驻筛选配置*/
  @Prop({ type: String, default: '' }) residentSettingOnlyId: string;
  @Prop({ type: String, default: '' }) dataId: string;
  @Prop({ type: String, default: APIType.MONITOR }) source: APIType;
  @Prop({ type: Array, default: () => [] }) favoriteList: IFavoriteListItem[];
  @Prop({ type: String, default: EMode.ui }) filterMode: EMode;
  /* 语句模式hover显示的操作是否显示在下方 */
  // @Prop({ type: Boolean, default: false }) isQsOperateWrapBottom: boolean;
  @Prop({ type: Boolean, default: false }) isShowFavorite: boolean;
  @Prop({ type: Boolean, default: false }) defaultShowResidentBtn: boolean;

  /* 展示常驻设置 */
  showResidentSetting = false;
  /* 当前查询模式 */
  mode = EMode.ui;
  uiValue: IFilterItem[] = [];
  cacheWhereStr = '';
  qsValue = '';

  /** 缓存的commonWhere */
  cacheCommonWhere: IWhereItem[] = [];

  /*  */
  qsSelectorOptionsWidth = 0;
  resizeObserver = null;
  cacheQueryString = '';

  clearKey = '';

  searchBtnObserver = null;
  rightBtnsWrapWidth = 146;

  /** 当前选择收藏的id */
  get curFavoriteId() {
    return this.selectFavorite?.config?.queryConfig?.result_table_id;
  }

  /** 判断是否展示默认的常驻设置 */
  get isDefaultResidentSetting() {
    // 如果当前dataId和收藏的dataId一致，展示收藏
    if (this.curFavoriteId === this.dataId) {
      return false;
    }
    return true;
  }

  get residentSettingValue() {
    if (this.isDefaultResidentSetting) return this.commonWhere;
    /** 不展示默认的常驻设置，则使用收藏的常驻设置 */
    return this.selectFavorite?.config?.queryConfig?.commonWhere || [];
  }

  created() {
    this.clearHideData();
  }
  beforeDestroy() {
    this.clearHideData();
  }

  mounted() {
    this.resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        // 获取元素的宽度
        const contentEl = entry.target.querySelector('.retrieval-filter__component-main > .filter-content');
        const rightEl = entry.target.querySelector('.retrieval-filter__component-main > .component-right');
        this.qsSelectorOptionsWidth = contentEl.clientWidth + rightEl.clientWidth - 48;
        // const height = contentEl.clientHeight;
        // if (height < 58) {
        //   this.rightBtnsWrapWidth = 146;
        // } else if (height < 102) {
        //   this.rightBtnsWrapWidth = 74;
        // } else if (height > 146) {
        //   this.rightBtnsWrapWidth = 38;
        // }
      }
    });
    this.resizeObserver.observe(this.$el);
  }

  handleChangeMode() {
    this.mode = this.mode === EMode.ui ? EMode.queryString : EMode.ui;
    this.$emit('modeChange', this.mode);
  }

  @Emit('showResidentBtnChange')
  handleShowResidentSetting() {
    this.showResidentSetting = !this.showResidentSetting;
    if (!this.showResidentSetting && this.commonWhere.some(item => item.value.length)) {
      this.cacheCommonWhere = deepClone(this.commonWhere);
      this.uiValue = this.residentSettingToUiValue();
      this.handleCommonWhereChange([]);
      this.handleChange();
      this.$bkMessage({
        message: this.$tc('“常驻筛选”面板被折叠，过滤条件已填充到上方搜索框。'),
        theme: 'success',
      });
    }
    return this.showResidentSetting;
  }

  @Watch('where', { immediate: true })
  handleWatchValue() {
    this.handleWatchValueFn(this.where);
  }

  @Watch('queryString', { immediate: true })
  handleWatchQsString() {
    if (this.qsValue !== this.queryString) {
      this.qsValue = this.queryString;
    }
  }

  @Watch('filterMode', { immediate: true })
  handleWatchFilterMode() {
    if (this.mode !== this.filterMode) {
      this.mode = this.filterMode;
    }
  }

  @Watch('defaultShowResidentBtn', { immediate: true })
  handleWatchShowResidentSetting(val: boolean) {
    if (val !== this.showResidentSetting) {
      this.showResidentSetting = val;
    }
  }

  handleWatchValueFn(where: IWhereItem[]) {
    const whereStr = JSON.stringify(where);
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
    const uiCacheDataHideList: { index: number; value: IFilterItem }[] = [];
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
    for (const w of where) {
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
          method: { id: w.method as EMethod, name: methodName || w.method },
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
          method: { id: w.method as EMethod, name: METHOD_MAP[w.method] || w.method },
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
    // this.uiValue = this.setResidentSettingStatus(value);
    this.uiValue = value.map(item => ({ ...item, isSetting: undefined }));
    this.handleChange();
  }

  handleChange() {
    const where = this.uiValueToWhere();
    const whereStr = JSON.stringify(where);
    this.cacheWhereStr = whereStr;
    this.$emit('whereChange', where);
  }
  uiValueToWhere() {
    const where = [];
    setCacheUIData(this.uiValue);
    for (const item of this.uiValue) {
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
    return where;
  }

  /**
   * @description 常驻设置值变化
   * @param value
   */
  @Emit('commonWhereChange')
  handleCommonWhereChange(value: IWhereItem[]) {
    return value;
  }

  /**
   * @description 将常驻选项添加ui模式中
   */
  residentSettingToUiValue(): IFilterItem[] {
    const uiValueAdd = [];
    const uiValueAddSet = new Set();
    // 收回常驻设置是需要把常驻设置的值带到ui模式中
    for (const item of this.cacheCommonWhere) {
      if (item.value?.length) {
        const field = this.fields.find(field => field.name === item.key);
        const methodName =
          field.supported_operations?.find(v => v.value === item.method)?.alias || METHOD_MAP[item.method];
        uiValueAdd.push({
          key: { id: item.key, name: field?.alias || item.key },
          method: { id: item.method, name: methodName || item.method },
          condition: { id: ECondition.and, name: 'AND' },
          value: item.value.map(v => ({
            id: v,
            name: v,
          })),
        });
        uiValueAddSet.add(`${item.key}____${item.method}____${item.value.join('____')}`);
      }
    }
    const uiValue = [...this.uiValue, ...uiValueAdd];
    // 去重并且配置常驻
    const result = [];
    const tempSet = new Set();
    for (const item of uiValue) {
      const str = `${item.key.id}____${item.method.id}____${item.value.map(v => v.id).join('____')}`;
      if (!tempSet.has(str)) {
        result.push({
          ...item,
          isSetting: uiValueAddSet.has(str),
        });
      }
      tempSet.add(str);
    }
    return result;
  }

  // setResidentSettingStatus(uiValue: IFilterItem[]) {
  //   const tempSet = new Set();
  //   for (const item of this.cacheCommonWhere) {
  //     tempSet.add(`${item.key}____${item.method}____${item.value.join('____')}`);
  //   }
  //   const result = [];
  //   for (const item of uiValue) {
  //     const str = `${item.key.id}____${item.method.id}____${item.value.map(v => v.id).join('____')}`;
  //     result.push({
  //       ...item,
  //       isSetting: tempSet.has(str),
  //     });
  //   }
  //   return result;
  // }

  handleFavoriteClick() {
    if (!this.selectFavorite) {
      this.handleFavorite(false);
    }
  }

  @Emit('favorite')
  handleFavorite(isEdit = false) {
    return isEdit;
  }

  handleQsValueChange(v: string) {
    this.qsValue = v;
    this.$emit('queryStringInputChange', v);
  }

  handleClickSearchBtn() {
    if (this.mode === EMode.ui) {
      this.handleChange();
    } else {
      this.handleQsValueChange(this.qsValue);
      this.$emit('queryStringChange', this.qsValue);
    }
    this.$emit('search');
  }

  handleQuery() {
    this.handleClickSearchBtn();
  }

  clearHideData() {
    const uiValue = getCacheUIData();
    setCacheUIData(uiValue.filter(item => !item?.hide));
  }

  handleClear(_event: MouseEvent) {
    if (this.mode === EMode.ui ? this.uiValue.length : this.qsValue) {
      this.clearKey = random(8);
    }
  }
  handleCopy(_event: MouseEvent) {
    let str = '';
    if (this.mode === EMode.ui && this.uiValue.length) {
      const where = this.uiValueToWhere();
      this.$emit('copyWhere', where);
    } else if (this.mode === EMode.queryString && this.qsValue) {
      str = this.qsValue;
    }
    if (str) {
      copyText(str, msg => {
        this.$bkMessage({
          message: msg,
          theme: 'error',
        });
        return;
      });
      this.$bkMessage({
        message: this.$t('复制成功'),
        theme: 'success',
      });
    }
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
                clearKey={this.clearKey}
                fields={this.fields}
                getValueFn={this.getValueFn}
                value={this.uiValue}
                onChange={this.handleUiValueChange}
              />
            ) : (
              <QsSelector
                clearKey={this.clearKey}
                favoriteList={this.favoriteList}
                fields={this.fields}
                getValueFn={this.getValueFn}
                // isQsOperateWrapBottom={this.isQsOperateWrapBottom}
                qsSelectorOptionsWidth={this.qsSelectorOptionsWidth}
                value={this.qsValue}
                onChange={this.handleQsValueChange}
                onQuery={() => this.handleQuery()}
              />
            )}
          </div>
          <div class='component-right'>
            <div
              // style={{
              //   width: `${this.rightBtnsWrapWidth}px`,
              // }}
              class='component-right-btns'
            >
              <div
                class={['clear-btn', { disabled: this.mode === EMode.ui ? !this.uiValue.length : !this.qsValue }]}
                v-bk-tooltips={{
                  content: window.i18n.tc('清空'),
                  delay: 300,
                }}
                onClick={this.handleClear}
              >
                <span class='icon-monitor icon-a-Clearqingkong' />
              </div>
              <div
                class={['copy-btn', { disabled: this.mode === EMode.ui ? !this.uiValue.length : !this.qsValue }]}
                v-bk-tooltips={{
                  content: window.i18n.tc('复制'),
                  delay: 300,
                }}
                onClick={this.handleCopy}
              >
                <span class='icon-monitor icon-mc-copy' />
              </div>
              {this.mode === EMode.ui && (
                <div
                  class={['setting-btn', { 'btn-active': this.showResidentSetting }]}
                  v-bk-tooltips={{
                    content: window.i18n.tc('常驻筛选'),
                    delay: 300,
                  }}
                  onClick={() => this.handleShowResidentSetting()}
                >
                  <span class='icon-monitor icon-configuration' />
                </div>
              )}
              {this.isShowFavorite && (
                <bk-popover
                  class='favorite-btn'
                  ext-cls='favorite-btn-popover'
                  tippy-options={{
                    trigger: 'click',
                    interactive: true,
                    theme: 'light',
                  }}
                  disabled={!this.selectFavorite}
                  placement='bottom'
                >
                  <div
                    v-bk-tooltips={{
                      content: window.i18n.tc('收藏'),
                      delay: 300,
                    }}
                    onClick={this.handleFavoriteClick}
                  >
                    {this.selectFavorite ? (
                      <span class='icon-monitor icon-a-savebaocun' />
                    ) : (
                      <span class='icon-monitor icon-bookmark' />
                    )}
                  </div>
                  <div
                    class='favorite-btn-popover-content'
                    slot='content'
                  >
                    <div
                      class='favorite-btn-item'
                      onClick={() => this.handleFavorite(true)}
                    >
                      {this.$t('覆盖当前收藏')}
                    </div>
                    <div
                      class='favorite-btn-item'
                      onClick={() => this.handleFavorite(false)}
                    >
                      {this.$t('另存为新收藏')}
                    </div>
                  </div>
                </bk-popover>
              )}
            </div>
            <div
              class='search-btn'
              onClick={this.handleClickSearchBtn}
            >
              <span class='icon-monitor icon-mc-search' />
            </div>
          </div>
        </div>
        {this.showResidentSetting && (
          <ResidentSetting
            fields={this.fields}
            getValueFn={this.getValueFn}
            isDefaultSetting={this.isDefaultResidentSetting}
            residentSettingOnlyId={this.residentSettingOnlyId}
            value={this.residentSettingValue}
            onChange={this.handleCommonWhereChange}
          />
        )}
      </div>
    );
  }
}
