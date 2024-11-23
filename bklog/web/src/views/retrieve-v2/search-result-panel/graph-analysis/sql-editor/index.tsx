import { computed, defineComponent, Ref, ref } from 'vue';
import useResizeObserve from '@/hooks/use-resize-observe';

import useStore from '@/hooks/use-store';
import $http from '@/api/index.js';
import useLocale from '@/hooks/use-locale';
import PreviewSql from '../common/PreviewSql.vue';

import './index.scss';
import useEditor from './use-editor';

export default defineComponent({
  emits: ['change'],
  setup(_, { emit }) {
    const store = useStore();
    const refRootElement: Ref<HTMLElement> = ref();
    const isRequesting = ref(false);
    const isSyncSqlRequesting = ref(false);
    const queryResult = ref({});
    const isPreviewSqlShow = ref(false);
    const sqlContent = ref(`SELECT
    thedate,
    dtEventTimeStamp,
    iterationIndex,
    log,
    time
FROM
    100968_proz_rd_ds2_test.doris
WHERE
    thedate >= '20241120'
    AND thedate <= '20241120'
LIMIT 200;`);

    const { editorInstance } = useEditor({ refRootElement, sqlContent });

    const editorConfig = ref({
      height: 400,
    });

    const { $t } = useLocale();
    const indexSetId = computed(() => store.state.indexId);
    const retrieveParams = computed(() => store.getters.retrieveParams);

    useResizeObserve(refRootElement, entry => {
      editorConfig.value.height = entry.target?.offsetHeight ?? 400;
    });

    const requestId = 'graphAnalysis_searchSQL';
    const handleQueryBtnClick = () => {
      isRequesting.value = true;
      $http
        .request('graphAnalysis/searchSQL', {
          requestId,
          params: {
            index_set_id: indexSetId.value,
          },
          data: {
            query_mode: 'sql',
            sql: editorInstance.value.getValue(), // 使用获取到的内容
          },
        })
        .then(resp => {
          isRequesting.value = false;
          queryResult.value = resp.data;
          emit('change', resp);
        })
        .finally(() => {
          isRequesting.value = false;
        });
    };

    const handlePreviewSqlClick = () => {
      sqlContent.value = editorInstance.value.getValue();
      isPreviewSqlShow.value = true;
    };

    const handleStopBtnClick = () => {
      $http.cancelRequest(requestId);
      isRequesting.value = false;
    };

    const handleSyncAdditionToSQL = () => {
      const { addition, start_time, end_time } = retrieveParams.value;
      isSyncSqlRequesting.value = true;
      $http
        .request('graphAnalysis/generateSql', {
          params: {
            index_set_id: indexSetId.value,
          },
          data: {
            addition,
            start_time,
            end_time,
          },
        })
        .then(resp => {
          sqlContent.value = resp.data.sql;
          editorInstance.value.setValue(resp.data.sql);
          editorInstance.value.focus();
        })
        .finally(() => {
          isSyncSqlRequesting.value = false;
        });
    };

    const renderTools = () => {
      return (
        <div class='sql-editor-tools'>
          <bk-button
            class='sql-editor-query-button'
            theme='primary'
            size='small'
            loading={isRequesting.value}
            onClick={handleQueryBtnClick}
          >
            <i class='bklog-icon bklog-bofang'></i>
            <span class='ml-min'>{$t('查询')}</span>
          </bk-button>
          <bk-button
            class='sql-editor-view-button'
            size='small'
            onClick={handleStopBtnClick}
          >
            <span class='icon bklog-icon bklog-stop' />
            <span>{$t('中止')}</span>
          </bk-button>
          <bk-button
            class='sql-editor-view-button'
            size='small'
            onClick={handlePreviewSqlClick}
          >
            {$t('预览查询 SQL')}
          </bk-button>
          <bk-popconfirm
            trigger='click'
            width='288'
            content='此操作会覆盖当前SQL，请谨慎操作'
            onConfirm={handleSyncAdditionToSQL}
          >
            <bk-button
              class='sql-editor-view-button'
              size='small'
              loading={isSyncSqlRequesting.value}
            >
              {$t('同步查询条件到SQL')}
            </bk-button>
          </bk-popconfirm>
        </div>
      );
    };

    const handleUpdateIsContentShow = val => {
      isPreviewSqlShow.value = val;
    };

    return {
      refRootElement,
      isPreviewSqlShow,
      sqlContent,
      renderTools,
      handleUpdateIsContentShow,
    };
  },
  render(h) {
    return (
      <div class='bklog-sql-editor-root'>
        <div
          ref='refRootElement'
          class='bklog-sql-editor'
        ></div>
        {this.renderTools()}
        <PreviewSql
          isShow={this.isPreviewSqlShow}
          sqlContent={this.sqlContent}
          {...{
            on: {
              'update:isShow': this.handleUpdateIsContentShow,
            },
          }}
        />
      </div>
    );
  },
});
