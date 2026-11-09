import { type PropType, computed, defineComponent, shallowRef } from 'vue';

import { type TableSort, PrimaryTable } from '@blueking/tdesign-ui';
import { Button, Exception, Radio, Switcher } from 'bkui-vue';
import dayjs from 'dayjs';
import { useI18n } from 'vue-i18n';

import { formatDuration } from '../../../../../components/trace-view/utils/date';
import {
  type DurationRankMode,
  type DurationSpanStat,
  buildDurationGroupStats,
  buildDurationSpanStats,
  findSpanRowView,
} from '../utils/duration-stats';

import type { LlmFlowSpan, LlmSpanKind } from '../utils/typings';

import './duration-stats-panel.scss';

const KIND_TABS: { id: LlmSpanKind; label: string }[] = [
  { id: 'LLM', label: window.i18n.t('模型') },
  { id: 'TOOL', label: window.i18n.t('工具') },
  { id: 'AGENT', label: 'Agent' },
];

/** 面板头部（标题 + Tabs）、内容内边距与工具栏的固定占位高度，用于换算表格可滚动区域 */
const PANEL_CHROME_HEIGHT = 160;
/** 未取得动态高度时表格的兜底最大高度 */
const DEFAULT_TABLE_MAX_HEIGHT = 360;

function formatPercent(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return '0%';
  return `${Math.round(value)}%`;
}

/** 单条 Trace 的耗时统计分析：按 Span 类型列表 / 聚合 */
export default defineComponent({
  name: 'LlmDurationStatsPanel',
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
    const kind = shallowRef<LlmSpanKind>('LLM');
    const aggregated = shallowRef(false);
    const rankMode = shallowRef<DurationRankMode>('top');
    /** 聚合表格排序信息（受控），空数组表示未排序 */
    const groupSort = shallowRef<TableSort>([]);

    const spanItems = computed(() => buildDurationSpanStats(props.flow, kind.value, rankMode.value));
    const groupItems = computed(() => buildDurationGroupStats(props.flow, kind.value));
    const sortedGroupItems = computed(() => {
      const info = Array.isArray(groupSort.value) ? groupSort.value[0] : groupSort.value;
      const sortBy = info?.sortBy as keyof (typeof groupItems.value)[number] | undefined;
      if (!sortBy) return groupItems.value;
      const list = [...groupItems.value];
      const descending = !!info?.descending;
      list.sort((left, right) => {
        const leftValue = left[sortBy];
        const rightValue = right[sortBy];
        if (typeof leftValue === 'string' && typeof rightValue === 'string') {
          return descending ? rightValue.localeCompare(leftValue) : leftValue.localeCompare(rightValue);
        }
        return descending ? Number(rightValue) - Number(leftValue) : Number(leftValue) - Number(rightValue);
      });
      return list;
    });
    const nameColumnTitle = computed(() => {
      if (kind.value === 'TOOL') return t('工具');
      if (kind.value === 'AGENT') return 'Agent';
      return t('模型');
    });
    const countColumnTitle = computed(() => (kind.value === 'TOOL' ? t('执行次数') : t('调用次数')));
    const groupColumns = computed<any[]>(() => [
      {
        colKey: 'name',
        title: nameColumnTitle.value,
        width: 200,
        ellipsis: true,
        ellipsisTitle: false,
      },
      {
        colKey: 'count',
        title: countColumnTitle.value,
        width: 87,
        align: 'right',
        ellipsis: true,
        ellipsisTitle: false,
        sorter: true,
      },
      {
        colKey: 'errorCount',
        title: t('异常次数'),
        width: 87,
        align: 'right',
        ellipsis: true,
        ellipsisTitle: false,
        sorter: true,
      },
      {
        colKey: 'p50',
        title: t('P50 耗时'),
        width: 87,
        align: 'right',
        ellipsis: true,
        ellipsisTitle: false,
        sorter: true,
        cell: (_h, { row }: { row: number }) => formatDuration(row.p50),
      },
      {
        colKey: 'p95',
        title: t('P95 耗时'),
        width: 86,
        align: 'right',
        ellipsis: true,
        ellipsisTitle: false,
        sorter: true,
        cell: (_h, { row }: { row: number }) => formatDuration(row.p95),
      },
      {
        colKey: 'avg',
        title: t('平均耗时'),
        width: 85,
        align: 'right',
        ellipsis: true,
        ellipsisTitle: false,
        sorter: true,
        cell: (_h, { row }: { row: number }) => formatDuration(row.avg),
      },
    ]);
    const panelStyle = computed(() => (props.maxHeight ? { maxHeight: `${props.maxHeight}px` } : {}));
    /** 当前 Tab（含聚合 / 列表模式）是否存在数据，用于决定是否展示工具栏 */
    const hasData = computed(() => {
      if (!props.flowLoaded) return false;
      return aggregated.value ? groupItems.value.length > 0 : spanItems.value.length > 0;
    });
    const tableMaxHeight = computed(() =>
      props.maxHeight ? Math.max(160, props.maxHeight - PANEL_CHROME_HEIGHT) : DEFAULT_TABLE_MAX_HEIGHT
    );

    const handleGroupSortChange = (sort: TableSort) => {
      groupSort.value = sort || [];
    };

    const handleViewDetail = (spanId: string) => {
      if (findSpanRowView(props.flow, spanId)) emit('view-detail', spanId);
    };

    const renderToolbar = () => {
      // 当前 Tab 无数据时隐藏工具条
      if (!hasData.value) return null;
      return (
        <div class='llm-duration-stats-toolbar'>
          <div class='llm-duration-stats-aggregate'>
            <Switcher
              modelValue={aggregated.value}
              theme='primary'
              onChange={(value: boolean) => {
                aggregated.value = value;
              }}
            />
            <span>{t('聚合查看')}</span>
          </div>
          {aggregated.value ? null : (
            <Radio.Group
              class='llm-duration-stats-rank'
              modelValue={rankMode.value}
              type='capsule'
              onChange={(value: DurationRankMode) => {
                rankMode.value = value;
              }}
            >
              <Radio.Button label='top'>Top 10</Radio.Button>
              <Radio.Button label='bottom'>Bottom 10</Radio.Button>
            </Radio.Group>
          )}
        </div>
      );
    };

    const renderSpanItem = (item: DurationSpanStat) => (
      <div
        key={item.spanId}
        class='llm-duration-stats-item'
      >
        <div class='llm-duration-stats-item-main'>
          <div class='llm-duration-stats-item-meta'>
            <span class='llm-duration-stats-item-names'>
              <span class='is-time'>{dayjs(item.startTime / 1000).format('HH:mm:ss')}</span>
              <span
                class='is-name'
                v-overflow-tips={{ content: item.name, placement: 'top' }}
              >
                {item.name}
              </span>
            </span>
            <span class='llm-duration-stats-item-values'>
              <span class='is-duration'>{formatDuration(item.elapsedTime)}</span>
              <span class='is-percent'>{formatPercent(item.percent)}</span>
            </span>
          </div>
          <div class='llm-duration-stats-bar'>
            <span
              style={{ width: `${Math.min(100, Math.max(0, item.percent))}%` }}
              class='llm-duration-stats-bar-fill'
            />
          </div>
        </div>
        <div class='llm-duration-stats-item-actions'>
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
        return <div class='llm-duration-stats-placeholder'>{t('加载中...')}</div>;
      }
      if (!props.flowLoaded) {
        return (
          <Exception
            class='llm-duration-stats-empty'
            scene='part'
            title={t('暂无数据')}
            type='empty'
          />
        );
      }
      if (aggregated.value) {
        if (!groupItems.value.length) {
          return (
            <Exception
              class='llm-duration-stats-empty'
              scene='part'
              title={t('暂无数据')}
              type='empty'
            />
          );
        }
        return (
          <PrimaryTable
            class='llm-duration-stats-table'
            columns={groupColumns.value}
            data={sortedGroupItems.value}
            maxHeight={tableMaxHeight.value}
            needCustomScroll={false}
            rowKey='key'
            size='small'
            sort={groupSort.value}
            stripe
            hover
            onSortChange={handleGroupSortChange}
          />
        );
      }
      if (!spanItems.value.length) {
        return (
          <Exception
            class='llm-duration-stats-empty'
            scene='part'
            title={t('暂无数据')}
            type='empty'
          />
        );
      }
      return <div class='llm-duration-stats-list'>{spanItems.value.map(renderSpanItem)}</div>;
    };

    return () => (
      <div
        class='llm-duration-stats-panel'
        style={panelStyle.value}
      >
        <div class='llm-duration-stats-header'>
          <div class='llm-duration-stats-title'>{t('耗时统计分析')}</div>
          <div class='llm-duration-stats-tabs'>
            {KIND_TABS.map(tab => (
              <button
                key={tab.id}
                class={['llm-duration-stats-tab', { 'is-active': kind.value === tab.id }]}
                type='button'
                onClick={() => {
                  kind.value = tab.id;
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
        <div class='llm-duration-stats-content'>
          {renderToolbar()}
          {renderBody()}
        </div>
      </div>
    );
  },
});
