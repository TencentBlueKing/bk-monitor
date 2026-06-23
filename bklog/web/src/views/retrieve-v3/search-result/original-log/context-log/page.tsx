import { defineComponent, onBeforeUnmount, onMounted } from 'vue';

import RelatedLogLayout from '../standalone-tab/related-log-layout';
import RelatedLogLoading from '../standalone-tab/related-log-loading';
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
        {/* <div class='standalone-related-log-title'>{page.t('上下文')}</div> */}
        {page.loading.value ? (
          <RelatedLogLoading
            title={page.t('上下文')}
            text={page.loadingText.value}
            steps={[
              page.t('解析 URL 中的检索参数'),
              page.t('重放检索请求并定位原始日志行'),
              page.t('加载字段配置和上下文日志'),
            ]}
          />
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
