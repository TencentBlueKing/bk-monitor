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
import { defineComponent, ref as deepRef, watch } from 'vue';

import { Sideslider } from 'bkui-vue';
import { traceDetail } from 'monitor-api/modules/apm_trace';

import { QUERY_TRACE_RELATION_APP } from '../../../../store/constant';
import { useTraceStore } from '../../../../store/modules/trace';
import TraceDetail from '../../../main/inquire-content/trace-detail';
import TraceDetailHeader from '../../../main/inquire-content/trace-detail-header';

import './explore-trace-slider.scss';

export default defineComponent({
  name: 'ExploreTraceSlider',
  props: {
    /* 是否显示组件 */
    isShow: {
      type: Boolean,
      required: true,
    },
    /** 当前选中的应用 ID */
    appName: {
      type: String,
      required: true,
    },
    /** 当前选中的 traceID */
    traceId: {
      type: String,
      required: true,
    },
  },
  emits: {
    sliderClose: () => true,
  },
  setup(props, { emit }) {
    const store = useTraceStore();

    /** TraceDetail 组件实例 */
    const traceDetailRef = deepRef<InstanceType<typeof TraceDetail>>(null);

    watch(
      () => props.isShow,
      val => {
        if (val && props.traceId) {
          getTraceDetails();
        }
      }
    );

    /**
     * @description 获取 Trace 详情数据
     *
     */
    async function getTraceDetails() {
      // searchCancelFn();
      store.setTraceDetail(true);
      store.setTraceLoaidng(true);

      const params: any = {
        bk_biz_id: window.bk_biz_id,
        app_name: props.appName,
        trace_id: props.traceId,
      };

      if (
        traceDetailRef.value?.activePanel !== 'statistics' &&
        (store.traceViewFilters.length > 1 ||
          (store.traceViewFilters.length === 1 && !store.traceViewFilters.includes('duration')))
      ) {
        const selects = store.traceViewFilters.filter(item => item !== 'duration' && item !== QUERY_TRACE_RELATION_APP); // 排除 耗时、跨应用追踪 选项
        params.displays = ['source_category_opentelemetry'].concat(selects);
      }
      if (traceDetailRef.value?.activePanel === 'timeline') {
        params[QUERY_TRACE_RELATION_APP] = store.traceViewFilters.includes(QUERY_TRACE_RELATION_APP);
      }
      await traceDetail(params)
        .then(async data => {
          await store.setTraceData({ ...data, appName: props.appName, trace_id: props.traceId });
          store.setTraceLoaidng(false);
        })
        .catch(() => null);
    }

    /**
     * @description 关闭侧边栏回调
     *
     */
    function handleSliderClose() {
      emit('sliderClose');
    }

    return {
      handleSliderClose,
    };
  },
  render() {
    const { isShow, appName, traceId } = this.$props;
    const { handleSliderClose } = this;
    return (
      <Sideslider
        width='80%'
        class='explore-trace-slider'
        v-slots={{
          header: () => (
            <TraceDetailHeader
              appName={appName}
              traceId={traceId}
              isInTable
            />
          ),
        }}
        esc-close={false}
        is-show={isShow}
        multi-instance
        transfer
        onClosed={handleSliderClose}
      >
        <div class='explore-trace-slider-main'>
          <TraceDetail
            ref='traceDetailRef'
            appName={appName}
            traceID={traceId}
            isInTable
          />
        </div>
      </Sideslider>
    );
  },
});
