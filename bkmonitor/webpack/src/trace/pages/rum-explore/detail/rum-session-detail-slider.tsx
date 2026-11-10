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
import { computed, defineComponent, shallowRef, toRef, watch } from 'vue';
import type { PropType } from 'vue';

import { Exception, Message, Sideslider } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { RumModeEnum } from '../constants';
import DetailHeader from './components/detail-header/detail-header';
import DetailSkeleton from './components/detail-skeleton/detail-skeleton';
import OriginDataPanel from './components/origin-data-panel/origin-data-panel';
import TimelineFilterBar from './components/trace-context/timeline-filter-bar';
import TimelineViewList from './components/trace-context/timeline-view-list';
import { useDetailFormatter, useDetailOverview, useOriginData, useSpanDetail, useTraceContext } from './composables';
import { RumTimelineFilterCategoryEnum } from './constants';
import RumSpanDetailSlider from './rum-span-detail-slider';
import { searchTraceInfo } from './services';
import SliderHeader from '@/components/slider-header/slider-header';
import TemporaryShareNew from '@/components/temporary-share/temporary-share-new';

import type { IRumField, IRumTimeRange } from '../typings';
import type { IRumTraceInfo } from './services';
import type { IRumDetailContext, IRumTimelineSpanVM, IRumTimelineViewVM } from './typings';

import './rum-span-detail-slider.scss';

/** 抽屉宽度，与 Span 详情保持一致 */
const SLIDER_WIDTH = 1280;

/** 会话详情的 Tab */
const SessionDetailTabEnum = {
  /** 原始属性 */
  ATTRIBUTES: 'attributes',
  /** 时间轴 */
  TIMELINE: 'timeline',
} as const;

type SessionDetailTabType = (typeof SessionDetailTabEnum)[keyof typeof SessionDetailTabEnum];

/**
 * Session 详情抽屉。
 *
 * 在 Span 详情的基础上按会话层级调整：
 * - Tab 为「Attributes / 时间轴」，不展示关联 Trace 提示条（会话不挂 Trace）；
 * - Attributes 展示会话概览与原始数据，时间轴按 View 分卡片展示会话内全部 View；
 * - 时间轴里的 Span / View 仍打开 Span 详情抽屉，叠在本抽屉之上。
 */
export default defineComponent({
  name: 'RumSessionDetailSlider',
  props: {
    isShow: {
      type: Boolean,
      default: false,
    },
    /** 详情上下文，关闭时传 null */
    context: {
      type: Object as PropType<IRumDetailContext | null>,
      default: null,
    },
    /** 视图配置里的全量字段，用于取字段别名、单位与枚举 */
    fields: {
      type: Array as PropType<IRumField[]>,
      default: () => [],
    },
  },
  emits: {
    'update:isShow': (_value: boolean) => true,
    /** 详情内点击「添加为检索条件」，回传给列表页 */
    conditionAdd: (_key: string, _value: string) => true,
    previous: () => true,
    next: () => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    /** 列表侧切换上一个 / 下一个时保留当前 tab */
    const activeTab = shallowRef<SessionDetailTabType>(SessionDetailTabEnum.ATTRIBUTES);
    const isFullscreen = shallowRef(false);
    /** 标题栏展示的会话 ID */
    const sessionId = computed(() => props.context?.record_id || '');

    /** 会话不注册关联数据，时间范围仅取上下文起止时间，供取数接口透传 */
    const timeRange = computed<IRumTimeRange>(() => ({
      start_time: props.context?.start_time ?? 0,
      end_time: props.context?.end_time ?? 0,
    }));

    const { detail, loading } = useSpanDetail({
      context: toRef(props, 'context'),
      mode: computed(() => RumModeEnum.SESSION),
      timeRange,
    });

    const originData = computed(() => detail.value?.origin_data || {});
    const { getField, formatField, copyText } = useDetailFormatter(toRef(props, 'fields'), originData);
    const { headerVM } = useDetailOverview(detail, 'session', formatField, getField);
    const { blocks, eventKeyword } = useOriginData(originData, toRef(props, 'fields'));
    /** 会话时间轴：与链路上下文共用同一套时间线产出，只是按 session_id 取数、且没有当前 Span */
    const sessionTimeline = useTraceContext({
      active: computed(() => activeTab.value === SessionDetailTabEnum.TIMELINE),
      appName: computed(() => props.context?.app_name || ''),
      dimension: sessionId,
      scope: 'session',
      formatField,
    });

    /** 时间轴里打开的其他 Span / View，复用 Span 详情抽屉叠在本抽屉之上 */
    const childContext = shallowRef<IRumDetailContext | null>(null);
    const childShow = shallowRef(false);

    watch(
      () => props.context,
      () => {
        childShow.value = false;
        childContext.value = null;
      }
    );

    /** 抽屉关闭后重置交互态，避免下次打开残留 */
    watch(
      () => props.isShow,
      show => {
        if (show) return;
        activeTab.value = SessionDetailTabEnum.ATTRIBUTES;
        eventKeyword.value = '';
        sessionTimeline.filterKeyword.value = '';
        sessionTimeline.filterCategory.value = RumTimelineFilterCategoryEnum.ALL;
      }
    );

    const getTraceUrl = (info: IRumTraceInfo) =>
      location.href.replace(
        location.hash,
        `#/trace/home?app_name=${info.app_name}&trace_id=${info.trace_id}&sceneMode=trace&filterMode=ui`
      );

    /**
     * 时间轴行内的「关联 Trace」：点击时才检索 Trace 所属应用。
     * 先同步打开空白页再回填地址，避免异步检索后 window.open 被浏览器拦截。
     */
    const handleTimelineTraceClick = async (traceId: string) => {
      const win = window.open('', '_blank');
      const info = await searchTraceInfo(traceId, originData.value.bk_biz_id ?? window.cc_biz_id);
      if (!info) {
        win?.close();
        Message({ theme: 'warning', message: t('未找到关联 Trace') });
        return;
      }
      if (win) {
        win.location.href = getTraceUrl(info);
      }
    };

    /** 打开 Span / View 明细：具体层级由 record_id 与 span_type 决定，查询模式固定为 span */
    function openChildSlider(recordId: string, spanType: string) {
      if (!props.context) return;
      childContext.value = { ...props.context, record_id: recordId, span_type: spanType };
      childShow.value = true;
    }

    const handleTimelineSpanClick = (span: IRumTimelineSpanVM) => {
      openChildSlider(span.spanId, span.spanType);
    };

    const handleTimelineViewClick = (view: IRumTimelineViewVM) => {
      openChildSlider(view.spanId, 'view');
    };

    function renderTitle() {
      return (
        <SliderHeader
          v-slots={{
            title: () => (
              <div class='rum-detail-title'>
                <span class='title-text'>{t('Session 详情')}</span>
                {sessionId.value ? (
                  <span class='title-sub'>
                    <span class='sub-divider' />
                    <span class='sub-label'>session_id:</span>
                    <span class='sub-value'>{sessionId.value}</span>
                    <TemporaryShareNew
                      icon='icon-copy-link'
                      type='rum'
                    />
                  </span>
                ) : null}
              </div>
            ),
          }}
          buttons={['fullscreen', 'previous', 'next']}
          isFullscreen={isFullscreen.value}
          onFullscreen={fullscreen => {
            isFullscreen.value = fullscreen;
          }}
          onNext={() => {
            emit('next');
          }}
          onPrevious={() => {
            emit('previous');
          }}
        />
      );
    }

    function renderTabs() {
      const tabs = [
        { id: SessionDetailTabEnum.ATTRIBUTES, icon: 'icon-mc-list', label: t('基础信息') },
        { id: SessionDetailTabEnum.TIMELINE, icon: 'icon-Tracing', label: t('时间轴') },
      ];
      return (
        <div class='rum-detail-tabs'>
          {tabs.map(tab => (
            <div
              key={tab.id}
              class={{ 'detail-tab': true, 'is-active': activeTab.value === tab.id }}
              onClick={() => {
                activeTab.value = tab.id;
              }}
            >
              <i class={`icon-monitor ${tab.icon}`} />
              {tab.label}
            </div>
          ))}
        </div>
      );
    }

    function renderAttributes() {
      return (
        <div class='rum-detail-card'>
          <OriginDataPanel
            blocks={blocks.value}
            eventKeyword={eventKeyword.value}
            onConditionAdd={(key, value) => emit('conditionAdd', key, value)}
            onCopy={copyText}
            onUpdate:eventKeyword={value => {
              eventKeyword.value = value;
            }}
          />
        </div>
      );
    }

    function renderTimeline() {
      return (
        <div class='rum-detail-card'>
          <TimelineFilterBar
            category={sessionTimeline.filterCategory.value}
            collapseMiddle={sessionTimeline.collapseMiddleView.value}
            durationText={sessionTimeline.durationText.value}
            keyword={sessionTimeline.filterKeyword.value}
            scope='session'
            sort={sessionTimeline.sortOrder.value}
            onUpdate:category={value => {
              sessionTimeline.filterCategory.value = value;
            }}
            onUpdate:collapseMiddle={value => {
              sessionTimeline.collapseMiddleView.value = value;
            }}
            onUpdate:keyword={value => {
              sessionTimeline.filterKeyword.value = value;
            }}
            onUpdate:sort={value => {
              sessionTimeline.sortOrder.value = value;
            }}
          />
          <TimelineViewList
            beginText={sessionTimeline.beginDateText.value}
            cardItems={sessionTimeline.cardItems.value}
            endText={sessionTimeline.endDurationText.value}
            error={sessionTimeline.error.value}
            hasFilter={sessionTimeline.hasFilter.value}
            loading={sessionTimeline.loading.value}
            scope='session'
            sort={sessionTimeline.sortOrder.value}
            spanType='session'
            onExpandFold={sessionTimeline.handleExpandFold}
            onExpandHidden={sessionTimeline.handleExpandHiddenViews}
            onSpanClick={handleTimelineSpanClick}
            onToggleNode={sessionTimeline.handleToggleNode}
            onTraceClick={handleTimelineTraceClick}
            onViewClick={handleTimelineViewClick}
          />
        </div>
      );
    }

    function renderContent() {
      if (loading.value) {
        return <DetailSkeleton />;
      }
      if (!detail.value) {
        return (
          <Exception
            class='detail-empty'
            description={t('查询详情失败，请稍后重试')}
            scene='part'
            type='empty'
          />
        );
      }
      return (
        <>
          <DetailHeader
            data={headerVM.value}
            onItemClick={(key, value) => emit('conditionAdd', key, value)}
          />
          {renderTabs()}
          {activeTab.value === SessionDetailTabEnum.TIMELINE ? renderTimeline() : renderAttributes()}
        </>
      );
    }

    /** 时间轴打开的 Span 详情：查询模式固定为 span，Span / View 记录都能按 span_id 定位 */
    function renderChildSlider() {
      if (!childContext.value) return null;
      return (
        <RumSpanDetailSlider
          context={childContext.value}
          fields={props.fields}
          isShow={childShow.value}
          mode='span'
          nested
          onConditionAdd={(key: string, value: string) => emit('conditionAdd', key, value)}
          onSpanOpen={(context: IRumDetailContext) => {
            childContext.value = context;
          }}
          onUpdate:isShow={(value: boolean) => {
            childShow.value = value;
            if (!value) childContext.value = null;
          }}
        />
      );
    }

    return () => (
      <Sideslider
        width={isFullscreen.value ? '100%' : SLIDER_WIDTH}
        class='rum-span-detail-slider rum-session-detail-slider'
        v-slots={{
          header: renderTitle,
          default: () => (
            <div class='rum-detail-body'>
              {renderContent()}
              {renderChildSlider()}
            </div>
          ),
        }}
        isShow={props.isShow}
        renderDirective='if'
        transfer={true}
        onUpdate:isShow={value => emit('update:isShow', value)}
      />
    );
  },
});
