import { computed, defineComponent, onMounted, Ref, ref, h } from 'vue';
import useResizeObserve from '@/hooks/use-resize-observe';
import * as monaco from 'monaco-editor';
import { setDorisFields } from './lang';
import useStore from '@/hooks/use-store';
import $http from '@/api/index.js';
import useLocale from '@/hooks/use-locale';
import PreviewSql from '../common/PreviewSql.vue';

import './index.scss';

export default defineComponent({
  emits: ['change'],
  setup(props, { emit }) {
    const store = useStore();
    const refRootElement: Ref<HTMLElement> = ref();
    const isRequesting = ref(false);
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
LIMIT 2;`);

    let editorInstance = null;

    const editorConfig = ref({
      height: 400,
    });

    const { $t } = useLocale();
    const fieldList = computed(() => store.state.indexFieldInfo.fields);
    const indexSetId = computed(() => store.state.indexId);

    useResizeObserve(refRootElement, entry => {
      editorConfig.value.height = entry.target?.offsetHeight ?? 400;
    });

    const initEditorInstance = () => {
      // 初始化编辑器
      editorInstance = monaco.editor.create(refRootElement.value, {
        value: sqlContent.value,
        language: 'dorisSQL',
        theme: 'vs-dark',
      });

      // 监听编辑器的键盘事件
      editorInstance.onKeyDown(e => {
        if (e.keyCode === monaco.KeyCode.Space) {
          // 阻止默认空格行为，使得我们可以手动处理
          e.preventDefault();

          // 获取当前光标位置
          const position = editorInstance.getPosition();

          // 手动插入空格
          editorInstance.executeEdits(null, [
            {
              range: new monaco.Range(position.lineNumber, position.column, position.lineNumber, position.column),
              text: ' ',
              forceMoveMarkers: true,
            },
          ]);

          // 触发自动补全
          editorInstance.trigger('keyboard', 'editor.action.triggerSuggest', {});
        }
      });
    };

    const setSuggestFields = () => {
      setDorisFields(() =>
        fieldList.value.map(field => {
          return { name: field.field_name, type: field.field_type, description: field.description };
        }),
      );
    };

    onMounted(() => {
      setTimeout(() => {
        editorConfig.value.height = refRootElement.value.offsetHeight ?? 400;
        initEditorInstance();
        setSuggestFields();
      });
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
            sql: editorInstance.getValue(), // 使用获取到的内容
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
      sqlContent.value = editorInstance.getValue();
      isPreviewSqlShow.value = true;
    };

    const handleStopBtnClick = () => {
      $http.cancelRequest(requestId);
      isRequesting.value = false;
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
      handleQueryBtnClick
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