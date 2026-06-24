import { defineComponent, onBeforeUnmount, onMounted } from 'vue';

import RelatedLogLayout from '../standalone-tab/related-log-layout';
import RelatedLogLoading from '../standalone-tab/related-log-loading';
import { useRealtimeRelatedLog } from '../standalone-tab/hooks/use-realtime-related-log';
import { useStandaloneRelatedPage } from '../standalone-tab/hooks/use-standalone-related-page';

import '../standalone-tab/index.scss';

export default defineComponent({
  name: 'StandaloneRealTimeLogPage',
  setup() {
    const page = useStandaloneRelatedPage();
    const viewModel = useRealtimeRelatedLog({
      indexSetId: page.indexSetId,
      targetRow: page.targetRow,
      targetFields: page.targetFields,
    });

    const init = async () => {
      await page.init();
      if (page.pageReady.value) {
        await viewModel.init();
      }
    };

    onMounted(init);
    onBeforeUnmount(() => viewModel.dispose());

    return () => (
      <div class='standalone-related-log-page'>
        {page.loading.value ? (
          <RelatedLogLoading
            title='Loading...'
            text={page.loadingText.value}
            steps={[
              'Resolve URL',
              'Run search',
              'Load realtime',
            ]}
          />
        ) : page.error.value ? (
          page.renderError()
        ) : (
          <RelatedLogLayout
            title={page.t('实时日志')}
            viewModel={{
              ...viewModel,
              indexSetId: page.indexSetId,
              rowIndex: page.rowIndex,
              retrieveParams: page.retrieveParams,
            }}
            isRealTime
          />
        )}
      </div>
    );
  },
});
