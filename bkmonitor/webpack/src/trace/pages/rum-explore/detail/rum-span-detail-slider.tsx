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
import { computed, defineComponent, shallowRef, toRef } from 'vue';
import type { PropType } from 'vue';

import { Alert, Button, Exception, Sideslider } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import DetailHeader from './components/detail-header/detail-header';
import DetailSections from './components/detail-sections/detail-sections';
import DetailSkeleton from './components/detail-skeleton/detail-skeleton';
import OriginDataPanel from './components/origin-data-panel/origin-data-panel';
import { useDetailFormatter, useDetailOverview, useDetailSections, useOriginData, useSpanDetail } from './composables';
import { RumDetailTabEnum } from './typings';
import SliderHeader from '@/components/slider-header/slider-header';
import TemporaryShareNew from '@/components/temporary-share/temporary-share-new';

import type { IRumField, IRumTimeRange, RumModeType } from '../typings';
import type { IRumDetailContext } from './typings';

import './rum-span-detail-slider.scss';

/** 抽屉宽度，与设计稿一致 */
const SLIDER_WIDTH = 1280;

/**
 * Span 详情抽屉。
 *
 * 只负责壳层（标题栏、Tab、加载与空态）与各区块的编排，
 * 「不同 span 类型展示什么」由 detail/registry 的两张注册表决定，本组件不含类型分支。
 */
export default defineComponent({
  name: 'RumSpanDetailSlider',
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
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const activeTab = shallowRef<string>(RumDetailTabEnum.BASIC);
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
    const { formatField, copyText, resolveCtx } = useDetailFormatter(toRef(props, 'fields'), originData);
    const { headerVM } = useDetailOverview(detail, spanType, formatField);
    const { sectionVMs } = useDetailSections(detail, spanType, related, resolveCtx, relatedLoading);
    const { blocks, eventKeyword } = useOriginData(originData);

    const isXhrOrFetch = computed(() => {
      const spanType = detail.value?.overview.items.find(item => item.field_name === 'display.span_type')?.value;
      return ['Resource(fetch)', 'Resource(xhr)'].includes(spanType as string);
    });

    /** 标题栏展示的 span_id，优先取接口回传值 */
    const spanId = computed(() => detail.value?.span_id || props.context?.record_id || '');

    const handleJumpTrace = () => {
      if (traceInfo.value) {
        window.open(
          location.href.replace(
            location.hash,
            `#/trace/home?app_name=${traceInfo.value.app_name}&trace_id=${traceInfo.value.trace_id}&sceneMode=trace&filterMode=ui`
          )
        );
      }
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
      return (
        <div class='rum-detail-tabs'>
          <div
            class={{ 'detail-tab': true, 'is-active': activeTab.value === RumDetailTabEnum.BASIC }}
            onClick={() => {
              activeTab.value = RumDetailTabEnum.BASIC;
            }}
          >
            <i class='icon-monitor icon-mc-list' />
            {t('基础信息')}
          </div>
          {/* 链路上下文本期未实现，保留入口但置为禁用态 */}
          <div
            class='detail-tab is-disabled'
            v-bk-tooltips={{ content: t('敬请期待') }}
          >
            <i class='icon-monitor icon-Tracing' />
            {t('链路上下文')}
          </div>
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
        </>
      );
    }

    return () => (
      <Sideslider
        width={isFullscreen.value ? '100%' : SLIDER_WIDTH}
        class='rum-span-detail-slider'
        v-slots={{ header: renderTitle, default: () => <div class='rum-detail-body'>{renderContent()}</div> }}
        isShow={props.isShow}
        renderDirective='if'
        transfer={true}
        onUpdate:isShow={value => emit('update:isShow', value)}
      />
    );
  },
});
