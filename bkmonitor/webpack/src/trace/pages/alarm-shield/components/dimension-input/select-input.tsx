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
import { type PropType, computed, defineComponent, nextTick, reactive, shallowRef, watch } from 'vue';

import { bkTooltips, Input, Loading, OverflowTitle, Popover, Radio } from 'bkui-vue';
import { getMetricListV2, getStrategyListV2, promqlToQueryConfig } from 'monitor-api/modules/strategies';
import { debounce } from 'monitor-common/utils';
import { useI18n } from 'vue-i18n';

import EmptyStatus from '../../../../components/empty-status/empty-status';

import type { IDimensionItem } from '../../typing';

import './select-input.scss';

export const ALL = 'ALL';
const changeDebounceTime = 300;

interface IListItem {
  id: string;
  name: string;
}

export default defineComponent({
  name: 'SelectInput',
  directives: {
    bkTooltips,
  },
  props: {
    value: {
      type: String,
      default: '',
    },
    list: {
      type: Array as PropType<IListItem[]>,
      default: () => [],
    },
    dimesionKey: {
      type: String,
      default: '',
    },
    /* 将维度选择框改为分组(根据策略分组) */
    isDimensionGroup: {
      type: Boolean,
      default: false,
    },
    groupDimensionMap: {
      type: Object as PropType<Map<string, IDimensionItem[]>>,
      default: () => new Map(),
    },
    strategyList: {
      type: Array,
      default: () => [],
    },
    onChange: {
      type: Function as PropType<(v: string) => void>,
      default: _v => {},
    },
    /* 删除 */
    onDelete: {
      type: Function,
      default: () => {},
    },
    /* 初始显示的策略列表，避免重复获取 */
    onStrategyListInit: {
      type: Function,
      default: _v => {},
    },
    /* 缓存策略包含的维度列表 配合groupDimensionMap使用 */
    dimensionSet: {
      type: Function as PropType<(key: string, list: IDimensionItem[]) => void>,
      default: (_key, _list) => {},
    },
    /* 缓存策略的meta信息 */
    metricMetaSet: {
      type: Function as PropType<(key: string, obj: any) => void>,
      default: (_key, _obj) => {},
    },
    /* 选中维度 */
    onSelectDimension: {
      type: Function as PropType<(item: IDimensionItem, meta: any, strategy) => void>,
      default: (_item, _meta, _strategy) => {},
    },
  },
  setup(props) {
    const popoverRef = shallowRef(null);
    const strategySearchRef = shallowRef(null);
    const { t } = useI18n();
    const localValue = shallowRef('');
    const localList = shallowRef([]);

    /* 维度选择框面板数据 */
    const selectData = reactive({
      strategy: ALL,
      /* 策略列表 */
      strategyList: [],
      /* 策略搜索栏 */
      strategySearch: '',
      showStrategySearch: false,
      /* 策略列表分页 */
      strategyPagination: {
        page: 1,
        pageSize: 20,
        isEnd: false,
      },
      /* 右侧选项（需父组件缓存下来） */
      optionsSearch: '',
      options: [],
      rightLoading: false,
      leftLoading: false,
    });
    const curMetricMeta = shallowRef(null);
    const notChange = shallowRef(false);

    const debounceHandleChange = debounce(handleChange, changeDebounceTime, false);
    const debounceHandleStrategySearch = debounce(handleStrategySearch, 300, false);
    const debounceHandleOptionSearch = debounce(handleOptionSearch, 300, false);

    const optionsFilter = computed(() => {
      return selectData.options.filter(item => {
        return item.id.indexOf(selectData.optionsSearch) >= 0 || item.name.indexOf(selectData.optionsSearch) >= 0;
      });
    });

    watch(
      () => props.list,
      v => {
        localList.value = v;
      },
      { immediate: true }
    );

    watch(
      () => props.value,
      v => {
        if (v !== localValue.value) {
          localValue.value = v;
        }
      },
      {
        immediate: true,
      }
    );

    init();

    async function init() {
      /* 分组的情况下执行 */
      if (props.isDimensionGroup) {
        if (props.strategyList.length) {
          selectData.strategyList = props.strategyList;
        } else {
          selectData.strategyList = await getStrategyList();
          props.onStrategyListInit(selectData.strategyList);
        }
      }
    }
    /* 获取策略列表数据 */
    async function getStrategyList(serach = '') {
      return await getStrategyListV2({
        conditions: serach
          ? [
              {
                key: 'strategy_name',
                value: [serach],
              },
            ]
          : [],
        order_by: '-update_time',
        page: selectData.strategyPagination.page,
        page_size: selectData.strategyPagination.pageSize,
        type: 'monitor',
      })
        .then(res => res.strategy_config_list)
        .catch(() => []);
    }
    /**
     * @description 搜索
     */
    const searchList = computed(() => {
      if (localValue.value) {
        const isCheck = localList.value.some(item => item.name === localValue.value || item.id === localValue.value);
        const lowerSearch = localValue.value.toLocaleLowerCase();
        return localList.value.filter(item => {
          const idLower = `${item.id}`.toLocaleLowerCase();
          const nameLower = `${item.name}`.toLocaleLowerCase();
          if (isCheck) {
            return true;
          }
          if (idLower.includes(lowerSearch)) {
            return true;
          }
          if (nameLower.includes(lowerSearch)) {
            return true;
          }
          return false;
        });
      }
      return localList.value;
    });
    /**
     * @description 选择
     * @param item
     */
    function handleSelect(item) {
      localValue.value = item.name;
      popoverRef.value?.hide();
      debounceHandleChange(item.name);
    }
    /**
     * @description 删除
     */
    function handleDelete() {
      localValue.value = '';
      popoverRef.value?.hide();
      props.onDelete();
    }
    /**
     * @description 值变更
     * @param v
     */
    function handleChange(v: string) {
      if (!notChange.value) {
        props.onChange(v);
      }
    }
    function handleInputChange(v) {
      debounceHandleChange(v);
    }
    /**
     * @description 展开策略搜索
     */
    function handleShowStrategySearch() {
      selectData.showStrategySearch = true;
      nextTick(() => {
        strategySearchRef.value?.focus();
      });
    }

    /**
     * @description 切换策略
     * @param v
     */
    async function handleStrategyChange(v) {
      selectData.strategy = v;
      const options = props.groupDimensionMap.get(selectData.strategy) || [];
      if (options.length) {
        selectData.options = options;
      } else if (v !== ALL) {
        if (props.groupDimensionMap.has(v)) {
          selectData.options = props.groupDimensionMap.get(v);
        } else {
          selectData.rightLoading = true;
          const strategyItem = selectData.strategyList.find(item => item.id === v);
          const {
            items: [{ query_configs: queryConfigs }],
          } = strategyItem;
          const isPrometheus = queryConfigs?.[0]?.data_source_label === 'prometheus';
          if (isPrometheus) {
            //
            const promqlData = await promqlToQueryConfig('', {
              promql: queryConfigs?.[0]?.promql || '',
            }).catch(() => null);
            if (promqlData) {
              const metricItem = promqlData.query_configs?.[0];
              if (metricItem) {
                const metricMeta = {
                  dataSourceLabel: metricItem.data_source_label,
                  dataTypeLabel: metricItem.data_type_label,
                  metricField: metricItem.metric_field,
                  resultTableId: metricItem.result_table_id,
                  indexSetId: metricItem.index_set_id,
                };
                curMetricMeta.value = metricMeta;
                props.metricMetaSet(v, metricMeta);
                const dimension = metricItem?.agg_dimension || [];
                const dimensionList = dimension.map(d => ({ id: d, name: d }));
                props.dimensionSet(v, dimensionList);
                selectData.options = dimensionList;
              }
            }
          } else {
            if (queryConfigs?.length) {
              const { metric_list: metricListTemp = [] } = await getMetricListV2({
                page: 1,
                page_size: queryConfigs.length,
                // result_table_label: scenario, // 不传result_table_label，避免关联告警出现不同监控对象时报错
                conditions: [{ key: 'metric_id', value: queryConfigs.map(item => item.metric_id) }],
              }).catch(() => ({}));
              const [metricItem] = metricListTemp;
              if (metricItem) {
                const metricMeta = {
                  dataSourceLabel: metricItem.data_source_label,
                  dataTypeLabel: metricItem.data_type_label,
                  metricField: metricItem.metric_field,
                  resultTableId: metricItem.result_table_id,
                  indexSetId: metricItem.index_set_id,
                };
                curMetricMeta.value = metricMeta;
                props.metricMetaSet(v, metricMeta);
              }
              const dimensionList = metricListTemp.length
                ? metricListTemp.reduce((pre, cur) => {
                    const dimensionList = pre
                      .concat(
                        cur.dimensions.filter(item => typeof item.is_dimension === 'undefined' || item.is_dimension)
                      )
                      .filter((item, index, arr) => arr.map(item => item.id).indexOf(item.id, 0) === index);
                    return dimensionList;
                  }, [])
                : [];
              // 取策略各指标agg_dimension的交集
              const getIntersection = (arrays: string[][]) => {
                if (arrays.length === 0) {
                  return [];
                }
                let intersection = arrays[0];
                for (let i = 1; i < arrays.length; i++) {
                  intersection = intersection.filter(item => arrays[i].includes(item));
                }
                return intersection;
              };
              const queryConfigDimensions = [];
              queryConfigs.forEach(q => {
                const temp = q?.agg_dimension || [];
                queryConfigDimensions.push(temp);
              });
              const strategyDimensionSet = new Set(getIntersection(queryConfigDimensions));
              const dimensionListFilter = dimensionList.filter(item => strategyDimensionSet.has(item.id));
              props.dimensionSet(v, dimensionListFilter);
              selectData.options = dimensionListFilter;
            }
          }
        }
        selectData.rightLoading = false;
      }
    }
    /**
     * @description 弹出选项
     */
    function handleAfterShow() {
      if (props.isDimensionGroup) {
        strategyPaginationInit();
        selectData.optionsSearch = '';
        selectData.strategyList = props.strategyList;
        selectData.strategySearch = '';
        selectData.strategy = ALL;
        selectData.showStrategySearch = false;
        selectData.options = props.groupDimensionMap.get(selectData.strategy) || [];
      }
    }
    /**
     * @description 策略列表滚动加载
     */
    async function handleScroll(e) {
      const contentHeight = e.target.scrollHeight;
      const viewportHeight = e.target.clientHeight;
      const scrollPosition = e.target.scrollTop;
      if (scrollPosition >= contentHeight - viewportHeight) {
        if (!selectData.strategyPagination.isEnd) {
          selectData.leftLoading = true;
          selectData.strategyPagination.page += 1;
          const list = await getStrategyList(selectData.strategySearch);
          selectData.strategyList.push(...list);
          if (list.length < selectData.strategyPagination.pageSize) {
            selectData.strategyPagination.isEnd = true;
          }
          selectData.leftLoading = false;
        }
      }
    }
    /**
     * @description 选择维度
     * @param item
     */
    function handleSelectDimension(item: IDimensionItem) {
      notChange.value = true;
      localValue.value = item.name;
      setTimeout(() => {
        notChange.value = false;
      }, changeDebounceTime + 50);
      popoverRef.value?.hide();
      props.onSelectDimension(item, curMetricMeta.value, selectData.strategy);
    }
    /**
     * 初始话策略列表分页
     */
    function strategyPaginationInit() {
      selectData.strategyPagination.isEnd = false;
      selectData.strategyPagination.page = 1;
    }
    /**
     * @description 策略列表搜索
     * @param v
     */
    async function handleStrategySearch(v: string) {
      selectData.strategySearch = v;
      selectData.leftLoading = true;
      strategyPaginationInit();
      selectData.strategyList = await getStrategyList(v);
      selectData.leftLoading = false;
    }
    /**
     * @description 搜索失焦
     */
    function handleSearchBlur() {
      if (!selectData.strategySearch) {
        selectData.showStrategySearch = false;
      }
    }
    /**
     * @description 清除搜索
     */
    function handleSearchClear() {
      selectData.showStrategySearch = false;
      strategyPaginationInit();
    }
    /**
     * @description 维度搜索
     * @param v
     */
    function handleOptionSearch(v: string) {
      selectData.optionsSearch = v;
    }

    /**
     * @description 清除筛选条件
     */
    function handleNoDataOperation() {
      handleOptionSearch('');
    }

    return {
      localList,
      searchList,
      popoverRef,
      localValue,
      selectData,
      strategySearchRef,
      optionsFilter,
      t,
      handleInputChange,
      handleSelect,
      handleDelete,
      handleShowStrategySearch,
      handleStrategyChange,
      handleAfterShow,
      handleScroll,
      handleSelectDimension,
      debounceHandleStrategySearch,
      handleSearchBlur,
      handleSearchClear,
      handleOptionSearch,
      debounceHandleOptionSearch,
      handleNoDataOperation,
    };
  },
  render() {
    return (
      <Popover
        content={this.dimesionKey}
        disabled={!this.dimesionKey}
        placement={'top'}
        popoverDelay={[300, 0]}
      >
        <span class='dimension-condition-input-select-input-component'>
          <Popover
            ref='popoverRef'
            extCls='dimension-condition-input-select-input-component-pop'
            arrow={false}
            placement='bottom-start'
            theme='light'
            trigger='click'
            onAfterShow={this.handleAfterShow}
          >
            {{
              default: () => (
                <Input
                  v-model={this.localValue}
                  placeholder={this.t('请选择维度')}
                  onChange={this.handleInputChange}
                />
              ),
              content: () =>
                this.isDimensionGroup ? (
                  <div class='group-wrap'>
                    <div class='left-wrap'>
                      <div class='search-wrap'>
                        {this.selectData.showStrategySearch ? (
                          <div class='active-wrap'>
                            <Input
                              ref='strategySearchRef'
                              behavior={'simplicity'}
                              modelValue={this.selectData.strategySearch}
                              clearable
                              onBlur={this.handleSearchBlur}
                              onClear={this.handleSearchClear}
                              onUpdate:modelValue={v => this.debounceHandleStrategySearch(v)}
                            >
                              {{
                                prefix: () => (
                                  <span class='search-icon'>
                                    <span class='icon-monitor icon-mc-search' />
                                  </span>
                                ),
                              }}
                            </Input>
                          </div>
                        ) : (
                          <div class='title-wrap'>
                            <span>{this.t('基于策略筛选')}</span>
                            <span
                              class='icon-monitor icon-mc-search'
                              onClick={this.handleShowStrategySearch}
                            />
                          </div>
                        )}
                      </div>
                      <Loading loading={this.selectData.leftLoading}>
                        <div
                          class='list-wrap-01'
                          onScroll={this.handleScroll}
                        >
                          {
                            <Radio.Group
                              key={this.selectData.strategyList.length}
                              modelValue={this.selectData.strategy}
                              size='small'
                              onChange={v => this.handleStrategyChange(v)}
                            >
                              {[{ id: ALL, name: this.t('全部') }, ...this.selectData.strategyList].map(item => (
                                <Radio
                                  key={item.id}
                                  label={item.id}
                                >
                                  <OverflowTitle
                                    placement='right'
                                    type='tips'
                                  >
                                    <span class='radio-label'>{item.name}</span>
                                  </OverflowTitle>
                                </Radio>
                              ))}
                            </Radio.Group>
                          }
                        </div>
                      </Loading>
                    </div>
                    <div class='right-wrap'>
                      <div class='search-wrap'>
                        <Input
                          behavior={'simplicity'}
                          modelValue={this.selectData.optionsSearch}
                          clearable
                          onUpdate:modelValue={v => this.debounceHandleOptionSearch(v)}
                        >
                          {{
                            prefix: () => (
                              <span class='search-icon'>
                                <span class='icon-monitor icon-mc-search' />
                              </span>
                            ),
                          }}
                        </Input>
                      </div>
                      <Loading loading={this.selectData.rightLoading}>
                        <div class='list-wrap-02'>
                          {this.optionsFilter.length ? (
                            this.optionsFilter.map(item => (
                              <Popover
                                key={item.id}
                                content={item.id}
                                placement={'right'}
                                popoverDelay={[300, 0]}
                              >
                                <div
                                  class='list-item'
                                  onClick={() => this.handleSelectDimension(item)}
                                >
                                  {item.name}
                                </div>
                              </Popover>
                            ))
                          ) : (
                            <div class='no-data'>
                              <EmptyStatus
                                scene='part'
                                type={this.selectData.optionsSearch ? 'search-empty' : 'empty'}
                                onOperation={this.handleNoDataOperation}
                              />
                            </div>
                          )}
                        </div>
                      </Loading>

                      <div
                        class='del-wrap'
                        onClick={() => this.handleDelete()}
                      >
                        <span class='icon-monitor icon-mc-delete-line' />
                        <span>{this.t('删除')}</span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div>
                    {this.searchList.length ? (
                      <ul class='list-wrap'>
                        {this.searchList.map((item, index) => (
                          <Popover
                            key={index}
                            content={item.id}
                            placement={'right'}
                            popoverDelay={[300, 0]}
                          >
                            <li onClick={() => this.handleSelect(item)}>{item.name}</li>
                          </Popover>
                        ))}
                      </ul>
                    ) : (
                      <div class='no-data-msg'>{''}</div>
                    )}
                    <div
                      style={{ display: this.dimesionKey ? 'flex' : 'none' }}
                      class='extension'
                      onClick={() => this.handleDelete()}
                    >
                      <i class='icon-monitor icon-chahao mr-8' />
                      <span>{this.t('删除')}</span>
                    </div>
                  </div>
                ),
            }}
          </Popover>
        </span>
      </Popover>
    );
  },
});
