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
import { computed, defineComponent, getCurrentInstance, shallowRef, toRef, watch } from 'vue';
import type { Component, PropType } from 'vue';

import { Alert, Button, Exception, Message, Sideslider } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { RUM_RECORD_ID_FIELD_MAP, RumModeEnum } from '../constants';
import DetailHeader from './components/detail-header/detail-header';
import DetailSections from './components/detail-sections/detail-sections';
import DetailSkeleton from './components/detail-skeleton/detail-skeleton';
import OriginDataPanel from './components/origin-data-panel/origin-data-panel';
import TimelineFilterBar from './components/trace-context/timeline-filter-bar';
import TimelineViewList from './components/trace-context/timeline-view-list';
import {
  useDetailFormatter,
  useDetailOverview,
  useDetailSections,
  useOriginData,
  useSpanDetail,
  useTraceContext,
} from './composables';
import { RumDetailTabEnum, RumTimelineFilterCategoryEnum } from './constants';
import { searchTraceInfo } from './services';
import SliderHeader from '@/components/slider-header/slider-header';
import TemporaryShareNew from '@/components/temporary-share/temporary-share-new';

import type { IRumField, IRumTimeRange, RumModeType } from '../typings';
import type { IRumTraceInfo } from './services';
import type { IRumDetailContext, IRumTimelineSpanVM, IRumTimelineViewVM, RumDetailTabType } from './typings';

import './rum-span-detail-slider.scss';

/** 抽屉宽度，与设计稿一致 */
const SLIDER_WIDTH = 1280;

/**
 * 详情抽屉（Span / View / Session 共用同一个 Sideslider 入口）。
 *
 * 只负责壳层（标题栏、Tab、加载与空态）与各区块的编排，
 * 「不同 span 类型展示什么」由 detail/registry 的注册表决定；
 * Session 层级无关联数据与关联 Trace，第二个 Tab 换成会话时间轴（按 session_id 取全部 View 卡片），
 * 因此详情类型变化时只切换内容，抽屉本身不重建，避免上一条 / 下一条跨类型切换时闪烁。
 *
 * 链路上下文里点击其他 Span 时，在上层叠一个同组件的嵌套抽屉（最多一层），本抽屉内容保持不变。
 */
export default defineComponent({
  name: 'RumSpanDetailSlider',
  props: {
    isShow: {
      type: Boolean,
      default: false,
    },
    /** 是否为链路上下文打开的嵌套抽屉：不提供上一个 / 下一个与分享，也不再继续嵌套 */
    nested: {
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
    /** 当前视角的可检索字段名：详情头部据此判断字段能否点击添加为检索条件 */
    retrievalFieldNames: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    mode: {
      type: String as PropType<RumModeType>,
      required: true,
    },
  },
  emits: {
    'update:isShow': (_value: boolean) => true,
    /** 详情内点击「添加为检索条件」，回传给列表页 */
    conditionAdd: (_key: string, _value: string) => true,
    previous: () => true,
    next: () => true,
    /** 嵌套抽屉里再点击其他 Span 时，请求上层替换嵌套抽屉的内容 */
    spanOpen: (_context: IRumDetailContext) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    /** 列表侧切换上一个 / 下一个时保留当前 tab */
    const activeTab = shallowRef<RumDetailTabType>(RumDetailTabEnum.BASIC);
    const spanType = computed(() => props.context?.span_type || '');
    const isFullscreen = shallowRef(false);
    /** Error 影响面统计沿用页面所选时间范围，详情上下文里已带上 */
    const timeRange = computed<IRumTimeRange>(() => ({
      start_time: props.context?.start_time ?? 0,
      end_time: props.context?.end_time ?? 0,
    }));

    /** 详情视角：嵌套抽屉展示的是链路上下文里的单个 Span（record_id 为 span_id），固定按 Span 语义查询与渲染 */
    const detailMode = computed<RumModeType>(() => (props.nested ? RumModeEnum.SPAN : props.mode));
    /** 是否为会话层级详情：会话的第二个 Tab 是时间轴，基础信息不渲染 span 区块 */
    const isSession = computed(() => detailMode.value === RumModeEnum.SESSION);
    /** 会话时间轴的取数维度 */
    const sessionId = computed(() => props.context?.record_id || '');

    const { detail, related, loading, relatedLoading, traceInfo } = useSpanDetail({
      context: toRef(props, 'context'),
      mode: detailMode,
      timeRange,
    });

    const originData = computed(() => detail.value?.origin_data || {});
    const { getField, formatField, copyText, resolveCtx } = useDetailFormatter(toRef(props, 'fields'), originData);
    const { headerVM } = useDetailOverview(
      detail,
      spanType,
      formatField,
      getField,
      toRef(props, 'retrievalFieldNames')
    );
    const { sectionVMs } = useDetailSections(detail, spanType, related, resolveCtx, relatedLoading, {
      /** 跳到链路上下文并套用来源卡片对应的快捷筛选类别，清空关键字避免与类别叠加后筛空 */
      switchTraceContext: category => {
        activeTab.value = RumDetailTabEnum.TRACE_CONTEXT;
        traceContext.filterCategory.value = category;
        traceContext.filterKeyword.value = '';
      },
    });
    const { blocks, eventKeyword } = useOriginData(originData, toRef(props, 'fields'));

    const isXhrOrFetch = computed(() => {
      const spanType = detail.value?.overview.items.find(item => item.field_name === 'display.span_type')?.value;
      return ['Resource(fetch)', 'Resource(xhr)'].includes(spanType as string);
    });

    /** 标题栏展示的记录 ID：优先取上层传入的实际 record_id，接口回传值兜底 */
    const recordId = computed(() => props.context?.record_id || detail.value?.span_id || '');
    /** 链路上下文定位用的 Span ID：以接口回传值为准，记录 ID 兜底（View 视角下两者不同） */
    const spanId = computed(() => detail.value?.span_id || props.context?.record_id || '');

    /** 标题文案随检索视角变化 */
    const detailTitle = computed(() => {
      const titleMap = {
        [RumModeEnum.SESSION]: t('Session 详情'),
        [RumModeEnum.VIEW]: t('View 详情'),
        [RumModeEnum.SPAN]: t('Span 详情'),
      };
      return titleMap[detailMode.value] || t('Span 详情');
    });

    /** 标题栏的 ID 标签：按实际渲染视角（嵌套抽屉固定 Span）展示对应的字段名，会话沿用简短的 session_id */
    const recordIdLabel = computed(() =>
      detailMode.value === RumModeEnum.SESSION ? 'session_id' : RUM_RECORD_ID_FIELD_MAP[detailMode.value] || 'span_id'
    );

    /** 当前 Span 所属的 View，链路上下文按它查询 */
    const viewId = computed(() => {
      const fromOrigin = originData.value.attributes?.['view.id'];
      const fromOverview = detail.value?.overview?.items?.find(item => item.field_name === 'attributes.view.id')?.value;
      return String(fromOrigin ?? fromOverview ?? '');
    });

    /** 会话时间轴：按 session_id 取整个会话的 View 卡片（会话层级没有当前 Span） */
    const sessionTimeline = useTraceContext({
      active: computed(() => isSession.value && activeTab.value === RumDetailTabEnum.TRACE_CONTEXT),
      appName: computed(() => props.context?.app_name || ''),
      dimension: sessionId,
      scope: 'session',
      formatField,
    });

    /** 链路上下文：按当前 Span 所属 View 取链路，仅非会话层级使用 */
    const traceContext = useTraceContext({
      active: computed(() => !isSession.value && activeTab.value === RumDetailTabEnum.TRACE_CONTEXT),
      appName: computed(() => props.context?.app_name || ''),
      dimension: viewId,
      currentSpanId: spanId,
      scope: 'view',
      formatField,
    });

    /** 第二个 Tab 的数据源：会话层级用会话时间轴，其余用链路上下文 */
    const timeline = computed(() => (isSession.value ? sessionTimeline : traceContext));

    /** 链路上下文打开的嵌套抽屉，复用本组件定义递归渲染 */
    const ChildSlider = getCurrentInstance()?.type as Component;
    const childContext = shallowRef<IRumDetailContext | null>(null);
    const childShow = shallowRef(false);

    watch(
      () => props.context,
      () => {
        childShow.value = false;
        childContext.value = null;
        /** 嵌套抽屉被替换成另一个 Span 时，与首次打开一致展示基础信息 */
        if (props.nested) activeTab.value = RumDetailTabEnum.BASIC;
      }
    );

    /** 抽屉关闭后重置交互态：tab、Events 搜索关键字与时间轴的筛选，避免下次打开残留；嵌套抽屉复用本组件同样生效 */
    watch(
      () => props.isShow,
      show => {
        if (show) return;
        activeTab.value = RumDetailTabEnum.BASIC;
        eventKeyword.value = '';
        traceContext.filterKeyword.value = '';
        traceContext.filterCategory.value = RumTimelineFilterCategoryEnum.ALL;
        sessionTimeline.filterKeyword.value = '';
        sessionTimeline.filterCategory.value = RumTimelineFilterCategoryEnum.ALL;
      }
    );

    const getTraceUrl = (info: IRumTraceInfo) =>
      location.href.replace(
        location.hash,
        `#/trace/home?app_name=${info.app_name}&trace_id=${info.trace_id}&sceneMode=trace&filterMode=ui`
      );

    const handleCopyTraceId = () => {
      copyText(originData.value.links?.[0]?.trace_id);
    };

    const handleJumpTrace = () => {
      if (traceInfo.value) {
        window.open(getTraceUrl(traceInfo.value));
      }
    };

    /**
     * 链路上下文行内的「关联 Trace」：点击时才检索 Trace 所属应用。
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

    const handleTimelineSpanClick = (span: IRumTimelineSpanVM) => {
      if (!props.context) return;
      const context: IRumDetailContext = { ...props.context, record_id: span.spanId, span_type: span.spanType };
      if (props.nested) {
        emit('spanOpen', context);
        return;
      }
      childContext.value = context;
      childShow.value = true;
    };

    /** 链路上下文头部点击「View 详情」，与 Span 行点击一致打开嵌套抽屉 */
    const handleTimelineViewClick = (view: IRumTimelineViewVM) => {
      if (!props.context) return;
      const context: IRumDetailContext = { ...props.context, record_id: view.spanId, span_type: 'view' };
      if (props.nested) {
        emit('spanOpen', context);
        return;
      }
      childContext.value = context;
      childShow.value = true;
    };

    function renderTitle() {
      return (
        <SliderHeader
          v-slots={{
            title: () => (
              <div class='rum-detail-title'>
                <span class='title-text'>{detailTitle.value}</span>
                {recordId.value ? (
                  <span class='title-sub'>
                    <span class='sub-divider' />
                    <span class='sub-label'>{recordIdLabel.value}:</span>
                    <span class='sub-value'>{recordId.value}</span>
                    {/* 分享链接只还原列表侧的详情上下文，嵌套抽屉不提供 */}
                    {props.nested ? null : (
                      <TemporaryShareNew
                        icon='icon-copy-link'
                        type='rum'
                      />
                    )}
                  </span>
                ) : null}
              </div>
            ),
          }}
          buttons={props.nested ? ['fullscreen'] : ['fullscreen', 'previous', 'next']}
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
        { id: RumDetailTabEnum.BASIC, icon: 'icon-mc-list', label: t('基础信息') },
        {
          id: RumDetailTabEnum.TRACE_CONTEXT,
          icon: 'icon-Tracing',
          label: isSession.value ? t('时间轴') : t('链路上下文'),
        },
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

    function renderBasicInfo() {
      /** 会话层级只展示原始数据：无关联 Trace 提示，也不渲染 span 区块 */
      return (
        <div class='rum-detail-card'>
          {!isSession.value && isXhrOrFetch.value && traceInfo.value ? (
            <Alert
              class='related-trace-alert'
              v-slots={{
                title: () => (
                  <div class='related-trace-alert-content'>
                    <span>{t('已有关联 Trace：')}</span>
                    <span>{originData.value.links?.[0]?.trace_id || '--'}</span>
                    <i
                      class='icon-monitor icon-mc-copy copy-icon'
                      v-bk-tooltips={{ content: t('复制') }}
                      onClick={handleCopyTraceId}
                    />
                    <Button
                      class='jump-btn'
                      theme='primary'
                      text
                      onClick={handleJumpTrace}
                    >
                      {t('查看 Trace 详情')}
                      <i class='icon-monitor icon-fenxiang' />
                    </Button>
                  </div>
                ),
              }}
              theme='info'
            />
          ) : null}
          {isSession.value ? null : <DetailSections sections={sectionVMs.value} />}
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

    /** 第二个 Tab：会话层级渲染会话事件时间轴，其余渲染链路上下文，两者共用同一套筛选与卡片组件 */
    function renderTimeline() {
      const ctx = timeline.value;
      /** 会话时间轴按会话取数，链路上下文按 View 取数 */
      const scope = isSession.value ? 'session' : 'view';
      return (
        <div class='rum-detail-card'>
          <TimelineFilterBar
            category={ctx.filterCategory.value}
            collapseMiddle={ctx.collapseMiddleView.value}
            durationText={ctx.durationText.value}
            keyword={ctx.filterKeyword.value}
            scope={scope}
            sort={ctx.sortOrder.value}
            onUpdate:category={value => {
              ctx.filterCategory.value = value;
            }}
            onUpdate:collapseMiddle={value => {
              ctx.collapseMiddleView.value = value;
            }}
            onUpdate:keyword={value => {
              ctx.filterKeyword.value = value;
            }}
            onUpdate:sort={value => {
              ctx.sortOrder.value = value;
            }}
          />
          <TimelineViewList
            beginText={ctx.beginDateText.value}
            cardItems={ctx.cardItems.value}
            endText={ctx.endDurationText.value}
            error={ctx.error.value}
            hasFilter={ctx.hasFilter.value}
            loading={ctx.loading.value}
            scope={scope}
            sort={ctx.sortOrder.value}
            spanType={isSession.value ? RumModeEnum.SESSION : spanType.value}
            onExpandFold={ctx.handleExpandFold}
            onExpandHidden={ctx.handleExpandHiddenViews}
            onSpanClick={handleTimelineSpanClick}
            onToggleNode={ctx.handleToggleNode}
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
          {activeTab.value === RumDetailTabEnum.TRACE_CONTEXT ? renderTimeline() : renderBasicInfo()}
        </>
      );
    }

    /** 链路上下文打开的嵌套抽屉，嵌套抽屉自身不再渲染下一层 */
    function renderChildSlider() {
      if (props.nested || !ChildSlider) return null;
      return (
        <ChildSlider
          context={childContext.value}
          fields={props.fields}
          isShow={childShow.value}
          mode={props.mode}
          retrievalFieldNames={props.retrievalFieldNames}
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
        class={isSession.value ? 'rum-span-detail-slider rum-session-detail-slider' : 'rum-span-detail-slider'}
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
