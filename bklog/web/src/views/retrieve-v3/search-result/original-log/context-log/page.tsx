import { defineComponent, onBeforeUnmount, onMounted } from 'vue';

import RelatedLogLayout from '../standalone-tab/related-log-layout';
import { useContextRelatedLog } from '../standalone-tab/hooks/use-context-related-log';
import { useStandaloneRelatedPage } from '../standalone-tab/hooks/use-standalone-related-page';

import '../standalone-tab/index.scss';

export default defineComponent({
  name: 'StandaloneContextLogPage',
  setup() {
    const page = useStandaloneRelatedPage();
    const viewModel = useContextRelatedLog({
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
        <div class='standalone-related-log-title'>{page.t('上下文')}</div>
        {page.loading.value ? (
          <div class='standalone-related-log-loading' v-bkloading={{ isLoading: true }} />
        ) : page.error.value ? (
          page.renderError()
        ) : (
          <RelatedLogLayout
            title={page.t('上下文')}
            viewModel={{
              ...viewModel,
              indexSetId: page.indexSetId,
              rowIndex: page.rowIndex,
              retrieveParams: page.retrieveParams,
            }}
          />
        )}
      </div>
    );
  },
});
