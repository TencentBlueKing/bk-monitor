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

import { type PropType, computed, defineComponent } from 'vue';

import { useI18n } from 'vue-i18n';

import RetrievalFilter from '../../../../components/retrieval-filter/retrieval-filter';
import {
  type IFavoriteListItem,
  type IFilterField,
  type IGetValueFnParams,
  type IHandleGetUserConfig,
  type IHandleSetUserConfig,
  type IWhereItem,
  type IWhereValueOptionsItem,
  EMode,
} from '../../../../components/retrieval-filter/typing';
import SpaceSelector from '../../../../components/space-select/space-selector';
import AlarmModuleSelector from './components/alarm-module-selector';
import SelectorTrigger from './components/selector-trigger';
import { useSpaceSelect } from './hooks/use-space-select';

import type { ITriggerSlotOptions } from '../../../../components/space-select/typing';
import type { CommonCondition } from '../../typings/services';
import type { ISpaceItem } from 'monitor-common/typings';

import './alarm-retrieval-filter.scss';

export default defineComponent({
  name: 'AlarmRetrievalFilter',
  props: {
    /* 字段列表 */
    fields: {
      type: Array as PropType<IFilterField[]>,
      default: () => [],
    },
    /* 查询模式 */
    filterMode: {
      type: String as PropType<EMode>,
      default: EMode.ui,
    },
    /* ui模式条件值 */
    conditions: {
      type: Array as PropType<CommonCondition[]>,
      default: () => [],
    },
    /* 常驻条件值 */
    residentCondition: {
      type: Object as PropType<CommonCondition[]>,
      default: () => ({}),
    },
    /* 语句模式语句 */
    queryString: {
      type: String,
      default: '',
    },
    /* 收藏列表 */
    favoriteList: {
      type: Array as PropType<IFavoriteListItem[]>,
      default: () => [],
    },
    /* 常驻条件配置id */
    residentSettingOnlyId: {
      type: String,
      default: '',
    },
    /* 当前选择的业务列表 */
    bizIds: {
      type: Array as PropType<(number | string)[]>,
      default: () => [],
    },
    /* 获取值的函数 */
    getValueFn: {
      type: Function as PropType<(params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>>,
      default: () =>
        Promise.resolve({
          count: 0,
          list: [],
        }),
    },
    /* 业务/空间列表 */
    bizList: {
      type: Array as PropType<ISpaceItem[]>,
      default: () => [],
    },
    /* 是否包含我有故障、空间的选项 */
    needIncidentOption: {
      type: Boolean,
      default: false,
    },
    // 常驻设置获取用户配置
    handleGetUserConfig: {
      type: Function as PropType<IHandleGetUserConfig>,
      default: () => Promise.resolve(undefined),
    },
    // 常驻设置设置用户配置
    handleSetUserConfig: {
      type: Function as PropType<IHandleSetUserConfig>,
      default: () => Promise.resolve(false),
    },
    // 当前选择收藏项
    selectFavorite: {
      type: Object as PropType<{
        commonWhere?: IWhereItem[];
        where?: IWhereItem[];
      }>,
      default: () => null,
    },
  },
  emits: {
    conditionChange: (_v: CommonCondition[]) => true,
    queryStringChange: (_v: string) => true,
    filterModeChange: (_v: EMode) => true,
    residentConditionChange: (_v: CommonCondition[]) => true,
    query: () => true,
    bizIdsChange: (_v: (number | string)[]) => true,
    favoriteSave: (_isEdit: boolean) => true,
  },
  setup(_props, { emit }) {
    const { t } = useI18n();

    const showAlarmModule = computed(() => {
      // return props.filterMode === EMode.ui;
      return false;
    });

    function handleConditionChange(val) {
      emit('conditionChange', val);
    }
    function handleQueryStringChange(val) {
      emit('queryStringChange', val);
    }
    function handleFilterModeChange(val: EMode) {
      emit('filterModeChange', val);
    }
    function handleResidentConditionChange(val) {
      emit(
        'residentConditionChange',
        val.map(item => ({
          ...item,
          condition: 'and',
        }))
      );
    }
    function handleQuery() {
      emit('query');
    }
    function handleBizIdsChange(val: (number | string)[]) {
      emit('bizIdsChange', val);
    }

    const handleFavoriteSave = val => {
      emit('favoriteSave', val);
    };

    return {
      showAlarmModule,
      t,
      handleQuery,
      handleConditionChange,
      handleQueryStringChange,
      handleFilterModeChange,
      handleResidentConditionChange,
      handleBizIdsChange,
      handleFavoriteSave,
      ...useSpaceSelect(),
    };
  },
  render() {
    return (
      <RetrievalFilter
        class='alarm-center__alarm-retrieval-filter-component'
        changeWhereFormatter={where => {
          return where.map(w => ({
            key: w.key,
            method: w.method,
            value: w.value,
            condition: w.condition,
          }));
        }}
        commonWhere={this.residentCondition}
        favoriteList={this.favoriteList}
        fields={this.fields}
        filterMode={this.filterMode}
        getValueFn={this.getValueFn}
        handleGetUserConfig={this.handleGetUserConfig}
        handleSetUserConfig={this.handleSetUserConfig}
        isShowClear={true}
        isShowCopy={true}
        isShowFavorite={true}
        isShowResident={true}
        loadDelay={0}
        queryString={this.queryString}
        residentSettingOnlyId={this.residentSettingOnlyId}
        selectFavorite={this.selectFavorite}
        where={this.conditions}
        onCommonWhereChange={this.handleResidentConditionChange}
        onFavorite={this.handleFavoriteSave}
        onModeChange={this.handleFilterModeChange}
        onQueryStringChange={this.handleQueryStringChange}
        onSearch={this.handleQuery}
        onWhereChange={this.handleConditionChange}
      >
        {{
          default: () => (
            <>
              <SpaceSelector
                hasAuthApply={true}
                isAutoSelectCurrentSpace={true}
                isCommonStyle={false}
                multiple={this.isMultiple}
                needChangeChoiceType={true}
                needIncidentOption={this.needIncidentOption}
                spaceList={this.bizList}
                value={this.bizIds}
                onApplyAuth={this.handleCheckAllowedByIds}
                onChange={this.handleBizIdsChange}
                onChangeChoiceType={this.handleChangeChoiceType}
              >
                {{
                  trigger: (options: ITriggerSlotOptions) => (
                    <SelectorTrigger
                      class='selector-trigger-space-select'
                      tips={options.valueStrList
                        .map(
                          (item, index) =>
                            `${index !== 0 ? `   , ${item.name}` : item.name}${item.id ? `(${item.id})` : ''}`
                        )
                        .join('')}
                      active={options.active}
                      hasRightSplit={true}
                      isError={options.error}
                    >
                      {{
                        top: () => <span>{this.t('空间')}</span>,
                        bottom: () => (
                          <span class='selected-text'>
                            {options.valueStrList.map((item, index) => (
                              <span
                                key={item.id}
                                class='selected-text-item'
                              >
                                {index !== 0 ? `   , ${item.name}` : item.name}
                                {!!item.id && <span class='selected-text-id'>({item.id})</span>}
                              </span>
                            ))}
                          </span>
                        ),
                      }}
                    </SelectorTrigger>
                  ),
                }}
              </SpaceSelector>
              {this.showAlarmModule && <AlarmModuleSelector />}
            </>
          ),
        }}
      </RetrievalFilter>
    );
  },
});
