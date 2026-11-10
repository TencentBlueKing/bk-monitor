import { type PropType, computed, defineComponent, shallowRef } from 'vue';

import { Button, Exception, Radio } from 'bkui-vue';
import dayjs from 'dayjs';
import { useI18n } from 'vue-i18n';

import { findSpanRowView } from '../utils/duration-stats';
import { type TokenMetric, type TokenRankMode, type TokenSpanStat, buildTokenSpanStats } from '../utils/token-stats';
import { formatCompactToken } from '../utils/transform';

import type { LlmFlowSpan } from '../utils/typings';

import './token-stats-panel.scss';

const METRIC_TABS: { id: TokenMetric; label: string }[] = [
  { id: 'total', label: window.i18n.t('总 Tokens') },
  { id: 'input', label: window.i18n.t('输入 Tokens') },
  { id: 'output', label: window.i18n.t('输出 Tokens') },
  { id: 'cacheRead', label: window.i18n.t('缓存读取') },
  { id: 'cacheWrite', label: window.i18n.t('缓存写入') },
];

function formatPercent(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return '0%';
  return `${Math.round(value)}%`;
}

/** 单条 Trace 的 Token 统计分析：按 usage 指标列表 Top / Bottom */
export default defineComponent({
  name: 'LlmTokenStatsPanel',
  props: {
    flow: {
      type: Array as PropType<LlmFlowSpan[]>,
      default: () => [],
    },
    flowLoaded: {
      type: Boolean,
      default: false,
    },
    flowLoading: {
      type: Boolean,
      default: false,
    },
    /** 面板最大高度（由触发列到视口底部动态计算），超出内部滚动 */
    maxHeight: {
      type: Number,
      default: undefined,
    },
  },
  emits: {
    locate: (_spanId: string) => true,
    'view-detail': (_spanId: string) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const metric = shallowRef<TokenMetric>('total');
    const rankMode = shallowRef<TokenRankMode>('top');

    const spanItems = computed(() => buildTokenSpanStats(props.flow, metric.value, rankMode.value));
    const panelStyle = computed(() => (props.maxHeight ? { maxHeight: `${props.maxHeight}px` } : {}));
    /** 当前 Tab 是否存在数据，用于决定是否展示工具栏 */
    const hasData = computed(() => props.flowLoaded && spanItems.value.length > 0);

    const handleViewDetail = (spanId: string) => {
      if (findSpanRowView(props.flow, spanId)) emit('view-detail', spanId);
    };

    const renderSpanItem = (item: TokenSpanStat) => (
      <div
        key={item.spanId}
        class='llm-token-stats-item'
      >
        <div class='llm-token-stats-item-main'>
          <div class='llm-token-stats-item-meta'>
            <span class='llm-token-stats-item-names'>
              <span class='is-time'>{dayjs(item.startTime / 1000).format('HH:mm:ss')}</span>
              <span
                class='is-name'
                v-overflow-tips={{ content: item.name, placement: 'top' }}
              >
                {item.name}
              </span>
            </span>
            <span class='llm-token-stats-item-values'>
              <span class='is-tokens'>{formatCompactToken(item.tokens)}</span>
              <span class='is-percent'>{formatPercent(item.percent)}</span>
            </span>
          </div>
          <div class='llm-token-stats-bar'>
            <span
              style={{ width: `${Math.min(100, Math.max(0, item.percent))}%` }}
              class='llm-token-stats-bar-fill'
            />
          </div>
        </div>
        <div class='llm-token-stats-item-actions'>
          <Button
            size='small'
            text
            theme='primary'
            onClick={() => emit('locate', item.spanId)}
          >
            <i
              class='icon-monitor icon-dingwei1'
              style='font-size: 12px'
            />
            {t('定位')}
          </Button>
          <Button
            size='small'
            text
            theme='primary'
            onClick={() => handleViewDetail(item.spanId)}
          >
            <i
              class='icon-monitor icon-chakan'
              style='font-size: 14px'
            />
            {t('详情')}
          </Button>
        </div>
      </div>
    );

    const renderBody = () => {
      if (props.flowLoading) {
        return <div class='llm-token-stats-placeholder'>{t('加载中...')}</div>;
      }
      if (!props.flowLoaded || !spanItems.value.length) {
        return (
          <Exception
            class='llm-token-stats-empty'
            scene='part'
            title={t('暂无数据')}
            type='empty'
          />
        );
      }
      return <div class='llm-token-stats-list'>{spanItems.value.map(renderSpanItem)}</div>;
    };

    return () => (
      <div
        class='llm-token-stats-panel'
        style={panelStyle.value}
      >
        <div class='llm-token-stats-header'>
          <div class='llm-token-stats-title'>{t('Token 统计分析')}</div>
          <div class='llm-token-stats-tabs'>
            {METRIC_TABS.map(tab => (
              <button
                key={tab.id}
                class={['llm-token-stats-tab', { 'is-active': metric.value === tab.id }]}
                type='button'
                onClick={() => {
                  metric.value = tab.id;
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
        <div class='llm-token-stats-content'>
          {hasData.value ? (
            <div class='llm-token-stats-toolbar'>
              <Radio.Group
                class='llm-token-stats-rank'
                modelValue={rankMode.value}
                type='capsule'
                onChange={(value: TokenRankMode) => {
                  rankMode.value = value;
                }}
              >
                <Radio.Button label='top'>Top 10</Radio.Button>
                <Radio.Button label='bottom'>Bottom 10</Radio.Button>
              </Radio.Group>
            </div>
          ) : null}
          {renderBody()}
        </div>
      </div>
    );
  },
});
