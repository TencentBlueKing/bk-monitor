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

import { defineComponent, useTemplateRef, watch } from 'vue';
import { shallowRef } from 'vue';
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

import { useResizeObserver } from '@vueuse/core';
import { Message, Popover } from 'bkui-vue';
import { copyText, deepClone, random } from 'monitor-common/utils/utils';
import { MODE_LIST } from 'monitor-pc/components/retrieval-filter/utils';

import QsSelector from './qs-selector';
import ResidentSetting from './resident-setting';
import {
  ECondition,
  type EMethod,
  EMode,
  type IFilterField,
  type IFilterItem,
  type IWhereItem,
  METHOD_MAP,
  RETRIEVAL_FILTER_EMITS,
  RETRIEVAL_FILTER_PROPS,
} from './typing';
import UiSelector from './ui-selector';
import { getCacheUIData, setCacheUIData, traceWhereFormatter } from './utils';

import './retrieval-filter.scss';

export default defineComponent({
  name: 'RetrievalFilter',
  props: RETRIEVAL_FILTER_PROPS,
  emits: RETRIEVAL_FILTER_EMITS,
  setup(props, { emit }) {
    const elRef = useTemplateRef('el');
    const { t } = useI18n();

    const showResidentSetting = shallowRef(false);
    const mode = shallowRef<EMode>(EMode.ui);
    const uiValue = shallowRef<IFilterItem[]>([]);
    const cacheWhereStr = shallowRef('');
    const qsValue = shallowRef('');
    const cacheCommonWhere = shallowRef<IWhereItem[]>([]);
    const qsSelectorOptionsWidth = shallowRef(0);
    const clearKey = shallowRef('');

    const localFields = computed(() => {
      return props.fields.map(item => ({
        ...item,
        supported_operations:
          item?.supported_operations?.map(s => ({
            ...s,
            alias: s.label,
            value: s.operator,
          })) || [],
      })) as IFilterField[];
    });
    const curFavoriteId = computed(() => props.selectFavorite?.config?.queryParams?.app_name);
    const isDefaultResidentSetting = computed(() => {
      if (curFavoriteId.value === props.dataId) {
        return false;
      }
      return true;
    });
    const residentSettingValue = computed(() => {
      if (isDefaultResidentSetting.value) {
        return props.isTraceRetrieval ? traceWhereFormatter(props.commonWhere) : props.commonWhere;
      }
      /** 不展示默认的常驻设置，则使用收藏的常驻设置 */
      return props.isTraceRetrieval
        ? traceWhereFormatter(props.selectFavorite?.config?.componentData?.commonWhere || [])
        : props.selectFavorite?.config?.componentData?.commonWhere || [];
    });
    const propsCommonWhere = computed(() => {
      return props.isTraceRetrieval ? traceWhereFormatter(props.commonWhere) : props.commonWhere;
    });

    init();

    watch(
      () => props.where,
      val => {
        const traceWhere = traceWhereFormatter(val);
        handleWatchValueFn(props.isTraceRetrieval ? traceWhere : val);
      },
      {
        immediate: true,
      }
    );
    watch(
      () => props.queryString,
      val => {
        if (qsValue.value !== val) {
          qsValue.value = val;
        }
      },
      {
        immediate: true,
      }
    );
    watch(
      () => props.filterMode,
      val => {
        if (mode.value !== val) {
          mode.value = val;
        }
      },
      { immediate: true }
    );
    watch(
      () => props.defaultShowResidentBtn,
      val => {
        if (val !== showResidentSetting.value) {
          showResidentSetting.value = val;
        }
      },
      {
        immediate: true,
      }
    );

    function init() {
      const uiValue = getCacheUIData();
      setCacheUIData(uiValue.filter(item => !item?.hide));
      useResizeObserver(elRef as any, entries => {
        const entry = entries[0];
        const contentEl = entry.target.querySelector('.retrieval-filter__component-main > .filter-content');
        const rightEl = entry.target.querySelector('.retrieval-filter__component-main > .component-right');
        if (contentEl && rightEl) {
          qsSelectorOptionsWidth.value = contentEl.clientWidth + rightEl.clientWidth - 48;
        }
      });
    }

    function handleChangeMode() {
      mode.value = mode.value === EMode.ui ? EMode.queryString : EMode.ui;
      emit('modeChange', mode.value);
    }

    /**
     * @description 常驻设置按钮点击
     */
    function handleShowResidentSetting() {
      showResidentSetting.value = !showResidentSetting.value;
      if (!showResidentSetting.value && propsCommonWhere.value.some(item => item.value.length)) {
        cacheCommonWhere.value = deepClone(propsCommonWhere.value);
        uiValue.value = residentSettingToUiValue();
        handleCommonWhereChange([]);
        handleChange();
        Message({
          message: t('“常驻筛选”面板被折叠，过滤条件已填充到上方搜索框。'),
          theme: 'success',
        });
      }
      emit('showResidentBtnChange', showResidentSetting.value);
    }
    function residentSettingToUiValue(): IFilterItem[] {
      const uiValueAdd = [];
      const uiValueAddSet = new Set();
      // 收回常驻设置是需要把常驻设置的值带到ui模式中
      for (const item of cacheCommonWhere.value) {
        if (item.value?.length) {
          const field = props.fields.find(field => field.name === item.key);
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
      const uiValue$ = [...uiValue.value, ...uiValueAdd];
      // 去重并且配置常驻
      const result = [];
      const tempSet = new Set();
      for (const item of uiValue$) {
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

    /**
     * @description 常驻设置值变化
     * @param value
     */
    function handleCommonWhereChange(value: IWhereItem[]) {
      const traceWhere = value.map(item => ({
        key: item.key,
        operator: item.method,
        value: item.value,
      }));
      emit('commonWhereChange', props.isTraceRetrieval ? traceWhere : value);
    }

    function handleChange() {
      const where = [];
      setCacheUIData(uiValue.value);
      for (const item of uiValue.value) {
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
      const whereStr = JSON.stringify(where);
      cacheWhereStr.value = whereStr;
      const traceWhere = where.map(item => ({
        key: item.key,
        operator: item.method,
        value: item.value,
      }));
      emit('whereChange', props.isTraceRetrieval ? traceWhere : where);
    }

    function handleWatchValueFn(where: IWhereItem[]) {
      const whereStr = JSON.stringify(where);
      if (cacheWhereStr.value === whereStr) {
        /* 避免重复渲染 */
        return;
      }
      cacheWhereStr.value = whereStr;
      const fieldsMap: Map<string, IFilterField> = new Map();
      for (const item of props.fields) {
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
      uiValue.value = localValue;
    }

    /**
     * @description ui部分值变化
     * @param value
     */
    function handleUiValueChange(value: IFilterItem[]) {
      uiValue.value = value.map(item => ({ ...item, isSetting: undefined }));
      handleChange();
    }

    function handleFavoriteClick() {
      if (!props.selectFavorite) {
        handleFavorite(false);
      }
    }

    function handleFavorite(isEdit = false) {
      emit('favorite', isEdit);
    }

    function handleQsValueChange(v: string) {
      qsValue.value = v;
      emit('queryStringInputChange', v);
    }
    function handleClickSearchBtn() {
      if (mode.value === EMode.ui) {
        handleChange();
      } else {
        handleQsValueChange(qsValue.value);
        emit('queryStringChange', qsValue.value);
      }
      emit('search');
    }

    function handleQuery() {
      handleClickSearchBtn();
    }
    function clearHideData() {
      const uiValue = getCacheUIData();
      setCacheUIData(uiValue.filter(item => !item?.hide));
    }

    function handleClear(_event: MouseEvent) {
      if (mode.value === EMode.ui ? uiValue.value.length : qsValue.value) {
        clearKey.value = random(8);
      }
    }
    function handleCopy(_event: MouseEvent) {
      let str = '';
      if (mode.value === EMode.ui && uiValue.value.length) {
        const where = [];
        for (const item of uiValue.value) {
          if (!item?.hide) {
            where.push({
              key: item.key.id,
              value: item.value.map(v => v.id),
              operator: item.method.id,
            });
          }
        }
        str = JSON.stringify(where);
      } else if (mode.value === EMode.queryString && qsValue.value) {
        str = qsValue.value;
      }
      if (str) {
        copyText(str, msg => {
          Message({
            message: msg,
            theme: 'error',
          });
          return;
        });
        Message({
          message: t('复制成功'),
          theme: 'success',
        });
      }
    }

    return {
      mode,
      uiValue,
      qsValue,
      residentSettingValue,
      showResidentSetting,
      clearKey,
      qsSelectorOptionsWidth,
      isDefaultResidentSetting,
      localFields,
      handleChangeMode,
      handleShowResidentSetting,
      handleUiValueChange,
      handleFavoriteClick,
      handleQuery,
      clearHideData,
      handleClear,
      handleCopy,
      handleFavorite,
      handleClickSearchBtn,
      handleQsValueChange,
      handleCommonWhereChange,
    };
  },
  render() {
    return (
      <div
        ref='el'
        class='vue3_retrieval-filter__component'
      >
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
                fields={this.localFields}
                getValueFn={this.getValueFn}
                value={this.uiValue}
                onChange={this.handleUiValueChange}
              />
            ) : (
              <QsSelector
                clearKey={this.clearKey}
                favoriteList={this.favoriteList}
                fields={this.localFields}
                getValueFn={this.getValueFn}
                qsSelectorOptionsWidth={this.qsSelectorOptionsWidth}
                value={this.qsValue}
                onChange={this.handleQsValueChange}
                onQuery={() => this.handleQuery()}
              />
            )}
          </div>
          <div class='component-right'>
            <div class='component-right-btns'>
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
                <Popover
                  extCls='retrieval-filter-favorite-btn-popover'
                  disabled={!this.selectFavorite}
                  placement='bottom'
                  theme='light padding-0'
                  trigger='click'
                >
                  {{
                    default: () => {
                      return (
                        <div
                          class='favorite-btn'
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
                      );
                    },
                    content: () => {
                      return (
                        <div class='favorite-btn-popover-content'>
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
                      );
                    },
                  }}
                </Popover>
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
        {this.showResidentSetting && this.mode !== EMode.queryString && (
          <ResidentSetting
            defaultResidentSetting={this.defaultResidentSetting}
            fields={this.localFields}
            getValueFn={this.getValueFn}
            isDefaultSetting={this.isDefaultResidentSetting}
            residentSettingOnlyId={this.residentSettingOnlyId}
            value={this.residentSettingValue}
            onChange={this.handleCommonWhereChange}
          />
        )}
      </div>
    );
  },
});
