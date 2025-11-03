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
import { defineComponent, reactive, shallowRef, watch } from 'vue';

import { spanDetail } from 'monitor-api/modules/apm_trace';

import transformTraceTree from '../../../../components/trace-view/model/transform-trace-data';
import { useTraceStore } from '../../../../store/modules/trace';
import SpanDetails from '../../../main/span-details';

import type { Span } from '../../../../components/trace-view/typings';
export default defineComponent({
  name: 'ExploreSpanSlider',
  props: {
    /* 是否显示组件 */
    isShow: {
      type: Boolean,
      required: true,
    },
    /** 当前选中的应用 ID */
    appName: {
      type: String,
    },
    /** 当前选中的 spanID */
    spanId: {
      type: String,
    },
  },
  emits: {
    sliderClose: () => true,
  },
  setup(props, { emit }) {
    const store = useTraceStore();

    const spanDetails = reactive<Partial<Span>>({});
    const spanDetailLoading = shallowRef(false);

    watch(
      () => props.isShow,
      val => {
        if (val && props.spanId) {
          getSpanDetails();
        }
      },
      {
        immediate: true,
      }
    );

    /**
     * @description 获取 Span 详情数据
     *
     */
    async function getSpanDetails() {
      const params = {
        app_name: props.appName,
        span_id: props.spanId,
      };
      spanDetailLoading.value = true;
      await spanDetail(params)
        .then(result => {
          // TODO：这里是东凑西凑出来的数据，代码并不严谨，后期需要调整。
          store.setSpanDetailData(result);

          result.trace_tree.traceID = result?.trace_tree?.spans?.[0]?.traceID;
          Object.assign(spanDetails, transformTraceTree(result.trace_tree)?.spans?.[0]);
        })
        .catch(() => {})
        .finally(() => {
          spanDetailLoading.value = false;
        });
    }

    /**
     * @description 关闭侧边栏回调
     *
     */
    function handleSliderShowChange(isShow: boolean) {
      if (isShow) {
        return;
      }
      emit('sliderClose');
    }

    return {
      spanDetails,
      spanDetailLoading,
      handleSliderShowChange,
    };
  },
  render() {
    const { isShow, spanDetails, spanDetailLoading, handleSliderShowChange } = this;

    return (
      <SpanDetails
        isPageLoading={spanDetailLoading}
        show={isShow}
        spanDetails={spanDetails as Span}
        onShow={handleSliderShowChange}
      />
    );
  },
});
