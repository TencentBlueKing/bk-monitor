import { defineComponent, type PropType } from 'vue';

import { Button } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import './host-loading.scss';

export const HostLoadingCell = defineComponent({
  name: 'HostLoadingCell',
  props: {
    kind: { type: String, default: 'text' },
    index: { type: Number, default: 0 },
  },
  setup(props) {
    return () => (
      <div class={['host-loading-cell', `host-loading-cell--${props.kind}`]} aria-hidden='true'>
        {['checkbox', 'status', 'name'].includes(props.kind) && <span class='host-loading-cell__icon' />}
        {props.kind !== 'checkbox' && (
          <span class='host-loading-cell__content'>
            <span style={{ width: `${[68, 82, 56, 74][props.index % 4]}%` }} class='host-loading-cell__line' />
            {['metric', 'name'].includes(props.kind) && <span class='host-loading-cell__subline' />}
          </span>
        )}
      </div>
    );
  },
});

export const HostRefreshStatus = defineComponent({
  name: 'HostRefreshStatus',
  props: {
    loading: Boolean,
    error: Boolean,
  },
  emits: { retry: () => true },
  setup(props, { emit }) {
    const { t } = useI18n();
    return () => props.loading ? (
      <div class='host-refresh-status' aria-label={t('加载中...')} role='status' />
    ) : props.error ? (
      <div class='host-refresh-error' role='alert'>
        <span>{t('加载失败')}</span>
        <Button text onClick={() => emit('retry')}>{t('重试')}</Button>
      </div>
    ) : null;
  },
});

export default defineComponent({
  name: 'HostLoading',
  props: {
    variant: { type: String as PropType<'tree' | 'detail' | 'process-info' | 'dashboard' | 'chart' | 'text-unit' | 'port-status'>, default: 'chart' },
    columns: { type: Number, default: 3 },
    title: { type: Boolean, default: true },
  },
  setup(props) {
    const { t } = useI18n();
    const trendPoints =
      '0,64 35,62 70,48 105,51 140,43 175,50 210,47 245,27 280,32 315,37 350,25 385,36 420,39 455,52 490,47 525,60 560,52 600,55';
    const renderChart = (title = true) => (
      <div class='host-loading-chart'>
        {title && <div class='host-loading-chart__title'><span /><span /></div>}
        <div class='host-loading-chart__plot'>
          <div class='host-loading-chart__ticks'>{[0, 1, 2, 3].map(i => <span key={i} />)}</div>
          <div class='host-loading-chart__main'>
            <div class='host-loading-chart__line'>
              <svg focusable='false' preserveAspectRatio='none' viewBox='0 0 600 100'>
                <polygon points={`0,100 ${trendPoints} 600,100`} />
                <polyline points={trendPoints} vector-effect='non-scaling-stroke' />
              </svg>
            </div>
            <div class='host-loading-chart__axis'>{[0, 1, 2, 3, 4].map(i => <span key={i} />)}</div>
          </div>
        </div>
      </div>
    );
    return () => (
      <div class={['host-loading', `host-loading--${props.variant}`]} aria-label={t('加载中...')} aria-busy='true' role='status'>
        <div class='host-loading__content' aria-hidden='true'>
          {props.variant === 'dashboard' ? (
            <>
              <div class='host-loading__group'><span /><span /></div>
              <div class='host-loading__grid' style={{ gridTemplateColumns: `repeat(${props.columns}, minmax(0, 1fr))` }}>
                {Array.from({ length: props.columns * 2 }, (_, i) => <div key={i} class='host-loading__card'>{renderChart()}</div>)}
              </div>
            </>
          ) : props.variant === 'chart' ? renderChart(props.title) : props.variant === 'tree' ? (
            [0, 1, 2, 2, 2, 1, 2, 2, 1, 2, 2, 2].map((depth, i) => (
              <div key={i} class='host-loading__tree-row' style={{ paddingLeft: `${depth * 16}px` }}>
                <i /><span style={{ width: `${[58, 72, 48, 64][i % 4]}%` }} /><b />
              </div>
            ))
          ) : props.variant === 'detail' ? (
            Array.from({ length: 10 }, (_, i) => (
              <div key={i} class='host-loading__detail-row'><span /><span style={{ width: `${[72, 90, 62, 80][i % 4]}%` }} /></div>
            ))
          ) : props.variant === 'process-info' ? (
            <div class='host-loading__process-info'>
              <i class='host-loading__process-icon' />
              <div class='host-loading__process-main'>
                <span class='host-loading__process-title' />
                <div class='host-loading__process-meta'>
                  {[120, 176, 88, 160, 224].map((width, i) => (
                    <div key={i} style={{ width: `${width}px` }}><span /><span /></div>
                  ))}
                </div>
              </div>
            </div>
          ) : props.variant === 'text-unit' ? (
            <div class='host-loading__value'><span /><span /></div>
          ) : (
            <div class='host-loading__ports'>
              {[0, 1].map(i => (
                <div key={i} class='host-loading__port'>
                  <span class='host-loading__port-name' />
                  <div class='host-loading__port-status'><i /><span /></div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  },
});
