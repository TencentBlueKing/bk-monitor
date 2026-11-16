import { defineComponent } from 'vue';
import { ListLoadingSkeleton } from '@/shared/ui/loading/list-skeleton';
import { t } from '@/shared/composables/use-locale';
import './loading-skeleton.scss';

/** Match the client log cards rather than centring a control-sized indicator. */
export default defineComponent({
  name: 'ClientLogLoadingSkeleton',
  props: { leaving: Boolean },
  setup(props) {
    const bar = (width: string) => <span class='bklog-list-skeleton__bar' style={{ width }} />;
    return () => (
      <div class={['client-log-loading', 'bklog-skeleton-presence', { 'is-leaving': props.leaving }]}
        role='status' aria-label={t('加载中')}>
        <div class='client-log-card client-log-loading__profile' aria-hidden='true'>
          <span class='bklog-list-skeleton__bar client-log-loading__avatar' />
          <div class='client-log-loading__identity'>{bar('65%')}{bar('90%')}</div>
          <div class='client-log-loading__metadata'>
            {Array.from({ length: 6 }, (_, i) => <div key={i}>{bar(i % 2 ? '70%' : '85%')}</div>)}
          </div>
        </div>
        <div class='task-content-area' aria-hidden='true'>
          <div class='client-log-card client-log-loading__tasks'>
            {bar('35%')}
            <div class='client-log-loading__tabs'>{bar('100%')}</div>
            <div class='client-log-loading__task-list'>
              {Array.from({ length: 20 }, (_, i) => (
                <div class='client-log-loading__task' key={i}>
                  <div class='client-log-loading__task-meta'>{bar('55%')}{bar('22%')}</div>
                  {bar(`${[90, 75, 85][i % 3]}%`)}
                </div>
              ))}
            </div>
          </div>
          <div class='client-log-card client-log-loading__detail'>
            {bar('90px')}
            <div class='client-log-loading__logs'><ListLoadingSkeleton variant='log' /></div>
          </div>
        </div>
      </div>
    );
  },
});

export const ClientLogDetailSkeleton = defineComponent({
  name: 'ClientLogDetailSkeleton',
  props: { files: Boolean, leaving: Boolean },
  setup(props) {
    return () => (
      <div class={['client-log-detail-loading', 'bklog-skeleton-presence', {
        'is-files': props.files, 'is-leaving': props.leaving,
      }]} role='status' aria-label={t('加载中')}>
        {Array.from({ length: 40 }, (_, index) => (
          <div class='client-log-detail-loading__row' key={index} aria-hidden='true'>
            {props.files && <span class='client-log-detail-loading__icon' />}
            <span class='client-log-detail-loading__line' style={{ width: `${[72, 90, 58, 83, 66][index % 5]}%` }} />
          </div>
        ))}
      </div>
    );
  },
});
