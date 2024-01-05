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
import { computed, defineComponent, onMounted, PropType, ref } from 'vue';
import { bkTooltips } from 'bkui-vue';

import { IDetectionConfig } from '../../../monitor-pc/pages/strategy-config/strategy-config-set-new/typings';
// @ts-ignore
import loadingIcon from '../../../monitor-ui/chart-plugins/icons/spinner.svg';
import { PanelModel } from '../../../monitor-ui/chart-plugins/typings';
import watermarkMaker from '../../../monitor-ui/monitor-echarts/utils/watermarkMaker';
import ChartRow from '../charts/chart-row/chart-row';
import ExceptionGuide from '../charts/exception-guide/exception-guide';
import RelatedLogChart from '../charts/related-log-chart/related-log-chart';
import TimeSeries from '../charts/time-series/time-series';
import { useReadonlyInject } from '../hooks';
import type * as PanelModelTraceVersion from '../typings';

import './chart-wrapper.scss';

export default defineComponent({
  name: 'ChartWrapperMigrated',
  directives: {
    bkTooltips
  },
  props: {
    panel: { required: true, type: Object as PropType<PanelModel> },
    /** 检测算法 */
    detectionConfig: { default: () => {}, type: Object as PropType<IDetectionConfig> },
    /* 是否可选中图表 */
    needCheck: { type: Boolean, default: false }
  },
  emits: ['chartCheck', 'collectChart', 'collapse', 'changeHeight', 'dimensionsOfSeries'],
  setup(props, { emit }) {
    // TODO: 该注入还没设置 provide 调用，后期需要补上
    const readonly = useReadonlyInject();

    /** 鼠标在图表内 */
    const showHeaderMoreTool = ref(false);
    /** 图表加载状态 */
    const loading = ref(false);
    /** 是否显示大图 */
    const showViewDetail = ref(false);
    /** 查看大图参数配置 */
    const viewQueryConfig = ref({});
    const errorMsg = ref('');
    /** 水印图 */
    const waterMaskImg = ref('');

    /** hover样式 */
    const needHoverStryle = computed(() => {
      // eslint-disable-next-line @typescript-eslint/naming-convention
      const { time_series_forecast, time_series_list } = props.panel?.options || {};
      return (time_series_list?.need_hover_style ?? true) && (time_series_forecast?.need_hover_style ?? true);
    });

    onMounted(() => {
      // @ts-ignore
      if (window.graph_watermark) {
        waterMaskImg.value = watermarkMaker(window.user_name || window.username);
      }
    });

    /**
     * @description: 供子组件更新loading的状态
     * @param {boolean} loading
     */
    function handleChangeLoading(v: boolean) {
      loading.value = v;
    }

    /**
     * @description: 错误处理
     * @param {string} msg
     */
    function handleErrorMsgChange(msg: string) {
      errorMsg.value = msg;
    }

    /**
     * @description: 清除错误
     */
    function handleClearErrorMsg() {
      errorMsg.value = '';
    }

    /**
     * @description: 关闭查看大图弹窗
     */
    function handleCloseViewDetail() {
      showViewDetail.value = false;
      viewQueryConfig.value = {};
    }

    function handleChartCheck() {
      emit('chartCheck', !props.panel.checked);
    }

    function handleCollapsed() {
      emit('collapse', !props.panel.collapsed);
    }

    function handlePanel2Chart() {
      switch (props.panel.type) {
        case 'row':
          return (
            <ChartRow
              panel={props.panel}
              clearErrorMsg={handleClearErrorMsg}
              onCollapse={handleCollapsed}
              onErrorMsg={handleErrorMsgChange}
            />
          );
        case 'exception-guide':
          return <ExceptionGuide panel={props.panel} />;
        case 'related-log-chart':
          return (
            <RelatedLogChart
              panel={props.panel}
              onLoading={handleChangeLoading}
              onErrorMsg={handleErrorMsgChange}
              clearErrorMsg={handleClearErrorMsg}
            />
          );
        default:
          return (
            <TimeSeries
              onLoading={handleChangeLoading}
              // 还不清楚该用新的还是旧的类型，这里先照旧
              panel={props.panel as PanelModelTraceVersion.PanelModel}
              showHeaderMoreTool={showHeaderMoreTool.value}
            />
          );
      }
    }

    return {
      needHoverStryle,
      showHeaderMoreTool,
      handlePanel2Chart,
      loading,
      readonly,
      handleChartCheck,
      showViewDetail,
      viewQueryConfig,
      handleCloseViewDetail,
      waterMaskImg,
      errorMsg
    };
  },
  render() {
    return (
      <div
        class={{
          'chart-wrapper': true,
          'grafana-check': this.panel.canSetGrafana,
          'is-checked': this.panel.checked,
          'is-collapsed': this.panel.collapsed,
          'hover-style': this.needCheck && this.needHoverStryle,
          'row-chart': this.panel.type === 'row'
        }}
        style={{ 'border-color': this.panel.type === 'tag-chart' ? '#eaebf0' : 'transparent' }}
        onMouseenter={() => (this.showHeaderMoreTool = true)}
        onMouseleave={() => (this.showHeaderMoreTool = false)}
      >
        {this.handlePanel2Chart()}
        {this.loading ? (
          <img
            class='loading-icon'
            src={loadingIcon}
            alt=''
          ></img>
        ) : undefined}
        {!this.readonly && this.panel.canSetGrafana && !this.panel.options?.disable_wrap_check && (
          <span
            class='check-mark'
            onClick={this.handleChartCheck}
          />
        )}
        {!!this.waterMaskImg && (
          <div
            class='wm'
            style={{ backgroundImage: `url('${this.waterMaskImg}')` }}
          ></div>
        )}
        {!!this.errorMsg && (
          <span
            class='is-error'
            v-bk-tooltips={{
              content: <div>{this.errorMsg}</div>,
              extCls: 'chart-wrapper-error-tooltip',
              placement: 'top-start'
            }}
          ></span>
        )}
      </div>
    );
  }
});
