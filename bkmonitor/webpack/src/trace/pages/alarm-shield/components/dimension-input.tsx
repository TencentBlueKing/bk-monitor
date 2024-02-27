/* eslint-disable vue/one-component-per-file */
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
import { computed, defineComponent, PropType, ref, watch } from 'vue';
import { Message, Popover, TagInput } from 'bkui-vue';
import { alertTopN } from 'monitor-api/modules/alert';
import { getVariableValue } from 'monitor-api/modules/grafana';
import { CONDITION, NUMBER_CONDITION_METHOD_LIST, STRING_CONDITION_METHOD_LIST } from 'monitor-pc/constant/constant';

import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import { useAppStore } from '../../../store/modules/app';
import { IConditionItem, IDimensionItem, IMetricMeta } from '../typing';

import SelectInput, { ALL } from './select-input';

import './dimension-input.scss';

function topNDataStrTransform(value: string) {
  const result = value.replace(/(^")|("$)/g, '');
  return result;
}

export default defineComponent({
  name: 'DimensionConditionInput',
  props: {
    conditionList: {
      type: Array as PropType<IConditionItem[]>,
      default: () => []
    },
    dimensionsList: {
      type: Array as PropType<IDimensionItem[]>,
      default: () => []
    },
    metricMeta: {
      type: Object as PropType<IMetricMeta>,
      default: () => null
    },
    /* 将维度选择框改为分组(根据策略分组) */
    isDimensionGroup: {
      type: Boolean,
      default: false
    },
    onChange: {
      type: Function,
      default: _v => {}
    }
  },
  setup(props) {
    const store = useAppStore();
    const conditions = ref<IConditionItem[]>([]);
    const dimensionsValueMap = ref<Map<string, { id: string; name: string }[]>>(new Map());

    /* 当前维度合集 分组情况下使用*/
    const groupDimensionMap = ref<Map<string, IDimensionItem[]>>(new Map());

    const strategyList = ref([]);

    const metricMetaMap = ref<Map<string, any>>(new Map());

    const showAdd = computed(() => {
      if (!conditions.value.length) return false;
      const { key, value } = conditions.value[conditions.value.length - 1];
      return !!key && value?.length > 0;
    });

    init();
    function init() {
      const conditionList = props.conditionList
        .filter(item => item.key)
        .map(item => ({
          ...item,
          dimensionName: item.dimensionName || item.dimension_name || ''
        }));
      conditions.value = conditionList.length ? conditionList : ([handleGetDefaultCondition()] as any);
      if (props.isDimensionGroup) {
        groupDimensionMap.value.set(ALL, props.dimensionsList);
      }
    }
    function handleGetDefaultCondition(needCondition = true) {
      return Object.assign(
        {},
        {
          key: '',
          dimensionName: '',
          value: [],
          method: 'eq'
        },
        needCondition ? { condition: 'and' } : {}
      );
    }
    async function handleDimensionChange(item, v) {
      item.dimensionName = v;
      let id = v;
      props.dimensionsList.forEach(d => {
        if (d.id === v || d.name === v) {
          id = d.id as string;
        }
      });
      if (item.key !== id) {
        item.value = [];
      }
      item.key = id;
      if (id && !dimensionsValueMap.value.get(id)) {
        if (props.dimensionsList.find(d => d.id === id)?.type === 'tags') {
          getTopNValueList(id);
        } else {
          await getVariableValueList(id);
        }
      }
      handleConditionChange();
    }
    /**
     * @description 获取维度值可选项
     * @param id
     * @returns
     */
    async function getVariableValueList(id: string, strategy?) {
      if (!props.metricMeta && !strategy) return;
      let metricMetaTemp = props.metricMeta;
      if (!!strategy) {
        metricMetaTemp = metricMetaMap.value.get(strategy);
      }
      const { dataSourceLabel, metricField, dataTypeLabel, resultTableId } = metricMetaTemp;
      if (!dataSourceLabel || !metricField || !dataTypeLabel) return;
      const params: any = {
        bk_biz_id: store.bizId,
        type: 'dimension',
        params: {
          data_source_label: dataSourceLabel,
          data_type_label: dataTypeLabel,
          field: id,
          metric_field: metricField,
          result_table_id: resultTableId || '',
          where: []
        }
      };
      if (metricMetaTemp.dataSourceLabel === 'bk_log_search') {
        params.params.index_set_id = metricMetaTemp.indexSetId;
      }
      const { data, tips } = await getVariableValue(params, { needRes: true });
      if (!!tips?.length) {
        Message({
          theme: 'warning',
          message: tips
        });
      }
      const result = Array.isArray(data) ? data.map(item => ({ name: item.label, id: item.value })) : [];
      const { field } = params.params;
      dimensionsValueMap.value.set(field, result || []);
    }
    /**
     * @description 根据选择tags维度获取topn维度值
     * @param id
     */
    async function getTopNValueList(id: string) {
      const [startTime, endTime] = handleTransformToTimestamp(['now-7d', 'now']);
      alertTopN({
        conditions: [],
        query_string: '',
        status: [],
        fields: [id],
        size: 10,
        start_time: startTime,
        end_time: endTime
      })
        .then(data => {
          const fieldItem = data.fields?.find(item => item.field === id);
          const isChar = !!fieldItem?.is_char;
          const values = fieldItem?.buckets?.map(item => ({
            ...item,
            id: isChar ? topNDataStrTransform(item.id) : item.id
          }));
          dimensionsValueMap.value.set(id, values || []);
        })
        .catch(() => []);
    }
    function handleMehodChange(item, v) {
      item.method = v;
      handleConditionChange();
    }

    function getDimensionValues(key) {
      return dimensionsValueMap.value.get(key) || [];
    }
    /**
     * @description 粘贴
     * @param v
     * @param item
     * @returns
     */
    function handlePaste(v, item) {
      const SYMBOL = ';';
      /** 支持 空格 | 换行 | 逗号 | 分号 分割的字符串 */
      const valList = `${v}`.replace(/(\s+)|([,;])/g, SYMBOL)?.split(SYMBOL);
      const ret = [];
      valList.forEach(val => {
        !item.value.some(v => v === val) && val !== '' && item.value.push(val);
        if (!dimensionsValueMap.value.get(item.key)?.some(item => item.id === val)) {
          ret.push({
            id: val,
            name: val,
            show: true
          });
        }
      });
      handleConditionChange();
      return ret;
    }
    /**
     * @description 新增条件
     */
    function handleAddCondition() {
      conditions.value.push(handleGetDefaultCondition());
    }

    /**
     * @description 维度值变更
     * @param item
     * @param v
     */
    function handleDimensionValueChange(item, v) {
      item.value = v;
      handleConditionChange();
    }

    /**
     * @description 连接符
     * @param item
     * @param v
     */
    function handleConditionConditionChange(item, v) {
      item.condition = v;
      handleConditionChange();
    }

    /**
     * @description 删除当前维度
     * @param index
     */
    function handleDeleteKey(index: number) {
      const deleteList = conditions.value.splice(index, 1);
      if (!conditions.value.length) {
        conditions.value.push(handleGetDefaultCondition(false));
      } else {
        if (conditions.value[index] && (conditions.value[index - 1]?.condition || index === 0)) {
          delete conditions.value[index].condition;
        }
      }
      !!deleteList?.[0]?.key && handleConditionChange();
    }

    /**
     * @description 返回数据
     */
    function handleConditionChange() {
      props.onChange(conditions.value);
    }
    /**
     * @description 第一页的策略列表
     */
    function handleStrategyListInit(list) {
      strategyList.value = list;
    }

    function handleSetDimensionList(key, list) {
      groupDimensionMap.value.set(key, list);
    }

    function handleSetMetricMetaSet(strategy, obj) {
      metricMetaMap.value.set(strategy, obj);
    }
    /**
     * @description 选中维度后更新数据并获取维度值
     * @param item 当前的输入框数据
     * @param dimensionItem 选中的选项
     * @param meta 当前维度所属策略的参数信息
     * @param strategy 当前维度所属的策略
     */
    async function handleSelectDimension(item, dimensionItem, _meta, strategy) {
      item.dimensionName = dimensionItem.name;
      item.key = dimensionItem.id;
      if (!!item.key && !dimensionsValueMap.value.get(item.key)) {
        if (strategy === ALL) {
          await getTopNValueList(item.key);
        } else {
          await getVariableValueList(item.key, strategy);
        }
      }
      handleConditionChange();
    }

    return {
      conditions,
      dimensionsValueMap,
      showAdd,
      groupDimensionMap,
      strategyList,
      metricMetaMap,
      handleConditionConditionChange,
      handleDimensionChange,
      handleDeleteKey,
      handleMehodChange,
      getDimensionValues,
      handlePaste,
      handleDimensionValueChange,
      handleAddCondition,
      handleStrategyListInit,
      handleSetDimensionList,
      handleSetMetricMetaSet,
      handleSelectDimension
    };
  },
  render() {
    return (
      <div class='dimension-condition-input-component'>
        {this.conditions.map((item, index) => {
          return [
            item.condition && item.key && index > 0 ? (
              <ConditionCondition
                class='mb-8'
                item={item}
                key={`condition-${index}-${item.key}`}
                onChange={v => this.handleConditionConditionChange(item, v)}
              ></ConditionCondition>
            ) : undefined,
            <SelectInput
              class='mb-8'
              value={item.dimensionName}
              list={this.dimensionsList as any}
              dimesionKey={item.key}
              isDimensionGroup={this.isDimensionGroup}
              groupDimensionMap={this.groupDimensionMap}
              strategyList={this.strategyList}
              onChange={v => this.handleDimensionChange(item, v)}
              onDelete={() => this.handleDeleteKey(index)}
              dimensionSet={(key, list) => this.handleSetDimensionList(key, list)}
              metricMetaSet={(key, obj) => this.handleSetMetricMetaSet(key, obj)}
              onStrategyListInit={list => this.handleStrategyListInit(list)}
              onSelectDimension={(dimensionItem, meta, strategy) =>
                this.handleSelectDimension(item, dimensionItem, meta, strategy)
              }
            ></SelectInput>,
            item.dimensionName
              ? [
                  <ConditionMethod
                    value={item.method}
                    dimensionList={this.dimensionsList}
                    dimensionKey={item.key}
                    onChange={v => this.handleMehodChange(item, v)}
                  ></ConditionMethod>,
                  <TagInput
                    modelValue={item.value}
                    class='condition-item condition-item-value mb-8'
                    list={this.getDimensionValues(item.key)}
                    trigger={'focus'}
                    allowCreate={true}
                    allowAutoMatch={true}
                    pasteFn={v => this.handlePaste(v, item)}
                    onUpdate:modelValue={v => this.handleDimensionValueChange(item, v)}
                  ></TagInput>
                ]
              : undefined
          ];
        })}
        {!!this.showAdd && (
          <span
            class='condition-item condition-add mb-8'
            onClick={this.handleAddCondition}
          >
            <span class='icon-monitor icon-mc-add'></span>
          </span>
        )}
      </div>
    );
  }
});

const ConditionCondition = defineComponent({
  name: 'ConditionCondition',
  props: {
    item: {
      type: Object,
      default: () => null
    },
    onChange: {
      type: Function as PropType<(v: string) => void>,
      default: _v => {}
    }
  },
  setup(props) {
    const popoverRef = ref(null);
    const conditionList = ref(CONDITION);

    function handleSelect(item) {
      popoverRef.value?.hide();
      props.onChange(item.id);
    }
    return () => (
      <Popover
        placement='bottom-start'
        arrow={false}
        theme='light'
        trigger='click'
        ref={popoverRef}
        extCls='dimension-condition-input-condition-condition-component-pop'
      >
        {{
          default: () => (
            <input
              style={{ display: props.item.condition ? 'block' : 'none' }}
              class='condition-item condition-item-condition mb-8'
              readonly
              value={props.item.condition.toLocaleUpperCase()}
            ></input>
          ),
          content: () => (
            <div>
              <ul class='list-wrap'>
                {conditionList.value.map((item, index) => (
                  <li
                    key={index}
                    onClick={() => handleSelect(item)}
                  >
                    {item.name}
                  </li>
                ))}
              </ul>
            </div>
          )
        }}
      </Popover>
    );
  }
});

const ConditionMethod = defineComponent({
  name: 'ConditionMethod',
  props: {
    value: {
      type: String,
      default: ''
    },
    dimensionKey: {
      type: String,
      default: ''
    },
    dimensionList: {
      type: Array as PropType<any[]>,
      default: () => []
    },
    onChange: {
      type: Function as PropType<(v: string) => void>,
      default: () => {}
    }
  },
  setup(props) {
    const popoverRef = ref(null);
    const methodList = ref([]);

    const show = ref(false);

    watch(
      () => props.dimensionKey,
      key => {
        const { type } = props.dimensionList.find(item => item.id === key) || { type: 'string' };
        methodList.value = handleGetMethodList(type);
      },
      {
        immediate: true
      }
    );

    function getMethodNameById(id: string) {
      return NUMBER_CONDITION_METHOD_LIST.find(item => item.id === id)?.name || '';
    }
    function handleGetMethodList(type: 'string' | 'number') {
      if (type === 'number') {
        return NUMBER_CONDITION_METHOD_LIST;
      }
      return STRING_CONDITION_METHOD_LIST;
    }

    function handleSelect(item) {
      popoverRef.value?.hide();
      props.onChange(item.id);
    }

    return () => (
      <Popover
        placement='bottom-start'
        arrow={false}
        theme='light'
        trigger='click'
        ref={popoverRef}
        extCls='dimension-condition-input-condition-method-component-pop'
        onAfterHidden={() => (show.value = false)}
        onAfterShow={() => (show.value = true)}
      >
        {{
          default: () => (
            <span
              class={[
                'condition-item condition-item-method mb-8',
                {
                  active: show.value
                }
              ]}
            >
              {getMethodNameById(props.value)}
            </span>
          ),
          content: () => (
            <div>
              <ul class='list-wrap'>
                {methodList.value.map((item, index) => (
                  <li
                    key={index}
                    onClick={() => handleSelect(item)}
                  >
                    {item.name}
                  </li>
                ))}
              </ul>
            </div>
          )
        }}
      </Popover>
    );
  }
});
