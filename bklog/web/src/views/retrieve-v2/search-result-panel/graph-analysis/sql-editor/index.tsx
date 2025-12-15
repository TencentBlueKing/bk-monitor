/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
import { computed, defineComponent, onMounted, ref, type Ref } from 'vue';

import $http from '@/api/index.js';
import useFieldAliasRequestParams from '@/hooks/use-field-alias-request-params';
import useLocale from '@/hooks/use-locale';
import useResizeObserve from '@/hooks/use-resize-observe';
import useRetrieveEvent from '@/hooks/use-retrieve-event';
import useStore from '@/hooks/use-store';
import { debounce } from 'lodash-es';
import screenfull from 'screenfull';
import { formatDialect, transactsql } from 'sql-formatter';

import { parseBigNumberList, readBlobRespToJson } from '@/common/util';
import { requestBlob } from '@/request';
import { getCommonFilterAdditionWithValues } from '../../../../../store/helper';
import RetrieveHelper, { RetrieveEvent } from '../../../../retrieve-helper';
import BookmarkPop from '../../../search-bar/components/bookmark-pop.vue';
import useEditor from './use-editor';

import './index.scss';

export default defineComponent({
  props: {
    extendParams: {
      type: Object,
      default: () => ({}),
    },
  },
  emits: ['change', 'sql-change', 'error'],
  setup(props, { emit, expose }) {
    const store = useStore();
    const refRootElement: Ref<HTMLElement> = ref();
    const refSqlBox: Ref<HTMLElement> = ref();
    const refSqlPreviewElement: Ref<HTMLElement> = ref();
    const isRequesting = ref(false);
    const isSyncSqlRequesting = ref(false);
    const isPreviewSqlShow = ref(false);
    const sqlPreviewHeight = ref(0);
    const previewSqlContent = ref('');

    const sqlContent = computed(() => store.state.indexItem.chart_params.sql);

    const isFullscreen = ref(false);
    const onValueChange = (value: any) => {
      if (value !== sqlContent.value) {
        store.commit('updateChartParams', { sql: value });
        emit('sql-change', value);
      }
    };
    const { $t } = useLocale();
    const { editorInstance } = useEditor({ refRootElement, sqlContent, onValueChange });
    const { alias_settings } = useFieldAliasRequestParams();

    const indexSetId = computed(() => store.state.indexId);
    const retrieveParams = computed(() => store.getters.retrieveParams);
    const requestAddition = computed(() => store.getters.requestAddition);
    // eslint-disable-next-line camelcase
    const filter_addition = computed(() => getCommonFilterAdditionWithValues(store.state));

    let abortController: AbortController | null = null;

    const handleQueryBtnClick = () => {
      const sql = editorInstance?.value?.getValue();
      if (!sql || isRequesting.value) {
        return;
      }

      isRequesting.value = true;
      emit('change', undefined, isRequesting.value);

      // 取消之前的请求
      if (abortController) {
        abortController.abort();
      }

      // 创建新的 AbortController
      abortController = new AbortController();
      const { signal } = abortController;


      const { start_time, end_time, keyword } = retrieveParams.value;
      const requestParams = {
        start_time,
        end_time,
        query_mode: 'sql',
        keyword,
        addition: requestAddition.value,
        sql,
        // eslint-disable-next-line camelcase
        alias_settings: alias_settings.value,
      };

      emit('error', { code: 200, message: '请求中', result: true });

      RetrieveHelper.reportLog({
        trigger_source: 'graph_analysis',
        action: 'request',
      }, store.state);

      return requestBlob({
        url: `/search/index_set/${indexSetId.value}/chart/`,
        params: requestParams,
        method: 'POST',
        signal,
      })
        .then(async (response: Response) => {
          // 获取 blob 响应
          const blob = await response.blob();

          // 使用 readBlobRespToJson 解析，保证长整型精度
          const resp = await readBlobRespToJson(blob);

          // 检查响应状态和业务结果
          if (!response.ok) {
            // HTTP 状态码错误，抛出解析后的错误响应
            throw resp;
          }

          if (!resp.result) {
            // 业务逻辑错误
            emit('error', resp);
            return;
          }

          // 处理 BigNumber 数据，将 list 中的 BigNumber 对象转换为字符串或数字
          if (resp.data?.list && Array.isArray(resp.data.list)) {
            resp.data.list = parseBigNumberList(resp.data.list);
          }

          // 成功时 emit 数据
          emit('change', resp);
          return resp;
        })
        .catch((err: any) => {
          if (err.name === 'AbortError' || signal.aborted) {
            console.log('请求被取消');
            return;
          }

          // 如果是响应数据，直接使用
          if (err && typeof err === 'object' && 'result' in err) {
            emit('error', err);
          } else {
            emit('error', { code: 500, message: err?.message || '请求失败', result: false });
          }
        })
        .finally(() => {
          // 统一在 finally 中更新请求状态
          isRequesting.value = false;
          emit('change', undefined, isRequesting.value);
          abortController = null;
        });
    };

    const handleStopBtnClick = () => {
      if (abortController) {
        abortController.abort();
        abortController = null;
      }
      isRequesting.value = false;
    };

    // 创建类型安全的自定义方言
    const createExtendedTSQL = () => {
      const baseIdentTypes = [...transactsql.tokenizerOptions.identTypes];
      return {
        ...transactsql,
        name: 'extended-transactsql',
        tokenizerOptions: {
          ...transactsql.tokenizerOptions,
          // 添加反引号标识符支持，同时保留原有的双引号和方括号支持
          // @ts-ignore - identTypes 类型定义较严格，但实际运行时支持字符串类型
          identTypes: [
            ...baseIdentTypes,
            '``', // 添加反引号支持
          ],
          // 允许标识符以数字开头，这是 MySQL 反引号标识符的特性
          identChars: {
            ...transactsql.tokenizerOptions.identChars,
            allowFirstCharNumber: true,
          },
        },
      };
    };

    // 使用示例
    const extendedTsql = createExtendedTSQL();

    const getFormatValue = (sql) => {
      try {
        // @ts-ignore - extendedTsql 的类型定义与 formatDialect 期望的类型不完全匹配，但运行时正常
        return formatDialect(sql, { dialect: extendedTsql });
      } catch (err) {
        console.error(err);
        return sql;
      }
    };

    const handleSyncAdditionToSQL = (callback?) => {
      const { start_time, end_time, keyword } = retrieveParams.value;
      isSyncSqlRequesting.value = true;
      return $http
        .request('graphAnalysis/generateSql', {
          params: {
            index_set_id: indexSetId.value,
          },
          data: {
            // eslint-disable-next-line camelcase
            addition: [...requestAddition.value, ...(filter_addition.value ?? []).filter(a => a.value?.length)],
            start_time,
            end_time,
            keyword,
            sql: sqlContent.value,
            // eslint-disable-next-line camelcase
            alias_settings: alias_settings.value,
          },
        })
        .then((resp) => {
          editorInstance.value.setValue(resp.data.sql);
          editorInstance.value.focus();
          onValueChange(resp.data.sql);
          setTimeout(() => {
            formatMonacoSqlCode();
          });

          previewSqlContent.value = getFormatValue(resp.data.additional_where_clause);
          isPreviewSqlShow.value = true;
          callback?.();
        })
        .catch((err) => {
          console.error(err);
        })
        .finally(() => {
          isSyncSqlRequesting.value = false;
        });
    };

    const debounceSyncAdditionToSQL = debounce(handleSyncAdditionToSQL, 500);

    const handleFullscreenClick = () => {
      if (!screenfull.isEnabled) {
        return;
      }
      isFullscreen.value ? screenfull.exit() : screenfull.request(refSqlBox.value);
      isFullscreen.value = !isFullscreen.value;
      editorInstance.value.focus();
    };

    const formatMonacoSqlCode = (value?: string) => {
      const val = getFormatValue(value ?? editorInstance.value?.getValue() ?? '');
      editorInstance.value?.setValue([val].join('\n'));
    };

    const renderTools = () => {
      return (
        <div class='sql-editor-tools'>
          <bk-button
            class='sql-editor-query-button'
            v-bk-tooltips={{ content: $t('查询'), theme: 'light' }}
            loading={isRequesting.value}
            size='small'
            theme='primary'
            onClick={handleQueryBtnClick}
          >
            <i class='bklog-icon bklog-bofang' />
          </bk-button>
          <bk-button
            class='sql-editor-view-button'
            v-bk-tooltips={{ content: $t('中止'), theme: 'light' }}
            disabled={!isRequesting.value}
            size='small'
            onClick={handleStopBtnClick}
          >
            <i class='bk-icon icon-stop-shape' />
          </bk-button>

          <BookmarkPop
            class='bklog-sqleditor-bookmark'
            v-bk-tooltips={{ content: ($t('button-收藏') as string).replace('button-', ''), theme: 'light' }}
            addition={requestAddition.value ?? []}
            extendParams={props.extendParams}
            search-mode='sqlChart'
            sql={retrieveParams.value.keyword}
          />
        </div>
      );
    };

    const renderHeadTools = () => {
      return (
        <div class='bk-monaco-tools'>
          <span>{$t('SQL查询')}</span>
          <div>
            <div class='fr header-tool-right'>
              <div
                class='sqlFormat header-tool-right-icon'
                v-bk-tooltips={{ content: $t('格式化') }}
                onClick={() => formatMonacoSqlCode()}
              >
                <span class='bk-icon icon-script-file' />
              </div>
              {isFullscreen.value ? (
                <div
                  class='header-tool-right-icon'
                  v-bk-tooltips={{ content: $t('取消全屏') }}
                  onClick={handleFullscreenClick}
                >
                  <span class='bk-icon icon-un-full-screen' />
                </div>
              ) : (
                <div
                  class='header-tool-right-icon'
                  v-bk-tooltips={{ content: $t('全屏') }}
                  onClick={handleFullscreenClick}
                >
                  <span class='bk-icon icon-full-screen' />
                </div>
              )}
            </div>
          </div>
        </div>
      );
    };

    const renderSqlPreview = () => {
      return (
        <div
          ref={refSqlPreviewElement}
          class={['sql-preview-root', { 'is-show': isPreviewSqlShow.value }]}
        >
          <div class='sql-preview-title'>
            <span class='bklog-icon bklog-circle-alert-filled' />
            {$t('检测到「顶部查询条件」，已自动补充 SQL（与已输入 SQL 语句叠加生效）：')}
          </div>
          <div class='sql-preview-text'>{previewSqlContent.value}</div>
        </div>
      );
    };

    const debounceQuery = debounce(handleQueryBtnClick, 120);
    const debounceUpdateHeight = debounce(() => {
      if (!refSqlPreviewElement?.value) {
        sqlPreviewHeight.value = 0;
        return;
      }

      sqlPreviewHeight.value = refSqlPreviewElement.value.offsetHeight;
    });

    /**
     * 监听关联数据变化
     */
    const onRefereceChange = (args) => {
      // 这里表示数据来自图表分析收藏点击回填数据
      if (args?.params?.chart_params?.sql?.length) {
        const old = editorInstance.value?.getValue();
        if (old !== args?.params?.chart_params?.sql) {
          editorInstance.value?.setValue(args?.params?.chart_params?.sql);
        }
        debounceQuery();
        return;
      }

      // 这里表示来自原始日志收藏或者查询参数相关改变时触发
      debounceSyncAdditionToSQL(handleQueryBtnClick);
    };

    const { addEvent } = useRetrieveEvent();
    addEvent(
      [
        RetrieveEvent.SEARCH_VALUE_CHANGE,
        RetrieveEvent.FAVORITE_ACTIVE_CHANGE,
        RetrieveEvent.SEARCH_TIME_CHANGE,
        RetrieveEvent.LEFT_FIELD_INFO_UPDATE,
      ],
      onRefereceChange,
    );
    useResizeObserve(refSqlPreviewElement, debounceUpdateHeight);

    onMounted(() => {
      if (!RetrieveHelper.isSearching) {
        debounceSyncAdditionToSQL(debounceQuery);
      }
    });

    expose({
      handleQueryBtnClick,
    });

    const sqlRootStyle = computed(() => {
      return {
        paddingBottom: `${(isPreviewSqlShow.value ? sqlPreviewHeight.value : 0) + 38}px`,
      };
    });

    return {
      refRootElement,
      refSqlBox,
      previewSqlContent,
      sqlContent,
      sqlRootStyle,
      renderTools,
      renderHeadTools,
      renderSqlPreview,
      handleQueryBtnClick,
    };
  },
  render() {
    return (
      <div
        ref='refSqlBox'
        style={this.sqlRootStyle}
        class='bklog-sql-editor-root'
      >
        <div
          ref='refRootElement'
          class='bklog-sql-editor'
        >
          {this.renderHeadTools()}
        </div>
        {this.renderSqlPreview()}
        {this.renderTools()}
      </div>
    );
  },
});
