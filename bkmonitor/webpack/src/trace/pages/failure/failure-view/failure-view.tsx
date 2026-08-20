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
import { type Ref, defineComponent, inject, nextTick, onUnmounted, ref, shallowRef, watch } from 'vue';

import { Loading } from 'bkui-vue';
import { incidentAlertView } from 'monitor-api/modules/incident';
import { useI18n } from 'vue-i18n';

import ExceptionComp from '../../../components/exception';
import LazyDashboardPanel from '../../../plugins/components/lazy-dashboard-panel';
import { filterAlertGroupsByCurrentPrimary, useIncidentInject } from '../utils';
import MetricsCollapse from './metrics-collapse';

import './failure-view.scss';

/** 切换「仅看最新排障告警」时 loading 展示时长 */
const VIEW_NEWEST_ALARM_LOADING_MS = 200;

export default defineComponent({
  name: 'FailureView',
  props: {
    /** 告警检索条件，对象时取 ids，也可直接传 query string */
    alertIdsObject: {
      type: [Object, String],
      default: () => ({}),
    },
    /** 检索条件是否通过校验，为 false 时不发起告警视图请求 */
    searchValidate: {
      type: Boolean,
      default: true,
    },
    /** 是否仅看最新排障记录中新增的告警（本地按 is_current_primary 过滤） */
    isViewNewestAlarm: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['refresh'],
  setup(props, { emit }) {
    const { t } = useI18n();
    /** 业务 ID 列表（由上层 provide） */
    const bkzIds = inject<Ref<string[]>>('bkzIds');
    const incidentId = useIncidentInject();
    /** 图表布局：0 一列，2 三列（与 MetricsCollapse 约定一致） */
    const layoutActive = ref<number>(2);
    /** 接口全量缓存 */
    const rawRecommendedMetricPanels = ref([]);
    /** 按开关过滤后的告警视图面板列表（用于渲染） */
    const recommendedMetricPanels = ref([]);
    /**
     * 缓存「最新告警」过滤结果，避免每次切换 Checkbox 都对上百/上千 alerts 重新遍历。
     * 注意：rawRecommendedMetricPanels 更新时需要清空该缓存。
     */
    const newestFilteredMetricPanels = ref<any[] | null>(null);
    const loading = ref(false);
    /** 错误 / 空状态 */
    const exceptionData = shallowRef({
      isError: false,
      errorMsg: '',
    });

    /** @description 基于缓存全量数据按当前开关写入展示列表 */
    const applyNewestAlarmFilter = () => {
      // 关闭过滤：复用原始引用，减少数组创建
      if (!props.isViewNewestAlarm) {
        recommendedMetricPanels.value = rawRecommendedMetricPanels.value;
        return;
      }

      // 开启过滤：懒加载缓存结果
      if (!newestFilteredMetricPanels.value) {
        newestFilteredMetricPanels.value = filterAlertGroupsByCurrentPrimary(rawRecommendedMetricPanels.value, true);
      }
      recommendedMetricPanels.value = newestFilteredMetricPanels.value;
    };

    /**
     * @description 过滤完成后触发懒加载视口重算，确保图表重新请求接口
     */
    const refreshLazyPanelViewport = () => {
      nextTick(() => {
        const scrollRoot = document.querySelector('.failure-view') as HTMLElement | null;
        if (!scrollRoot) return;
        const originTop = scrollRoot.scrollTop;
        scrollRoot.scrollTop = originTop + 1;
        requestAnimationFrame(() => {
          scrollRoot.scrollTop = originTop;
        });
      });
    };

    /**
     * @description 展开分组下「加载更多」隐藏的面板
     */
    const handleLoadPanels = panel => {
      panel.showMore = false;
      panel.panels = panel.totalPanels;
    };

    /**
     * @description 拉取故障告警视图数据
     */
    const getIncidentAlertView = () => {
      loading.value = true;
      exceptionData.value.isError = false;
      exceptionData.value.errorMsg = '';

      const queryString =
        typeof props.alertIdsObject === 'object' ? props.alertIdsObject?.ids || '' : props.alertIdsObject;
      incidentAlertView(
        {
          bk_biz_ids: bkzIds.value,
          id: incidentId.value,
          query_string: queryString,
        },
        { needMessage: false }
      )
        .then(res => {
          loading.value = false;
          // 缓存仍有告警的分组，再按开关生成本地展示数据
          rawRecommendedMetricPanels.value = (res || []).filter(item => item.alerts?.length > 0);
          // rawRecommendedMetricPanels 更新后清空过滤缓存
          newestFilteredMetricPanels.value = null;
          applyNewestAlarmFilter();
        })
        .catch(err => {
          loading.value = false;
          rawRecommendedMetricPanels.value = [];
          recommendedMetricPanels.value = [];
          newestFilteredMetricPanels.value = null;
          // 异常状态赋值
          exceptionData.value.isError = true;
          exceptionData.value.errorMsg = err.message || '';
        });
    };

    /**
     * @description 单图加载成功后刷新列表，并通知上层刷新相关数据
     */
    const handleSuccessLoad = () => {
      rawRecommendedMetricPanels.value = [];
      recommendedMetricPanels.value = [];
      getIncidentAlertView();
      setTimeout(() => emit('refresh'), 2000);
    };

    /**
     * @description 指标分组下的告警图表面板
     */
    const renderDashboardPanel = (item, slotProps) => {
      return (
        <div class='panel-warp'>
          {item.alerts?.length > 0 && (
            <LazyDashboardPanel
              id={`${item.id}`}
              // 随过滤开关 remount，强制图表重新走懒加载并请求接口
              key={`${item.id}-${props.isViewNewestAlarm}`}
              column={slotProps.column}
              panels={item.alerts}
              onSuccessLoad={handleSuccessLoad}
            />
          )}
          {item.showMore && (
            <span
              class='add-more'
              onClick={() => handleLoadPanels(item)}
            >
              {t('加载更多')}
            </span>
          )}
        </div>
      );
    };

    /**
     * @description 单个指标分组折叠面板
     */
    const renderMetricsCollapse = (item, index) => {
      const panelLen = recommendedMetricPanels.value.length;
      return (
        <MetricsCollapse
          id={`${item.id}_collapse`}
          key={`${item.id}_collapse`}
          ref={`${item.id}_collapse`}
          class={[panelLen > 1 && index !== panelLen - 1 ? 'mb10' : '']}
          v-slots={{
            default: slotProps => renderDashboardPanel(item, slotProps),
            title: () => (
              <span class='title-main'>
                {item.name}
                <label class='title-num'>({item.alerts?.length})</label>
              </span>
            ),
          }}
          layoutActive={layoutActive.value}
          needLayout={true}
          onLayoutChange={val => (layoutActive.value = val)}
        />
      );
    };

    // 检索条件变化且校验通过时重新拉取
    watch(
      () => props.alertIdsObject,
      () => {
        props.searchValidate && getIncidentAlertView();
      },
      { deep: true }
    );

    // 业务 ID 就绪后立即拉取（含首次）
    watch(
      () => bkzIds.value,
      val => {
        val.length > 0 && getIncidentAlertView();
      },
      { immediate: true }
    );

    // 切换「仅看最新排障告警」：展示 loading，本地过滤并 remount 图表
    let newestAlarmSwitchTimer: null | ReturnType<typeof setTimeout> = null;
    watch(
      () => props.isViewNewestAlarm,
      () => {
        loading.value = true;
        applyNewestAlarmFilter();
        // 允许用户连点：只保留最后一次切换对应的延时回调
        if (newestAlarmSwitchTimer) clearTimeout(newestAlarmSwitchTimer);
        newestAlarmSwitchTimer = setTimeout(() => {
          loading.value = false;
          refreshLazyPanelViewport();
        }, VIEW_NEWEST_ALARM_LOADING_MS);
      }
    );

    onUnmounted(() => {
      // 防止组件销毁后延时回调继续操作 DOM/状态
      if (newestAlarmSwitchTimer) clearTimeout(newestAlarmSwitchTimer);
    });

    return {
      t,
      renderMetricsCollapse,
      recommendedMetricPanels,
      loading,
      exceptionData,
    };
  },
  render() {
    const len = this.recommendedMetricPanels.length;
    return (
      <Loading
        class='failure-view-wrapper'
        loading={this.loading}
      >
        <div class='failure-view'>
          {len > 0 ? (
            this.recommendedMetricPanels.map((item, index) => this.renderMetricsCollapse(item, index))
          ) : (
            <ExceptionComp
              errorMsg={this.exceptionData.errorMsg}
              imgHeight={160}
              isError={this.exceptionData.isError}
              title={this.exceptionData.isError ? this.t('查询异常') : this.t('暂无告警视图')}
            />
          )}
        </div>
      </Loading>
    );
  },
});
