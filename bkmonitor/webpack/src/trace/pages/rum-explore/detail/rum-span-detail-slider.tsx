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

import DetailHeader from './components/detail-header/detail-header';
import DetailSections from './components/detail-sections/detail-sections';
import DetailSkeleton from './components/detail-skeleton/detail-skeleton';
import OriginDataPanel from './components/origin-data-panel/origin-data-panel';
import TimelineFilterBar from './components/trace-context/timeline-filter-bar';
import TraceContextPanel from './components/trace-context/trace-context-panel';
import {
  useDetailFormatter,
  useDetailOverview,
  useDetailSections,
  useOriginData,
  useSpanDetail,
  useTraceContext,
} from './composables';
import { searchTraceInfo } from './services';
import { RumDetailTabEnum } from './typings';
import SliderHeader from '@/components/slider-header/slider-header';
import TemporaryShareNew from '@/components/temporary-share/temporary-share-new';

import type { IRumField, IRumTimeRange, RumModeType } from '../typings';
import type { IRumTraceInfo } from './services';
import type { IRumDetailContext, IRumTimelineSpanVM, RumDetailTabType } from './typings';

import './rum-span-detail-slider.scss';

/** 抽屉宽度，与设计稿一致 */
const SLIDER_WIDTH = 1280;

/**
 * Span 详情抽屉。
 *
 * 只负责壳层（标题栏、Tab、加载与空态）与各区块的编排，
 * 「不同 span 类型展示什么」由 detail/registry 的注册表决定，本组件不含类型分支。
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

    const { detail, related, loading, relatedLoading, traceInfo } = useSpanDetail({
      context: toRef(props, 'context'),
      mode: toRef(props, 'mode'),
      timeRange,
    });

    const originData = computed(() => detail.value?.origin_data || {});
    const { getField, formatField, copyText, resolveCtx } = useDetailFormatter(toRef(props, 'fields'), originData);
    const { headerVM } = useDetailOverview(detail, spanType, formatField, getField);
    const { sectionVMs } = useDetailSections(detail, spanType, related, resolveCtx, relatedLoading, {
      switchTab: tab => {
        activeTab.value = tab;
      },
    });
    const { blocks, eventKeyword } = useOriginData(originData, toRef(props, 'fields'));

    const isXhrOrFetch = computed(() => {
      const spanType = detail.value?.overview.items.find(item => item.field_name === 'display.span_type')?.value;
      return ['Resource(fetch)', 'Resource(xhr)'].includes(spanType as string);
    });

    /** 标题栏展示的 span_id，优先取接口回传值 */
    const spanId = computed(() => detail.value?.span_id || props.context?.record_id || '');

    /** 当前 Span 所属的 View，链路上下文按它查询 */
    const viewId = computed(() => {
      const fromOrigin = originData.value.attributes?.['view.id'];
      const fromOverview = detail.value?.overview?.items?.find(item => item.field_name === 'attributes.view.id')?.value;
      return String(fromOrigin ?? fromOverview ?? '');
    });

    const traceContext = useTraceContext({
      active: computed(() => activeTab.value === RumDetailTabEnum.TRACE_CONTEXT),
      appName: computed(() => props.context?.app_name || ''),
      viewId,
      currentSpanId: spanId,
      formatField,
    });

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

    /** 抽屉关闭后重置交互态：tab、Events 搜索关键字与链路上下文的筛选，避免下次打开残留；嵌套抽屉复用本组件同样生效 */
    watch(
      () => props.isShow,
      show => {
        if (show) return;
        activeTab.value = RumDetailTabEnum.BASIC;
        eventKeyword.value = '';
        traceContext.filterKeyword.value = '';
        traceContext.filterCategory.value = 'all';
      }
    );

    const getTraceUrl = (info: IRumTraceInfo) =>
      location.href.replace(
        location.hash,
        `#/trace/home?app_name=${info.app_name}&trace_id=${info.trace_id}&sceneMode=trace&filterMode=ui`
      );

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

    function renderTitle() {
      return (
        <SliderHeader
          v-slots={{
            title: () => (
              <div class='rum-detail-title'>
                <span class='title-text'>{t('Span 详情')}</span>
                {spanId.value ? (
                  <span class='title-sub'>
                    <span class='sub-divider' />
                    <span class='sub-label'>span_id:</span>
                    <span class='sub-value'>{spanId.value}</span>
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
        { id: RumDetailTabEnum.TRACE_CONTEXT, icon: 'icon-Tracing', label: t('链路上下文') },
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
      return (
        <div class='rum-detail-card'>
          {isXhrOrFetch.value && traceInfo.value ? (
            <Alert
              class='related-trace-alert'
              v-slots={{
                title: () => (
                  <div>
                    <span>{t('已有关联 Trace：')}</span>
                    <span>{originData.value.links?.[0]?.trace_id || '--'}，</span>
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
          <DetailSections sections={sectionVMs.value} />
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

    function renderTraceContext() {
      return (
        <div class='rum-detail-card'>
          <TimelineFilterBar
            category={traceContext.filterCategory.value}
            keyword={traceContext.filterKeyword.value}
            onUpdate:category={value => {
              traceContext.filterCategory.value = value;
            }}
            onUpdate:keyword={value => {
              traceContext.filterKeyword.value = value;
            }}
          />
          <TraceContextPanel
            error={traceContext.error.value}
            items={traceContext.items.value}
            loading={traceContext.loading.value}
            view={traceContext.viewVM.value}
            onExpandFold={traceContext.handleExpandFold}
            onSpanClick={handleTimelineSpanClick}
            onToggleNode={traceContext.handleToggleNode}
            onTraceClick={handleTimelineTraceClick}
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
          {activeTab.value === RumDetailTabEnum.TRACE_CONTEXT ? renderTraceContext() : renderBasicInfo()}
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
        class='rum-span-detail-slider'
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
