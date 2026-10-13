import { type PropType, defineComponent } from 'vue';

import { PrimaryTable, type TdPrimaryTableProps } from '@blueking/tdesign-ui';
import { AlarmTableSkeletonCell } from '../components/alarm-skeleton';
import { Button } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import './detail-loading.scss';

const block = (width: number | string, height = 12) => (
  <span class='detail-loading-block' style={{ width: typeof width === 'number' ? `${width}px` : width, height: `${height}px` }} />
);
const trend = '0,64 35,62 70,48 105,51 140,43 175,50 210,47 245,27 280,32 315,37 350,25 385,36 420,39 455,52 490,47 525,60 560,52 600,55';

export const DetailLoadStatus = defineComponent({
  name: 'DetailLoadStatus',
  props: { loading: Boolean, error: Boolean },
  emits: { retry: () => true },
  setup(props, { emit }) {
    const { t } = useI18n();
    return () => props.loading ? (
      <div class='detail-refresh-progress' role='status' aria-label={t('加载中...')} />
    ) : props.error ? (
      <div class='detail-load-error' role='alert'>
        <span>{t('加载失败')}</span>
        <Button text onClick={() => emit('retry')}>{t('重试')}</Button>
      </div>
    ) : null;
  },
});

export default defineComponent({
  name: 'DetailLoading',
  props: {
    variant: { type: String as PropType<'header' | 'detail' | 'chart' | 'dashboard' | 'records' | 'form' | 'treemap' | 'status' | 'tags' | 'list'>, default: 'chart' },
    showTitle: { type: Boolean, default: true },
  },
  setup(props) {
    const { t } = useI18n();
    const chart = () => (
      <div class='detail-loading-chart'>
        {props.showTitle && <div class='detail-loading-chart-heading'>
          <div class='detail-loading-row'>{block('28%')}{block(24, 8)}</div>
          <div class='detail-loading-chart-subtitle'>{block('42%', 10)}</div>
        </div>}
        <div class='detail-loading-plot'>
          <div class='detail-loading-ticks'>{[0, 1, 2, 3].map(i => <div key={i}>{block(28, 8)}</div>)}</div>
          <div class='detail-loading-plot-main'>
            <div class='detail-loading-trend'>
              <svg viewBox='0 0 600 100' preserveAspectRatio='none' focusable='false'>
                <polygon points={`0,100 ${trend} 600,100`} />
                <polyline points={trend} vector-effect='non-scaling-stroke' />
              </svg>
            </div>
            <div class='detail-loading-row'>{[0, 1, 2, 3, 4].map(i => <div key={i}>{block(36, 8)}</div>)}</div>
          </div>
        </div>
      </div>
    );
    const form = () => (
      <div class='detail-loading-fields'>
        {[96, 140, 112, 180, 80, 124, 160, 108, 136].map((width, i) => (
          <div class='detail-loading-field' key={i}>{block(64)}{block(width)}</div>
        ))}
      </div>
    );
    return () => (
      <div class={['detail-loading', `detail-loading--${props.variant}`]} role='status' aria-label={t('加载中...')} aria-busy='true'>
        <div class='detail-loading-content' aria-hidden='true'>
          {props.variant === 'header' ? (
            <div class='detail-loading-header'>
              {block(36, 36)}
              <div class='detail-loading-title'>{block(120, 10)}{block('65%', 16)}</div>
              <div class='detail-loading-actions'>{block(72, 28)}{block(72, 28)}</div>
            </div>
          ) : props.variant === 'detail' ? (
            <>
              <div class='detail-loading-card detail-loading-summary'>
                <div class='detail-loading-row'>{block(96, 20)}{block(136, 16)}</div>
                {block('72%')}{block('48%')}
              </div>
              <div class='detail-loading-card'>
                {block(64)}
                <div class='detail-loading-tags'>{[160, 112, 184].map(w => <div key={w}>{block(w, 24)}</div>)}</div>
                {block(64)}{form()}
              </div>
              <div class='detail-loading-tabs'>{[64, 48, 64, 48].map((w, i) => <div key={i}>{block(w)}</div>)}</div>
              <div class='detail-loading-card detail-loading-chart-card'>{chart()}</div>
            </>
          ) : props.variant === 'dashboard' ? (
            <div class='detail-loading-dashboard'>{[0, 1, 2, 3].map(i => <div key={i} class='detail-loading-card detail-loading-chart-card'>{chart()}</div>)}</div>
          ) : props.variant === 'tags' ? (
            <div class='detail-loading-choices'>{[72, 64, 88].map(w => <div key={w}>{block(14, 14)}{block(w)}</div>)}</div>
          ) : props.variant === 'list' ? (
            <div class='detail-loading-list'>{[112, 168, 136].map(w => <div key={w}>{block(w)}</div>)}</div>
          ) : props.variant === 'status' ? (
            <div class='detail-loading-status'>{block(40, 40)}{block('36%', 16)}{block('72%')}{block('56%')}</div>
          ) : props.variant === 'treemap' ? (
            <div class='detail-loading-treemap'>{[0, 1, 2, 3, 4, 5].map(i => <span key={i} class='detail-loading-block' />)}</div>
          ) : props.variant === 'records' ? (
            <div class='detail-loading-records'>{[0, 1, 2].map(i => (
              <div key={i} class='detail-loading-record'>{block(24, 24)}
                <div class='detail-loading-title'>{block(164)}{block(`${[72, 58, 84][i]}%`)}{block(108, 10)}</div>
              </div>
            ))}</div>
          ) : props.variant === 'form' ? form() : chart()}
        </div>
      </div>
    );
  },
});

export const DetailTableSkeleton = defineComponent({
  name: 'DetailTableSkeleton',
  props: {
    columns: { type: Array as PropType<TdPrimaryTableProps['columns']>, default: () => [] },
  },
  setup(props) {
    const { t } = useI18n();
    return () => (
      <div class='detail-table-skeleton' aria-label={t('加载中...')} aria-busy='true'>
        <PrimaryTable
          columns={props.columns.map(column => ({
            ...column,
            sorter: false,
            filter: undefined,
            cell: (_h, { rowIndex }) => <AlarmTableSkeletonCell columnKey={column.colKey} rowIndex={rowIndex} />,
          }))}
          data={Array.from({ length: 6 }, (_, id) => ({ id }))}
          rowKey='id'
          needCustomScroll={false}
          tableLayout='fixed'
        />
      </div>
    );
  },
});
