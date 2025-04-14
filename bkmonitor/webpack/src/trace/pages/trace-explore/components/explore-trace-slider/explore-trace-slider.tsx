import { defineComponent } from 'vue';

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
import { Sideslider } from 'bkui-vue';

import TraceDetail from '../../../main/inquire-content/trace-detail';
import TraceDetailHeader from '../../../main/inquire-content/trace-detail-header';

export default defineComponent({
  name: 'ExploreTraceSlider',
  props: {
    /* 是否显示组件 */
    isShow: {
      type: Boolean,
      required: true,
    },
    /** 当前选中的应用 ID */
    application: {
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
    showChange: (isShow: boolean) => typeof isShow === 'boolean',
  },
  setup(props, { emit }) {
    /**
     * @description 关闭侧边栏回调
     *
     */
    function handleSliderClose() {
      emit('showChange', false);
    }

    return {
      handleSliderClose,
    };
  },
  render() {
    const { isShow, application, traceId } = this.$props;
    const { handleSliderClose } = this;

    return (
      <Sideslider
        width='80%'
        class='explore-trace-slider'
        v-slots={{
          header: () => (
            <TraceDetailHeader
              appName={application}
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
            ref='traceDetailElem'
            appName={application}
            traceID={traceId}
            isInTable
          />
        </div>
      </Sideslider>
    );
  },
});
