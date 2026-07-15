/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { type PropType, type Ref, computed, defineComponent, inject, provide, ref } from 'vue';
import PanelK8s from '../../../pages/alarm-center/common-detail/components/panel-k8s';
import { handleTransformToTimestampMs } from '@/components/time-range/utils';
import { useAppStore } from '@/store/modules/app';
import { useTraceExploreStore } from '@/store/modules/explore';
import type { BookMarkModel } from '../../../plugins/typings';
import { PanelModel } from 'monitor-ui/chart-plugins/typings';
import ExceptionGuide from '../../../plugins/charts/exception-guide/exception-guide';
import type { DateValue } from '@blueking/date-picker';

import './index.scss';

export default defineComponent({
  name: 'K8sContainer',
  props: {
    sceneData: { type: Object as PropType<BookMarkModel>, required: true },
  },
  setup(props) {
    const serviceName = inject<Ref<string>>('serviceName');
    const appName = inject<Ref<string>>('appName');
    const spanId = inject<Ref<string>>('spanId', ref(''));
    const injectedBizId = inject<Ref<number | string> | undefined>('bizId', undefined);

    const traceStore = useTraceExploreStore();
    const timeRange = computed(() => handleTransformToTimestampMs(traceStore.timeRange as DateValue));
    const bizId = computed(() => {
      const fromInject = injectedBizId?.value;
      if (fromInject != null && fromInject !== '' && !Number.isNaN(+fromInject)) {
        return +fromInject;
      }
      return +(useAppStore().bizId || window.bk_biz_id || window.cc_biz_id || 0);
    });
    const isExceptionGuide = computed(
      () =>
        props.sceneData?.overview_panels?.length === 1 && props.sceneData?.overview_panels[0].type === 'exception-guide'
    );
    const singleChartPanel = computed(() =>
      isExceptionGuide ? new PanelModel(props.sceneData?.overview_panels[0]) : ({} as PanelModel)
    );

    // 注入span详情中需要的全部参数对象
    const traceSpanInfo = computed(() => ({
      spanId: spanId.value,
      bizId: bizId.value,
      serviceName: serviceName.value,
      appName: appName.value,
      timeRange: timeRange.value,
    }));

    provide('traceSpanInfo', traceSpanInfo);

    return () => (
      <div class='new-k8s-container-wrap'>
        {isExceptionGuide.value ? <ExceptionGuide panel={singleChartPanel.value} /> : <PanelK8s />}
      </div>
    );
  },
});
