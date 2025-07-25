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
import { type PropType, defineComponent, reactive, ref } from 'vue';

import { Popover } from 'bkui-vue';
import { getVariableValue } from 'monitor-api/modules/grafana';
import { random } from 'monitor-common/utils';
import { NUMBER_CONDITION_METHOD_LIST, STRING_CONDITION_METHOD_LIST } from 'monitor-pc/constant/constant';
import { useI18n } from 'vue-i18n';

import type {
  ICommonItem,
  IWhereItem,
  MetricDetail,
} from 'monitor-pc/pages/strategy-config/strategy-config-set-new/typings';

import './where-display.scss';

export default defineComponent({
  name: 'WhereDisplay',
  props: {
    value: {
      type: Array as PropType<IWhereItem[]>,
      default: () => [],
    },
    groupByList: {
      type: Array as PropType<ICommonItem[]>,
      default: () => [],
    },
    metric: {
      type: Object as PropType<MetricDetail>,
      default: () => null,
    },
    allWhereValueMap: {
      type: Map as PropType<Map<string, ICommonItem[]>>,
      default: () => new Map(),
    },
    readonly: {
      type: Boolean,
      default: false,
    },
    allNames: {
      type: Object,
      default: () => ({}),
    },
    onValueMapChange: {
      type: Function as PropType<(_v: Map<string, ICommonItem[]>) => void>,
      default: _v => {},
    },
  },
  setup(props) {
    const { t } = useI18n();
    const maps = reactive<{
      methodNameMap: Map<string, string>;
      whereNameMap: Map<number | string, string>;
      whereValueMap: Map<string, ICommonItem[]>;
    }>({
      whereNameMap: new Map(),
      methodNameMap: new Map(),
      whereValueMap: new Map(),
    });
    const valueKey = ref(random(8));

    init();

    function init() {
      if (!props.readonly) {
        handleGetWhereOption();
        props.groupByList.forEach(item => maps.whereNameMap.set(item.id, item.name as string));
      }
      const methodList = [...STRING_CONDITION_METHOD_LIST, ...NUMBER_CONDITION_METHOD_LIST];
      methodList.forEach(item => maps.methodNameMap.set(item.id, item.name));
    }

    function handleValueMap(mapObject: Map<string, ICommonItem[]>) {
      props.onValueMapChange(mapObject);
    }

    /**
     * @description 获取条件的可选项数据
     */
    async function handleGetWhereOption() {
      // eslint-disable-next-line @typescript-eslint/naming-convention
      const { data_source_label, data_type_label, metric_field, result_table_id } = props.metric;
      const promiseList = props.value.map(item => {
        const params = {
          params: {
            field: item.key,
            data_source_label,
            data_type_label,
            metric_field,
            result_table_id,
            where: [],
          },
          type: 'dimension',
        };
        if (props.allWhereValueMap.get(item.key)) {
          maps.whereValueMap.set(item.key, props.allWhereValueMap.get(item.key));
          return null;
        }
        return getVariableValue(params).then(res => {
          maps.whereValueMap.set(
            item.key,
            res.map(set => ({ id: set.label, name: set.value }))
          );
          /* 将变量保存在父组件 */
          const valueMap = new Map(props.allWhereValueMap);
          valueMap.set(
            item.key,
            res.map(set => ({ id: set.label, name: set.value }))
          );
          handleValueMap(valueMap);
        });
      });
      await Promise.all(promiseList);
      valueKey.value = random(8);
    }
    /**
     * @description 处理条件值
     * @param value
     * @param key
     * @returns
     */
    function handleValue(value, key) {
      const options = maps.whereValueMap.get(key) || [];
      const names = value.map(val => {
        const item = options.find(item => item.id === val);
        return item?.name || val;
      });
      return names.toString() || `${t('空')}`;
    }

    function getFieldName(item) {
      if (props.readonly) {
        return props.allNames[item?.key] || item.key;
      }
      return maps.whereNameMap.get(item.key) || item.key;
    }

    function renderFn() {
      return (
        <span class='where-display-wrap'>
          {props.value.map((item, index) => (
            <span class='where-item'>
              {!!item.condition && !!index ? <span class='where-condition'>{` ${item.condition} `}</span> : undefined}
              <Popover
                content={item?.key}
                disabled={!item?.key || item?.key === getFieldName(item)}
                placement={'top'}
                popoverDelay={[300, 0]}
              >
                <span class='where-field'>{` ${getFieldName(item)} `}</span>
              </Popover>
              <span class='where-method'>{` ${maps.methodNameMap.get(item.method) || item.method} `}</span>
              <span
                key={valueKey.value}
                class='where-content'
              >
                {handleValue(item.value, item.key)}
              </span>
            </span>
          ))}
        </span>
      );
    }

    return {
      renderFn,
      maps,
    };
  },
  render() {
    return this.renderFn();
  },
});
