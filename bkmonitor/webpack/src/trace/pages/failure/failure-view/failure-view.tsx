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
import { type Ref, defineComponent, inject, onMounted, provide, ref, watch } from 'vue';

import { Exception, Loading } from 'bkui-vue';
import { incidentAlertView } from 'monitor-api/modules/incident';
import { useI18n } from 'vue-i18n';

import DashboardPanel from '../../../plugins/components/flex-dashboard-panel';
import { useIncidentInject } from '../utils';
import MetricsCollapse from './metrics-collapse';

import './failure-view.scss';

export default defineComponent({
  name: 'FailureView',
  props: {
    info: {
      type: Object,
      default: () => ({}),
    },
    alertIdsObject: {
      type: [Object, String],
      default: () => ({}),
    },
    searchValidate: {
      type: Boolean,
      default: true,
    },
  },
  emits: ['refresh'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const bkzIds = inject<Ref<string[]>>('bkzIds');
    const layoutActive = ref<number>(2);
    const incidentId = useIncidentInject();
    // 提供给子组件的键值
    const LAYOUT_ACTIVE_KEY = Symbol();
    // 提供响应式数据
    provide(LAYOUT_ACTIVE_KEY, layoutActive);
    const recommendedMetricPanels = ref([]);
    const loading = ref(false);
    const dataZoomTimeRange = ref({ timeRange: [] });
    provide('dataZoomTimeRange', dataZoomTimeRange);
    /** 指标加载全部 */
    const handleLoadPanels = panel => {
      panel.showMore = false;
      panel.panels = panel.totalPanels;
      // this.$nextTick(this.handleScroll);
    };
    watch(
      () => props.alertIdsObject,
      () => {
        props.searchValidate && getIncidentAlertView();
      },
      { deep: true }
    );
    const getIncidentAlertView = () => {
      loading.value = true;
      const queryString =
        typeof props.alertIdsObject === 'object' ? props.alertIdsObject?.ids || '' : props.alertIdsObject;
      incidentAlertView({
        bk_biz_ids: bkzIds.value,
        id: incidentId.value,
        query_string: queryString,
      })
        .then(res => {
          loading.value = false;
          recommendedMetricPanels.value = (res || []).filter(item => item.alerts?.length > 0);
        })
        .catch(err => {
          loading.value = false;
          console.log(err);
        });
    };
    // onMounted(() => {
    //   getIncidentAlertView();
    // });
    const handleSuccessLoad = () => {
      recommendedMetricPanels.value = [];
      getIncidentAlertView();
      setTimeout(() => emit('refresh'), 2000);
    };
    /** 指标展开收起 */
    const renderDashboardPanel = (item, props) => {
      return (
        <div class='panel-warp'>
          {item.alerts?.length > 0 ? (
            <DashboardPanel
              id={item.name}
              key={item.id}
              column={props.column}
              customHeightFn={column => '200px' || (column === 1 ? '220px' : '256px')}
              isAlarmView={true}
              isSingleChart={false}
              isSplitPanel={false}
              needOverviewBtn={false}
              panels={item.alerts}
              onSuccessLoad={handleSuccessLoad}
            />
          ) : (
            ''
          )}
          {item.showMore ? (
            <span
              class='add-more'
              onClick={handleLoadPanels.bind(this, item)}
            >
              {t('加载更多')}
            </span>
          ) : (
            ''
          )}
        </div>
      );
    };

    const renderMetricsCollapse = (item, index) => {
      const panelLen = recommendedMetricPanels.value.length;
      return (
        <MetricsCollapse
          id={`${item.id}_collapse`}
          key={`${item.id}_collapse`}
          ref={`${item.id}_collapse`}
          class={[panelLen > 1 && index !== panelLen - 1 ? 'mb10' : '']}
          v-slots={{
            default: renderDashboardPanel.bind(this, item),
            title: () => (
              <span class='title-main'>
                {item.name}
                <label class='title-num'>({item.alerts?.length})</label>
              </span>
            ),
          }}
          info={props.info}
          layoutActive={layoutActive.value}
          needLayout={true}
          onLayoutChange={val => (layoutActive.value = val)}
        />
      );
    };
    watch(
      () => bkzIds.value,
      val => {
        val.length > 0 && getIncidentAlertView();
      },
      { immediate: true }
    );
    return {
      t,
      renderMetricsCollapse,
      recommendedMetricPanels,
      loading,
    };
  },
  render() {
    const len = this.recommendedMetricPanels.length;
    return (
      <Loading
        class='failure-view bk-scroll-y'
        loading={this.loading}
      >
        {len > 0 ? (
          this.recommendedMetricPanels.map((item, index) => this.renderMetricsCollapse(item, index))
        ) : (
          <Exception
            class='failure-view-empty'
            description={this.t('暂无告警视图')}
            scene='part'
            type='empty'
          />
        )}
      </Loading>
    );
  },
});
