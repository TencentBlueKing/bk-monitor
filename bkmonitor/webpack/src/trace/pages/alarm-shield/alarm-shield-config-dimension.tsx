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
 * to permit persons to whom the Software is furnished to do so, subject to
 * 6 the following conditions:
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
import { defineComponent, reactive, ref, shallowRef, watch } from 'vue';

import { PrimaryTable } from '@blueking/tdesign-ui';
import { listAlertTags } from 'monitor-api/modules/alert';
// import { getStrategyListV2 } from 'monitor-api/modules/strategies';
import { deepClone, random } from 'monitor-common/utils';
import { useI18n } from 'vue-i18n';

import { handleTransformToTimestamp } from '../../components/time-range/utils';
import { useAppStore } from '../../store/modules/app';
import DimensionConditionInput from './components/dimension-input/dimension-input';
import FormItem from './components/form-item';
import WhereDisplay from './components/where-display';

import './alarm-shield-config-dimension.scss';

export const dimensionPropData = () => ({
  key: random(8),
  dimension_conditions: [],
  strategy_id: '',
});

export default defineComponent({
  name: 'AlarmShieldConfigDimension',
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    value: {
      type: Object,
      default: () => dimensionPropData(),
    },
    isEdit: {
      type: Boolean,
      default: false,
    },
    onChange: {
      type: Function,
      default: _v => {},
    },
  },
  setup(props) {
    const { t } = useI18n();
    const localValue = shallowRef(dimensionPropData());
    const store = useAppStore();
    // 维度条件
    const dimensionCondition = reactive({
      conditionKey: random(8),
      dimensionList: [], // 维度列表
      metricMeta: null, // 获取条件候选值得参数
      conditionList: [], // 维度条件数据
      allNames: {}, // 维度名合集
    });

    const tagsDimension = ref([]);
    /* 策略相关数据 */
    // const strategyId = ref('');
    // const strategyList = ref([]);
    // const allStrategy = shallowReactive({
    //   list: [],
    //   current: 1,
    //   isEnd: false,
    // });
    // const strategyLoading = ref(false);
    // const strategyScrollLoading = ref(false);
    // const strategyItem = ref(null);
    // const metricList = ref([]);
    // const strategyPagination = reactive({
    //   current: 1,
    //   limit: 10,
    //   isEnd: false,
    // });
    /* 校验 */
    const errMsg = reactive({
      dimensionCondition: '',
    });

    // const debounceSearchStrategy = debounce(searchStrategy, 300, false);

    watch(
      () => props.show,
      async show => {
        if (show) {
          // strategyList.value = [];
          getDimensionList();
          // strategyList.value = await getStrategyList();
          // allStrategy.list = [...strategyList.value];
        }
      },
      {
        immediate: true,
      }
    );

    watch(
      () => props.value.key,
      key => {
        if (key === localValue.value.key) {
          return;
        }
        localValue.value = deepClone(props.value) as any;
        dimensionCondition.conditionList = localValue.value.dimension_conditions.map(item => ({
          ...item,
          dimensionName: item.name || item.key,
        }));
        dimensionCondition.conditionList.forEach(item => {
          dimensionCondition.allNames[item.key] = item.name || item.key;
        });
        dimensionCondition.conditionKey = random(8);
      }
    );

    function handleChange() {
      errMsg.dimensionCondition = '';
      props.onChange(localValue.value);
    }

    function handleDimensionConditionChange(v) {
      dimensionCondition.conditionList = v;
      localValue.value.dimension_conditions = dimensionCondition.conditionList
        .map(item => ({
          condition: item.condition,
          key: item.key,
          method: item.method,
          value: item.value,
          name: item.dimensionName,
        }))
        .filter(item => !!item.key);
      handleChange();
    }

    /* 获取策略列表数据 */
    // async function getStrategyList(serach = '') {
    //   return await getStrategyListV2({
    //     conditions: serach
    //       ? [
    //           {
    //             key: 'strategy_name',
    //             value: [serach],
    //           },
    //         ]
    //       : [],
    //     order_by: '-update_time',
    //     page: strategyPagination.current,
    //     page_size: strategyPagination.limit,
    //     type: 'monitor',
    //   })
    //     .then(res => res.strategy_config_list)
    //     .catch(() => []);
    // }

    /**
     * 策略搜索
     * @param v
     * @returns
     */
    // async function searchStrategy(v) {
    //   strategyLoading.value = true;
    //   strategyPagination.current = 1;
    //   strategyPagination.isEnd = false;
    //   strategyList.value = await getStrategyList(v);
    //   strategyLoading.value = false;
    //   return strategyList.value;
    // }

    /**
     * @description 滚动加载
     */
    // async function handleScrollEnd() {
    //   if (!strategyPagination.isEnd) {
    //     strategyScrollLoading.value = true;
    //     strategyPagination.current += 1;
    //     const list = await getStrategyList();
    //     strategyScrollLoading.value = false;
    //     if (list.length) {
    //       strategyList.value.push(...list);
    //     } else {
    //       strategyPagination.isEnd = true;
    //     }
    //     allStrategy.list = [...strategyList.value];
    //     allStrategy.current = strategyPagination.current;
    //     allStrategy.isEnd = strategyPagination.isEnd;
    //   }
    // }
    /**
     * @description 弹出策略选择
     * @param v
     */
    // function handleToggle(v: boolean) {
    //   if (v) {
    //     strategyList.value = [...allStrategy.list];
    //     strategyPagination.current = allStrategy.current;
    //     strategyPagination.isEnd = allStrategy.isEnd;
    //   }
    // }
    /**
     * @description 策略选择
     * @param v
     */
    // async function handleStrategyChange(v: string) {
    //   strategyId.value = v;
    //   localValue.value.strategy_id = v;
    //   handleChange();
    //   strategyItem.value = strategyList.value.find(item => item.id === strategyId.value);
    //   const {
    //     items: [{ query_configs: queryConfigs }]
    //   } = strategyItem.value;
    //   if (queryConfigs?.length) {
    //     const { metric_list: metricListTemp = [] } = await getMetricListV2({
    //       page: 1,
    //       page_size: queryConfigs.length,
    //       // result_table_label: scenario, // 不传result_table_label，避免关联告警出现不同监控对象时报错
    //       conditions: [{ key: 'metric_id', value: queryConfigs.map(item => item.metric_id) }]
    //     }).catch(() => ({}));
    //     metricList.value = metricListTemp;
    //     const [metricItem] = metricListTemp;
    //     if (metricItem) {
    //       dimensionCondition.metricMeta = {
    //         dataSourceLabel: metricItem.data_source_label,
    //         dataTypeLabel: metricItem.data_type_label,
    //         metricField: metricItem.metric_field,
    //         resultTableId: metricItem.result_table_id,
    //         indexSetId: metricItem.index_set_id
    //       };
    //     } else {
    //       dimensionCondition.metricMeta = null;
    //     }
    //     const dimensionList = !!metricList.value.length
    //       ? metricList.value.reduce((pre, cur) => {
    //           const dimensionList = pre
    //             .concat(cur.dimensions.filter(item => typeof item.is_dimension === 'undefined' || item.is_dimension))
    //             .filter((item, index, arr) => arr.map(item => item.id).indexOf(item.id, 0) === index);
    //           return dimensionList;
    //         }, [])
    //       : [];
    //     dimensionCondition.dimensionList = [...dimensionList, ...tagsDimension.value];
    //     dimensionCondition.conditionKey = random(8);
    //   }
    // }

    /**
     * @description 无策略情况获取维度列表
     */
    async function getDimensionList() {
      const [startTime, endTime] = handleTransformToTimestamp(['now-7d', 'now']);
      // 获取tags
      const tags = await listAlertTags({
        conditions: [],
        query_string: '',
        status: [],
        start_time: startTime,
        end_time: endTime,
        bk_biz_ids: [store.bizId || window.bk_biz_id],
      }).catch(() => []);
      const tagsDimensionTemp = tags.map(item => ({ ...item, type: 'tags' }));
      tagsDimension.value = tagsDimensionTemp;
      dimensionCondition.dimensionList = tagsDimensionTemp;
      dimensionCondition.conditionKey = random(8);
    }

    function validate() {
      if (!dimensionCondition.conditionList.length) {
        errMsg.dimensionCondition = t('维度选择不能为空');
      }
      return Object.keys(errMsg).every(key => !errMsg[key]);
    }

    function renderFn() {
      return (
        <div class={['alarm-shield-config-dimension-component', { show: props.show }]}>
          <FormItem
            class='mt24'
            errMsg={errMsg.dimensionCondition}
            label={t('维度选择')}
            require={true}
          >
            {props.isEdit ? (
              <div class='max-w836'>
                <PrimaryTable
                  columns={[
                    {
                      colKey: 'name',
                      title: t('维度条件'),
                      cell: () => {
                        if (dimensionCondition.conditionList.length) {
                          return (
                            <WhereDisplay
                              key={dimensionCondition.conditionKey}
                              allNames={dimensionCondition.allNames}
                              readonly={true}
                              value={dimensionCondition.conditionList}
                            />
                          );
                        }
                        return '--';
                      },
                    },
                  ]}
                  bordered={true}
                  data={[{}]}
                  maxHeight={450}
                  rowKey='key'
                />
              </div>
            ) : (
              <div class='dimension-select-content'>
                <DimensionConditionInput
                  key={dimensionCondition.conditionKey}
                  class='mr-16'
                  conditionList={dimensionCondition.conditionList}
                  dimensionsList={dimensionCondition.dimensionList}
                  isDimensionGroup={true}
                  metricMeta={dimensionCondition.metricMeta}
                  onChange={v => handleDimensionConditionChange(v)}
                />
                {/* <Select
                  class='mb-8'
                  modelValue={strategyId.value}
                  scrollHeight={216}
                  filterable={true}
                  clearable={false}
                  inputSearch={false}
                  scrollLoading={strategyScrollLoading.value}
                  remoteMethod={debounceSearchStrategy}
                  placeholder={t('基于策略选择')}
                  onScroll-end={handleScrollEnd}
                  onToggle={handleToggle}
                  onUpdate:modelValue={v => handleStrategyChange(v)}
                  popoverOptions={{
                    extCls: 'shield-dimension-select-list-wrap'
                  }}
                >
                  <Loading loading={strategyLoading.value}>
                    <div class='select-list-wrap'>
                      {strategyList.value.map(item => (
                        <Select.Option
                          key={item.id}
                          id={item.id}
                          name={item.name}
                        ></Select.Option>
                      ))}
                    </div>
                  </Loading>
                </Select> */}
              </div>
            )}
          </FormItem>
        </div>
      );
    }
    return {
      renderFn,
      validate,
      localValue,
      dimensionCondition,
    };
  },
  render() {
    return this.renderFn();
  },
});
