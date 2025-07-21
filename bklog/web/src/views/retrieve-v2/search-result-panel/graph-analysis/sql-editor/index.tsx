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
import { axiosInstance } from '@/api';
import $http from '@/api/index.js';
import useFieldAliasRequestParams from '@/hooks/use-field-alias-request-params';
import useLocale from '@/hooks/use-locale';
import useResizeObserve from '@/hooks/use-resize-observe';
import useStore from '@/hooks/use-store';
import RequestPool from '@/store/request-pool';
import { debounce } from 'lodash';
import screenfull from 'screenfull';
import { format } from 'sql-formatter';
import { computed, defineComponent, Ref, ref, onMounted } from 'vue';

import { getCommonFilterAdditionWithValues } from '../../../../../store/helper';
import RetrieveHelper, { RetrieveEvent } from '../../../../retrieve-helper';
import BookmarkPop from '../../../search-bar/bookmark-pop.vue';

import './index.scss';
import useEditor from './use-editor';

export default defineComponent({
  props: {
    extendParams: {
      type: Object,
      default: () => ({}),
    },
  },
  emits: ['change', 'sql-change', 'error'],
  render() {
    return (
      <div
        class="bklog-sql-editor-root"
        ref="refSqlBox"
        style={this.sqlRootStyle}
      >
        <div class="bklog-sql-editor" ref="refRootElement">
          {this.renderHeadTools()}
        </div>
        {this.renderSqlPreview()}
        {this.renderTools()}
      </div>
    );
  },
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
    const { editorInstance } = useEditor({
      onValueChange,
      refRootElement,
      sqlContent,
    });
    const { alias_settings } = useFieldAliasRequestParams();

    const indexSetId = computed(() => store.state.indexId);
    const retrieveParams = computed(() => store.getters.retrieveParams);
    const filter_addition = computed(() =>
      getCommonFilterAdditionWithValues(store.state)
    );

    const requestId = 'graphAnalysis_searchSQL';

    const handleQueryBtnClick = () => {
      const sql = editorInstance?.value?.getValue();
      if (!sql || isRequesting.value) {
        return;
      }

      isRequesting.value = true;
      emit('change', undefined, isRequesting.value);
      RequestPool.execCanceToken(requestId);
      const requestCancelToken = RequestPool.getCancelToken(requestId);
      const baseUrl =
        process.env.NODE_ENV === 'development'
          ? 'api/v1'
          : (window as any).AJAX_URL_PREFIX;
      const { addition, end_time, keyword, start_time } = retrieveParams.value;
      const params = {
        baseURL: baseUrl,
        cancelToken: requestCancelToken,
        data: {
          addition,
          alias_settings: alias_settings.value,
          end_time,
          keyword,
          query_mode: 'sql',
          sql, // 使用获取到的内容
          start_time,
        },
        method: 'post',
        originalResponse: true,
        url: `/search/index_set/${indexSetId.value}/chart/`,
        withCredentials: true,
      };

      emit('error', { code: 200, message: '请求中', result: true });

      return axiosInstance(params)
        .then((resp: any) => {
          if (resp.result) {
            isRequesting.value = false;
            emit('change', resp);
          } else {
            emit('error', resp);
          }
        })
        .catch((err) => {
          if (err.code === 'ERR_CANCELED') {
            console.log('请求被取消');
          }
        })
        .finally(() => {
          isRequesting.value = false;
          emit('change', undefined, isRequesting.value);
        });
    };

    const handleStopBtnClick = () => {
      RequestPool.execCanceToken(requestId);
      isRequesting.value = false;
    };

    const handleSyncAdditionToSQL = (callback?) => {
      const { addition, end_time, keyword, start_time } = retrieveParams.value;
      isSyncSqlRequesting.value = true;
      return $http
        .request('graphAnalysis/generateSql', {
          data: {
            addition: [
              ...addition,
              ...(filter_addition.value ?? []).filter((a) => a.value?.length),
            ],
            alias_settings: alias_settings.value,
            end_time,
            keyword,
            sql: sqlContent.value,
            start_time,
          },
          params: {
            index_set_id: indexSetId.value,
          },
        })
        .then((resp) => {
          editorInstance.value.setValue(resp.data.sql);
          editorInstance.value.focus();
          onValueChange(resp.data.sql);
          setTimeout(() => {
            formatMonacoSqlCode();
          });

          previewSqlContent.value = format(resp.data.additional_where_clause, {
            language: 'transactsql',
          });
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
      if (!screenfull.isEnabled) return;
      isFullscreen.value
        ? screenfull.exit()
        : screenfull.request(refSqlBox.value);
      isFullscreen.value = !isFullscreen.value;
      editorInstance.value.focus();
    };

    const formatMonacoSqlCode = (value?: string) => {
      const val = format(value ?? editorInstance.value?.getValue() ?? '', {
        language: 'transactsql',
      });
      editorInstance.value?.setValue([val].join('\n'));
    };

    const renderTools = () => {
      return (
        <div class="sql-editor-tools">
          <bk-button
            class="sql-editor-query-button"
            loading={isRequesting.value}
            onClick={handleQueryBtnClick}
            size="small"
            theme="primary"
            v-bk-tooltips={{ content: $t('查询'), theme: 'light' }}
          >
            <i class="bklog-icon bklog-bofang"></i>
          </bk-button>
          <bk-button
            class="sql-editor-view-button"
            disabled={!isRequesting.value}
            onClick={handleStopBtnClick}
            size="small"
            v-bk-tooltips={{ content: $t('中止'), theme: 'light' }}
          >
            <i class="bk-icon icon-stop-shape" />
          </bk-button>

          <BookmarkPop
            addition={retrieveParams.value.addition ?? []}
            class="bklog-sqleditor-bookmark"
            extendParams={props.extendParams}
            search-mode="sqlChart"
            sql={retrieveParams.value.keyword}
            v-bk-tooltips={{
              content: ($t('button-收藏') as string).replace('button-', ''),
              theme: 'light',
            }}
          ></BookmarkPop>
        </div>
      );
    };

    const renderHeadTools = () => {
      return (
        <div class="bk-monaco-tools">
          <span>{$t('SQL查询')}</span>
          <div>
            <div class="fr header-tool-right">
              <div
                class="sqlFormat header-tool-right-icon"
                onClick={() => formatMonacoSqlCode()}
                v-bk-tooltips={{ content: $t('格式化') }}
              >
                <span class="bk-icon icon-script-file"></span>
              </div>
              {isFullscreen.value ? (
                <div
                  class="header-tool-right-icon"
                  onClick={handleFullscreenClick}
                  v-bk-tooltips={{ content: $t('取消全屏') }}
                >
                  <span class="bk-icon icon-un-full-screen"></span>
                </div>
              ) : (
                <div
                  class="header-tool-right-icon"
                  onClick={handleFullscreenClick}
                  v-bk-tooltips={{ content: $t('全屏') }}
                >
                  <span class="bk-icon icon-full-screen"></span>
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
          class={['sql-preview-root', { 'is-show': isPreviewSqlShow.value }]}
          ref={refSqlPreviewElement}
        >
          <div class="sql-preview-title">
            <span class="bklog-icon bklog-circle-alert-filled"></span>
            {$t(
              '检测到「顶部查询条件」，已自动补充 SQL（与已输入 SQL 语句叠加生效）：'
            )}
          </div>
          <div class="sql-preview-text">{previewSqlContent.value}</div>
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
    const onRefereceChange = async (args) => {
      // 这里表示数据来自图表分析收藏点击回填数据
      if (args?.params?.chart_params?.sql?.length) {
        const old = editorInstance.value?.getValue();
        if (old != args?.params?.chart_params?.sql) {
          editorInstance.value?.setValue(args?.params?.chart_params?.sql);
        }
        debounceQuery();
        return;
      }

      // 这里表示来自原始日志收藏或者查询参数相关改变时触发
      debounceSyncAdditionToSQL(handleQueryBtnClick);
    };

    // @ts-ignore
    RetrieveHelper.on(
      [
        RetrieveEvent.SEARCH_VALUE_CHANGE,
        RetrieveEvent.FAVORITE_ACTIVE_CHANGE,
        RetrieveEvent.SEARCH_TIME_CHANGE,
        RetrieveEvent.LEFT_FIELD_INFO_UPDATE,
      ],
      // eslint-disable-next-line @typescript-eslint/no-misused-promises
      onRefereceChange
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
      handleQueryBtnClick,
      previewSqlContent,
      refRootElement,
      refSqlBox,
      renderHeadTools,
      renderSqlPreview,
      renderTools,
      sqlContent,
      sqlRootStyle,
    };
  },
});
