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
import { defineComponent, reactive, ref, shallowRef, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Checkbox, Loading, Select, Table } from 'bkui-vue';
import { getMetricListV2, getStrategyListV2, getStrategyV2, plainStrategyList } from 'monitor-api/modules/strategies';
import { random } from 'monitor-common/utils';

import DimensionConditionInput from './components/dimension-input';
import FormItem from './components/form-item';
import StrategyDetail from './components/strategy-detail';
import WhereDisplay from './components/where-display';
import AlarmShieldConfigScope, { scopeData } from './alarm-shield-config-scope';

import './alarm-shield-config-strategy.scss';

export const strategyDataProp = () => ({
  key: random(8),
  scopeData: scopeData(),
  id: [],
  level: [],
  dimension_conditions: []
});

export default defineComponent({
  name: 'AlarmShieldConfigStrategy',
  props: {
    show: {
      type: Boolean,
      default: false
    },
    value: {
      type: Object,
      default: () => strategyDataProp()
    },
    isEdit: {
      type: Boolean,
      default: false
    },
    isClone: {
      type: Boolean,
      default: false
    },
    onChange: {
      type: Function,
      default: () => {}
    }
  },
  setup(props) {
    const { t } = useI18n();
    const strategyList = shallowRef([]);
    const strategyId = ref([]);

    // 策略内容展示
    const strategyData = shallowRef(null);
    // 是否展示策略内容
    const isShowDetail = ref(false);

    // 维度条件
    const dimensionCondition = reactive({
      conditionKey: random(8),
      dimensionList: [], // 维度列表
      metricMeta: null, // 获取条件候选值得参数
      conditionList: [], // 维度条件数据
      allNames: {} // 维度名合集
    });
    // 告警级别限制条件
    const levelOptional = ref([]);
    // 告警级别
    const noticeLever = ref([]);
    // 告警级别选项
    const levelMap = [
      {
        id: 1,
        name: t('致命')
      },
      {
        id: 2,
        name: t('预警')
      },
      {
        id: 3,
        name: t('提醒')
      }
    ];
    const loading = ref(false);

    const localValue = ref(strategyDataProp());

    const errMsg = reactive({
      strategyId: '',
      level: ''
    });

    /**
     * @description 初始化
     */
    watch(
      () => props.show,
      async (v: boolean) => {
        if (v) {
          if (!strategyList.value.length) {
            loading.value = true;
            const data = await plainStrategyList().catch(() => []);
            strategyList.value = data;
            loading.value = false;
          }
        }
      },
      {
        immediate: true
      }
    );

    /**
     * @description 回填数据
     */
    watch(
      () => props.value.key,
      key => {
        if (key === localValue.value.key) {
          return;
        }
        localValue.value = props.value as any;
        strategyId.value = localValue.value.id;
        dimensionCondition.conditionList = localValue.value.dimension_conditions.map(item => ({
          ...item,
          dimensionName: item.name || item.key
        }));
        dimensionCondition.conditionList.forEach(item => {
          dimensionCondition.allNames[item.key] = item.name || item.key;
        });
        noticeLever.value = localValue.value.level;
        dimensionCondition.conditionKey = random(8);
        localValue.value.scopeData.key = random(8);
        handleStrategyChange(true);
      }
    );

    function handleChange() {
      props.onChange(localValue.value);
    }

    /**
     * @description 策略选择
     * @returns
     */
    function handleStrategyChange(isInit = false) {
      clearErrMsg();
      if (JSON.stringify(localValue.value.id) !== JSON.stringify(strategyId.value) && !isInit) {
        handleLevelChange([]);
      }
      localValue.value.id = strategyId.value;
      if (!isInit) {
        handleChange();
      }
      if (strategyId.value.length === 0) {
        levelOptional.value = [];
        dimensionCondtionInit();
        return;
      }
      if (strategyId.value.length === 1) {
        getStrategyV2({ id: strategyId.value[0] })
          .then(data => {
            strategyData.value = data;
            levelOptional.value = data.detects.map(item => item.level);
            isShowDetail.value = true;
            setDimensionConditionParams([data]);
          })
          .catch(() => {
            isShowDetail.value = false;
          });
      } else {
        strategyLevelFilter(strategyId.value);
        isShowDetail.value = true;
      }
    }
    function handleClear() {
      handleLevelChange([]);
    }
    /**
     * @description 初始化维度条件
     */
    function dimensionCondtionInit() {
      dimensionCondition.dimensionList = [];
      dimensionCondition.metricMeta = null;
      dimensionCondition.conditionList = [];
    }

    /**
     * @description 获取策略内的维度
     * @param strategys
     */
    async function setDimensionConditionParams(strategys: any[]) {
      if (strategys.length) {
        const metricIds = [];
        strategys.forEach(item => {
          item.items?.[0].query_configs.forEach(queryConfig => {
            if (!metricIds.includes(queryConfig.metric_id)) {
              metricIds.push(queryConfig.metric_id);
            }
          });
        });
        const { metric_list: metricList = [] } = await getMetricListV2({
          page: 1,
          page_size: metricIds.length,
          conditions: [{ key: 'metric_id', value: metricIds }]
        }).catch(() => ({}));
        const [metricItem] = metricList;
        if (metricItem) {
          dimensionCondition.metricMeta = {
            dataSourceLabel: metricItem.data_source_label,
            dataTypeLabel: metricItem.data_type_label,
            metricField: metricItem.metric_field,
            resultTableId: metricItem.result_table_id,
            indexSetId: metricItem.index_set_id
          };
        } else {
          dimensionCondition.metricMeta = null;
        }
        dimensionCondition.dimensionList = (
          !!metricList.length
            ? metricList.reduce((pre, cur) => {
                const dimensionList = pre
                  .concat(cur.dimensions.filter(item => typeof item.is_dimension === 'undefined' || item.is_dimension))
                  .filter((item, index, arr) => arr.map(item => item.id).indexOf(item.id, 0) === index);
                return dimensionList;
              }, [])
            : []
        ).filter(item => !['bk_target_ip', 'bk_target_cloud_id', 'bk_topo_node'].includes(item.id));
        dimensionCondition.conditionKey = random(8);
      }
    }
    /**
     *
     * @param ids
     */
    async function strategyLevelFilter(ids: number[]) {
      const list = await getStrategyListV2({
        conditions: [
          {
            key: 'strategy_id',
            value: ids
          }
        ]
      })
        .then(res => res.strategy_config_list)
        .catch(() => []);
      const allLevel = list.reduce((pre, cur) => {
        const curLevel = cur.detects.map(item => item.level);
        const res = Array.from(new Set(curLevel.concat(pre)));
        return res;
      }, []);
      levelOptional.value = allLevel;
      setDimensionConditionParams(list);
    }

    /**
     * @description 维度选择
     * @param v
     */
    function handleDimensionConditionChange(v) {
      dimensionCondition.conditionList = v;
      localValue.value.dimension_conditions = dimensionCondition.conditionList
        .map(item => ({
          condition: item.condition,
          key: item.key,
          method: item.method,
          value: item.value,
          name: item.dimensionName
        }))
        .filter(item => !!item.key);
      handleChange();
    }

    /**
     * @description 屏蔽范围
     * @param v
     */
    function handleScopeChange(v) {
      localValue.value.scopeData = v;
      handleChange();
    }

    /**
     * @description 告警级别切换
     * @param v
     */
    function handleLevelChange(v) {
      clearErrMsg();
      noticeLever.value = v;
      localValue.value.level = v;
      handleChange();
    }

    function clearErrMsg() {
      Object.keys(errMsg).forEach(key => {
        errMsg[key] = '';
      });
    }
    function validate() {
      if (!strategyId.value.length) {
        errMsg.strategyId = t('选择屏蔽策略');
      }
      if (strategyId.value.length && !noticeLever.value.length) {
        errMsg.level = t('至少选择一种告警等级');
      }
      return Object.keys(errMsg).every(key => !errMsg[key]);
    }

    return {
      strategyList,
      dimensionCondition,
      strategyData,
      strategyId,
      t,
      errMsg,
      loading,
      isShowDetail,
      localValue,
      noticeLever,
      levelMap,
      levelOptional,
      validate,
      handleStrategyChange,
      handleDimensionConditionChange,
      handleScopeChange,
      handleLevelChange,
      handleClear
    };
  },
  render() {
    return (
      <div class={['alarm-shield-config-strategy-component', { show: this.show }]}>
        <Loading loading={this.loading}>
          <FormItem
            class='mt24'
            label={this.t('屏蔽策略')}
            require={true}
            errMsg={this.errMsg.strategyId}
          >
            <div>
              <Select
                class='width-940'
                modelValue={this.strategyId}
                multiple={true}
                filterable={true}
                selectedStyle={'checkbox'}
                onUpdate:modelValue={v => (this.strategyId = v)}
                onToggle={() => this.handleStrategyChange()}
                onClear={this.handleClear}
              >
                {this.strategyList.map(item => (
                  <Select.Option
                    key={item.id}
                    label={item.name}
                    value={item.id}
                  >
                    {{
                      default: () => (
                        <span>
                          <span style='margin-right: 9px'>{item.name}</span>
                          <span style='color: #c4c6cc'>{`${item.first_label_name}-${item.second_label_name}（#${item.id}）`}</span>
                        </span>
                      )
                    }}
                  </Select.Option>
                ))}
              </Select>
            </div>
            {!!this.isShowDetail && this.strategyId.length === 1 && (
              <StrategyDetail
                class='mt10'
                strategyData={this.strategyData}
              ></StrategyDetail>
            )}
          </FormItem>
          {!!this.isShowDetail && (
            <FormItem
              class='mt24'
              label={this.t('维度选择')}
            >
              {this.isEdit ? (
                <div class='max-w836'>
                  <Table
                    data={[{}]}
                    maxHeight={450}
                    border={['outer']}
                    columns={[
                      {
                        id: 'name',
                        label: () => this.t('维度条件'),
                        render: () =>
                          (() => {
                            if (this.dimensionCondition.conditionList.length) {
                              return (
                                <WhereDisplay
                                  value={this.dimensionCondition.conditionList}
                                  readonly={true}
                                  allNames={this.dimensionCondition.allNames}
                                  key={this.dimensionCondition.conditionKey}
                                ></WhereDisplay>
                              );
                            }
                            return '--';
                          })()
                      }
                    ]}
                  ></Table>
                </div>
              ) : (
                <DimensionConditionInput
                  key={this.dimensionCondition.conditionKey}
                  conditionList={this.dimensionCondition.conditionList}
                  dimensionsList={this.dimensionCondition.dimensionList}
                  metricMeta={this.dimensionCondition.metricMeta}
                  onChange={v => this.handleDimensionConditionChange(v)}
                ></DimensionConditionInput>
              )}
            </FormItem>
          )}
          {!!this.isShowDetail && (
            <AlarmShieldConfigScope
              isEdit={this.isEdit}
              show={true}
              require={false}
              filterTypes={['ip', 'node']}
              value={this.localValue.scopeData}
              onChange={v => this.handleScopeChange(v)}
            ></AlarmShieldConfigScope>
          )}
          <FormItem
            label={this.t('告警等级')}
            require={true}
            class='mt24'
            errMsg={this.errMsg.level}
          >
            <Checkbox.Group
              class='mt8'
              modelValue={this.noticeLever}
              onUpdate:modelValue={this.handleLevelChange}
            >
              {this.levelMap.map(item => (
                <Checkbox
                  key={item.id}
                  disabled={!this.levelOptional.includes(item.id)}
                  label={item.id}
                >
                  {item.name}
                </Checkbox>
              ))}
            </Checkbox.Group>
          </FormItem>
        </Loading>
      </div>
    );
  }
});
