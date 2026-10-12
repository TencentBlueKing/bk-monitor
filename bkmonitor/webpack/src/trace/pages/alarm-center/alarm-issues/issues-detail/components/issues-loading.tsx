import { type PropType, defineComponent } from 'vue';

import { useI18n } from 'vue-i18n';

import BasicCard from './basic-card/basic-card';

import DetailLoading from '../../../common-detail/detail-loading';

import './issues-loading.scss';

export default defineComponent({
  name: 'IssuesLoading',
  props: {
    variant: { type: String as PropType<'page' | 'basic' | 'trend' | 'dimensions' | 'history' | 'tapd' | 'activity' | 'count'>, default: 'page' },
  },
  setup(props) {
    const { t } = useI18n();
    const block = (width: number | string, height = 12) => <span class='issues-loading-block' style={{ width: typeof width === 'number' ? `${width}px` : width, height: `${height}px` }} />;
    const rows = (type: string) => type === 'history' ? <div class='issues-loading-rows issues-loading-rows--history'>{[0, 1, 2, 3, 4].map(i => <div class='issues-loading-row' key={i}>{block(`${[58, 72, 45][i % 3]}%`)}{block(48, 10)}</div>)}</div> : <div class={`issues-loading-rows issues-loading-rows--${type}`}>
      {Array.from({ length: type === 'basic' ? 7 : 3 }, (_, i) => <div class='issues-loading-row' key={i}>
        {type === 'activity' ? block(24, 24) : type === 'basic' ? block(56) : null}
        <div class='issues-loading-text'>{block(`${[68, 86, 56][i % 3]}%`)}{type !== 'basic' && block(type === 'tapd' ? '60%' : 72, 10)}</div>
      </div>)}
    </div>;
    const trend = () => <div class='issues-loading-trend'>
      <div class='issues-loading-axis'>{[0, 1, 2].map(i => <div key={i}>{block(24, 8)}</div>)}</div>
      <div class='issues-loading-plot'>
        <div class='issues-loading-bars'>{[26, 42, 34, 58, 76, 52, 40, 68, 88, 64, 45, 32].map((height, i) => <span key={i} class='issues-loading-block' style={{ height: `${height}%` }} />)}</div>
        <div class='issues-loading-labels'>{[0, 1, 2, 3].map(i => <div key={i}>{block(28, 8)}</div>)}</div>
      </div>
    </div>;
    const dimensions = () => <div class='issues-loading-dimensions'>{[0, 1, 2].map(i => <div class='issues-loading-row' key={i}>
      {block(70)}<div class='issues-loading-segments'>{block(`${[42, 56, 34][i]}%`, 24)}{block('25%', 24)}{block('18%', 24)}</div>
    </div>)}</div>;
    const card = (content, className = '') => <BasicCard class={['issues-loading-card', className]} v-slots={{ header: () => className.includes('issues-trend-chart') ? <div class='chart-header'>{block(72, 14)}{block(96)}</div> : block(72, 14) }}>{content}</BasicCard>;
    return () => <div class={['issues-loading', `issues-loading--${props.variant}`]} role='status' aria-label={t('加载中...')} aria-busy='true'>
      <div class='issues-loading-content' aria-hidden='true'>
        {props.variant === 'page' ? <div class='issues-slider-wrapper'>
          <div class='issues-slider-left-panel'>
            <div class='issues-loading-filter'>{block('72%', 20)}{block(64, 28)}</div>
            <div class='issues-chart-wrapper'>{card(<div class='chart-body'>{trend()}</div>, 'issues-loading-chart-card issues-trend-chart')}{card(dimensions(), 'issues-loading-chart-card dimension-stats')}</div>
            <div class='issues-loading-tabs'>{[88, 88, 96].map((w, i) => <div key={i}>{block(w)}</div>)}</div>
            <DetailLoading variant='detail' />
          </div>
          <div class='issues-slider-right-panel'>
            {card(rows('basic'), 'issues-basic-info')}{card(rows('tapd'))}{card(rows('history'))}{card(rows('activity'))}
          </div>
        </div> : props.variant === 'trend' ? trend() : props.variant === 'dimensions' ? dimensions() : props.variant === 'count' ? block(32) : rows(props.variant)}
      </div>
    </div>;
  },
});
