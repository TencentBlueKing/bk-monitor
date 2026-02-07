/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { type PropType, defineComponent, onBeforeUnmount, onMounted, onUpdated, useTemplateRef } from 'vue';

import { i18n, QueryPanel, QueryPanelEmits, Vue2 } from '@blueking/monitor-vue2-components/index.mjs';

import type {
  IGetMetricListData,
  IGetMetricListParams,
} from 'monitor-pc/pages/query-template/components/metric/components/types';
import type { IFunctionOptionsItem } from 'monitor-pc/pages/query-template/components/type/query-config';
import type {
  AggCondition,
  AggFunction,
  IVariableModel,
  MetricDetailV2,
  QueryConfig,
} from 'monitor-pc/pages/query-template/typings';
import type { VariableModelType } from 'monitor-pc/pages/query-template/variables';

import '@blueking/monitor-vue2-components/index.css';
export default defineComponent({
  name: 'MonitorVue2',
  props: {
    queryConfig: {
      type: Object as PropType<QueryConfig>,
      default: () => ({}),
    },
    variables: {
      type: Array as PropType<VariableModelType[]>,
      default: () => [],
    },
    metricFunctions: {
      type: Array as PropType<IFunctionOptionsItem[]>,
      default: () => [],
    },
    hasAdd: {
      type: Boolean,
      default: false,
    },
    hasDelete: {
      type: Boolean,
      default: false,
    },
    hasVariableOperate: {
      type: Boolean,
      default: false,
    },
    getMetricList: {
      type: Function as PropType<(params: IGetMetricListParams) => Promise<IGetMetricListData>>,
    },
    onChangeCondition: {
      type: Function as PropType<(val: AggCondition[]) => void>,
      default: () => {},
    },
    onChangeDimension: {
      type: Function as PropType<(val: string[]) => void>,
      default: () => {},
    },
    onChangeFunction: {
      type: Function as PropType<(val: AggFunction[]) => void>,
      default: () => {},
    },
    onChangeInterval: {
      type: Function as PropType<(val: number | string) => void>,
      default: () => {},
    },
    onChangeMethod: {
      type: Function as PropType<(val: string) => void>,
      default: () => {},
    },
    onCreateVariable: {
      type: Function as PropType<(val: IVariableModel) => void>,
      default: () => {},
    },
    onDelete: {
      type: Function as PropType<() => void>,
      default: () => {},
    },
    onSelectMetric: {
      type: Function as PropType<(val: MetricDetailV2) => void>,
      default: () => {},
    },
  },
  setup(props, { emit }) {
    const componentWrapperRef = useTemplateRef<InstanceType<typeof QueryPanel>>('componentWrapperRef');
    Vue2.prototype.$t = (key: string) => key;
    console.log(props);
    let app = new Vue2({
      render: h => {
        return h(QueryPanel, {
          ref: 'componentRef',
          props,
          i18n,
        });
      },
    });
    onMounted(() => {
      app.$mount();
      componentWrapperRef.value.appendChild(app.$el);
      for (const eventName of QueryPanelEmits) {
        app.$refs.componentRef.$on(eventName, (...agrs) => {
          emit(eventName, ...agrs);
        });
      }
      onUpdated(() => {
        for (const [key, value] of Object.entries(props)) {
          app.$refs.componentRef[key] = value;
        }
        app.$refs.componentRef.$forceUpdate();
      });
    });

    onBeforeUnmount(() => {
      app.$el.parentNode.removeChild(app.$el);
      app.$destroy();
      app = null;
    });

    return () => <div ref='componentWrapperRef' />;
  },
});
