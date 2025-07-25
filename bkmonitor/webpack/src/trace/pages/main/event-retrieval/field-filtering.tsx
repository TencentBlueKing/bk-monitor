/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
import { type PropType, defineComponent, reactive, ref, toRefs, watch } from 'vue';

import { Exception } from 'bkui-vue';
import { deepClone } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';

import { useTraceStore } from '../../../store/modules/trace';
import FieldList, { type IDimissionItem, type TraceFieldValue } from './field-list';

import type { FieldListType, IFilterCondition } from 'monitor-pc/pages/data-retrieval/typings';

import './field-filtering.scss';
/**
 * @description: 查询结果统计组件
 */

const FIELD_VALUE_BASE_INFO = {
  type: 'string', // 数据类型
  dimensions: [], // 值
  checked: true, // 是否选中
  total: 0,
  showMore: false, // 是否展开更多的条件
};

const IProps = {
  value: {
    type: Array as PropType<TraceFieldValue[]>,
    default: () => [],
  },
  total: {
    type: Number,
    default: 0,
  },
};

export default defineComponent({
  name: 'FieldFiltering',
  props: IProps,
  emits: ['addCondition', 'change'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const store = useTraceStore();
    const localValue = ref<TraceFieldValue[]>([]);
    const statusCodes = reactive<TraceFieldValue>({
      ...FIELD_VALUE_BASE_INFO,
      key: 'statusCodes',
      // field: 'status.code',
      field: 'root_service_status_code',
      fieldName: t('状态码'),
      list_key: 'root_service_status_code',
    });
    const rootService = reactive<TraceFieldValue>({
      ...FIELD_VALUE_BASE_INFO,
      key: 'rootService',
      // field: 'resource.service.name',
      field: 'root_service',
      fieldName: t('入口服务'),
      list_key: 'root_service',
    });
    const rootEndpoint = reactive<TraceFieldValue>({
      ...FIELD_VALUE_BASE_INFO,
      key: 'rootEndpoint',
      // field: 'span_name',
      field: 'root_span_name',
      fieldName: t('入口接口'),
      list_key: 'root_span_name',
    });
    const category = reactive<TraceFieldValue>({
      ...FIELD_VALUE_BASE_INFO,
      key: 'category',
      // field: 'kind',
      field: 'root_service_category',
      fieldName: t('调用类型'),
      list_key: 'root_service_category',
    });

    const spanServiceName = reactive<TraceFieldValue>({
      ...FIELD_VALUE_BASE_INFO,
      key: 'service.name',
      field: 'resource.service.name',
      fieldName: t('所属服务'),
      list_key: 'service.name',
    });
    const spanName = reactive<TraceFieldValue>({
      ...FIELD_VALUE_BASE_INFO,
      key: 'span_name',
      field: 'span_name',
      fieldName: t('Span 名称'),
      list_key: 'span_name',
    });
    const statusCode = reactive<TraceFieldValue>({
      ...FIELD_VALUE_BASE_INFO,
      key: 'status',
      field: 'status.code',
      fieldName: t('状态码'),
      list_key: 'status',
    });
    const kind = reactive<TraceFieldValue>({
      ...FIELD_VALUE_BASE_INFO,
      key: 'kind',
      field: 'kind',
      fieldName: t('调用类型'),
      list_key: 'kind',
    });

    const interfaceType = reactive<TraceFieldValue>({
      ...FIELD_VALUE_BASE_INFO,
      key: 'kind',
      field: 'kind',
      fieldName: t('接口类型'),
      list_key: 'kind',
    });
    const interfaceName = reactive<TraceFieldValue>({
      ...FIELD_VALUE_BASE_INFO,
      key: 'span_name',
      field: 'span_name',
      fieldName: t('接口名'),
      list_key: 'span_name',
    });
    const interfaceServiceName = reactive<TraceFieldValue>({
      ...FIELD_VALUE_BASE_INFO,
      key: 'service_name',
      field: 'resource.service.name',
      fieldName: t('所属Service'),
      list_key: 'service_name',
    });

    const serviceNameInServiceStatistic = reactive<TraceFieldValue>({
      ...FIELD_VALUE_BASE_INFO,
      key: 'service_name',
      field: 'resource.service.name',
      fieldName: 'Service',
      list_key: 'service_name',
    });
    const serviceTypeInServiceStatistic = reactive<TraceFieldValue>({
      ...FIELD_VALUE_BASE_INFO,
      key: 'kind',
      field: 'kind',
      fieldName: t('服务类型'),
      list_key: 'kind',
    });

    const localValueMapping = {
      trace: [rootService, rootEndpoint, statusCodes, category],
      span: [spanServiceName, spanName, statusCode, kind],
      interfaceStatistics: [interfaceType, interfaceName, interfaceServiceName],
      serviceStatistics: [serviceNameInServiceStatistic, serviceTypeInServiceStatistic],
    };

    localValue.value = localValueMapping[store.listType] || [];

    const { total } = toRefs(props);
    /** 字段列表数据 */
    watch(
      () => store.traceList,
      () => {
        localValue.value = [rootService, rootEndpoint, statusCodes, category].map(item => {
          const dimensions = getFieldValueStatistics(item.list_key);
          const total = dimensions.length;
          return { ...item, dimensions, total };
        });
      }
    );

    watch(
      () => store.spanList,
      () => {
        localValue.value = [spanServiceName, spanName, statusCode, kind].map(item => {
          const dimensions = getFieldValueStatistics(item.list_key);
          const total = dimensions.length;
          return { ...item, dimensions, total };
        });
      }
    );

    watch(
      () => store.interfaceStatisticsList,
      () => {
        localValue.value = (localValueMapping[store.listType] || []).map(item => {
          const dimensions = getFieldValueStatistics(item.list_key);
          const total = dimensions.length;
          return { ...item, dimensions, total };
        });
      }
    );

    watch(
      () => store.serviceStatisticsList,
      () => {
        localValue.value = (localValueMapping[store.listType] || []).map(item => {
          const dimensions = getFieldValueStatistics(item.list_key);
          const total = dimensions.length;
          return { ...item, dimensions, total };
        });
      }
    );

    // 调用类型 的映射对象，将 value 转成 text 用作显示。
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const root_service_categoryMapping = {};
    /**
     * @desc 查询结果字段值统计
     * @param { String } field
     * @returns { IDimissionItem[] } dimensions
     */
    const getFieldValueStatistics = (field: string) => {
      const fieldObj: { [key: string]: number } = {};
      if (store.listType === 'trace') {
        store.traceList.forEach(item => {
          const fieldValue = ['root_service_status_code', 'root_service_category'].includes(field)
            ? item?.[field]?.value
            : item?.[field];
          if (fieldValue) {
            fieldObj[fieldValue] = fieldObj[fieldValue] ? fieldObj[fieldValue] + 1 : 1;
          }
          // 调用类型比较特殊，不能直接显示值，要显示他的别名。
          if (['root_service_category'].includes(field)) {
            item?.[field].value && (root_service_categoryMapping[item?.[field].value] = item?.[field].text);
          }
        });
      } else if (store.listType === 'span') {
        store.spanList.forEach(item => {
          let fieldValue = null;
          if (field === 'service.name') {
            fieldValue = item?.resource?.[field];
          } else if (field === 'status') {
            fieldValue = `${item?.status?.code}`;
          } else {
            fieldValue = item?.[field];
          }
          if (fieldValue) {
            fieldObj[fieldValue] = fieldObj[fieldValue] ? fieldObj[fieldValue] + 1 : 1;
          }
        });
      } else if (store.listType === 'interfaceStatistics') {
        store.interfaceStatisticsList.forEach(item => {
          const fieldValue = item?.[field];
          if (fieldValue) {
            fieldObj[fieldValue] = fieldObj[fieldValue] ? fieldObj[fieldValue] + 1 : 1;
          }
        });
      } else if (store.listType === 'serviceStatistics') {
        store.serviceStatisticsList.forEach(item => {
          const fieldValue = item?.[field];
          if (fieldValue) {
            fieldObj[fieldValue] = fieldObj[fieldValue] ? fieldObj[fieldValue] + 1 : 1;
          }
        });
      }
      const lenMapping = {
        trace: store.traceList.length,
        span: store.spanList.length,
        interfaceStatistics: store.interfaceStatisticsList.length,
        serviceStatistics: store.serviceStatisticsList.length,
      };
      const len = lenMapping[store.listType] || 0;
      const dimensions: IDimissionItem[] = [];
      Object.keys(fieldObj).forEach(key => {
        dimensions.push({
          id: key,
          percent: Math.round(((fieldObj[key] * 100) / len) * 100) / 100,
          // 调用类型比较特殊，不能直接显示值，要显示他的别名。
          alias: root_service_categoryMapping?.[key] || '',
        });
      });
      dimensions.sort((a, b) => b.percent - a.percent);
      return dimensions;
    };

    /**
     * @description: 添加过滤条件
     * @param {IFilterCondition} val
     * @return {*}
     */
    const handleAddCondition = (val: IFilterCondition.localValue) => {
      emit('addCondition', val);
    };

    /** 展开更多 */
    const handleShowMoreChange = (key: string) => {
      localValue.value = localValue.value.map(item => ({ ...item, showMore: item.key === key }));
    };

    const handleValueChange = (obj: FieldListType.IEvent['onCheckedChange']) => {
      const target = localValue.value.find(item => item.field === obj.field);
      if (target) {
        target.checked = obj.checked;
      }
      emit('change', deepClone(localValue.value));
    };

    const renderDom = () => (
      <div class='field-filtering-wrapper'>
        <div class='field-list-wrap'>
          {localValue.value.length ? (
            <FieldList
              total={total.value}
              value={localValue.value}
              onAddCondition={handleAddCondition}
              onShowMoreChange={handleShowMoreChange}
            />
          ) : (
            <Exception
              scene='part'
              type='empty'
            />
          )}
        </div>
      </div>
    );
    return {
      renderDom,
      total,
      handleAddCondition,
      handleValueChange,
      localValue,
    };
  },

  render() {
    return this.renderDom();
  },
});
