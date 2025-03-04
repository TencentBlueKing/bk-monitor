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
import { computed, defineComponent, Ref, ref, watch } from 'vue';

import $http from '@/api/index.js';
import useLocale from '@/hooks/use-locale';
import useResizeObserve from '@/hooks/use-resize-observe';
import useStore from '@/hooks/use-store';
import RequestPool from '@/store/request-pool';
import axios from 'axios';
import { debounce } from 'lodash';
import screenfull from 'screenfull';
import { format } from 'sql-formatter';

import BookmarkPop from '../../../search-bar/bookmark-pop.vue';
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
    const isRequesting = ref(false);
    const isSyncSqlRequesting = ref(false);
    const isPreviewSqlShow = ref(false);
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

    const editorConfig = ref({
      height: 400,
    });

    const indexSetId = computed(() => store.state.indexId);
    const retrieveParams = computed(() => store.getters.retrieveParams);

    useResizeObserve(
      refRootElement,
      entry => {
        editorConfig.value.height = entry.target?.offsetHeight ?? 400;
      },
      60,
    );

    const requestId = 'graphAnalysis_searchSQL';

    const handleQueryBtnClick = () => {
      const sql = editorInstance?.value?.getValue();

      if (!sql || isRequesting.value) {
        return;
      }

      isRequesting.value = true;
      emit('change', undefined, isRequesting.value);

      const requestCancelToken = RequestPool.getCancelToken(requestId);
      const baseUrl = process.env.NODE_ENV === 'development' ? 'api/v1' : (window as any).AJAX_URL_PREFIX;
      const { start_time, end_time } = retrieveParams.value;
      const params = {
        method: 'post',
        url: `/search/index_set/${indexSetId.value}/chart/`,
        cancelToken: requestCancelToken,
        withCredentials: true,
        baseURL: baseUrl,
        data: {
          start_time,
          end_time,
          query_mode: 'sql',
          sql, // 使用获取到的内容
        },
      };

      emit('error', { code: 200, message: '请求中', result: true });

      return axios(params)
        .then((resp: any) => {
          if (resp.data.result) {
            isRequesting.value = false;
            emit('change', resp.data);
          } else {
            emit('error', resp.data);
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

    const handleSyncAdditionToSQL = () => {
      const { addition, start_time, end_time } = retrieveParams.value;
      isSyncSqlRequesting.value = true;
      return $http
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
          editorInstance.value.setValue(resp.data.sql);
          editorInstance.value.focus();
          onValueChange(resp.data.sql);
          setTimeout(() => {
            formatMonacoSqlCode();
          });
        })
        .finally(() => {
          isSyncSqlRequesting.value = false;
        });
    };

    const handleFullscreenClick = () => {
      if (!screenfull.isEnabled) return;
      isFullscreen.value ? screenfull.exit() : screenfull.request(refSqlBox.value);
      isFullscreen.value = !isFullscreen.value;
      editorInstance.value.focus();
    };

    const formatMonacoSqlCode = (value?: string) => {
      const val = format(value ?? editorInstance.value?.getValue() ?? '', { language: 'mysql' });
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
            <i class='bklog-icon bklog-bofang'></i>
            {/* <span class='ml-min'>{$t('查询')}</span> */}
          </bk-button>
          <bk-button
            class='sql-editor-view-button'
            v-bk-tooltips={{ content: $t('中止'), theme: 'light' }}
            disabled={!isRequesting.value}
            size='small'
            onClick={handleStopBtnClick}
          >
            <i class='bk-icon icon-stop-shape' />
            {/* <span>{$t('中止')}</span> */}
          </bk-button>
          <bk-popconfirm
            width='288'
            content={$t('此操作将根据当前日志查询条件覆盖当前SQL查询语句，请谨慎操作')}
            trigger='click'
            onConfirm={handleSyncAdditionToSQL}
          >
            <bk-button
              class='sql-editor-view-button'
              v-bk-tooltips={{ content: $t('同步查询条件到SQL'), theme: 'light' }}
              loading={isSyncSqlRequesting.value}
              size='small'
            >
              <i class='bklog-icon bklog-tongbu'></i>
            </bk-button>
          </bk-popconfirm>
          <BookmarkPop
            class='bklog-sqleditor-bookmark'
            v-bk-tooltips={{ content: ($t('button-收藏') as string).replace('button-', ''), theme: 'light' }}
            addition={retrieveParams.value.addition ?? []}
            extendParams={props.extendParams}
            search-mode='sqlChart'
            sql={retrieveParams.value.keyword}
          ></BookmarkPop>
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
                <span class='bk-icon icon-script-file'></span>
              </div>
              {isFullscreen.value ? (
                <div
                  class='header-tool-right-icon'
                  v-bk-tooltips={{ content: $t('取消全屏') }}
                  onClick={handleFullscreenClick}
                >
                  <span class='bk-icon icon-un-full-screen'></span>
                </div>
              ) : (
                <div
                  class='header-tool-right-icon'
                  v-bk-tooltips={{ content: $t('全屏') }}
                  onClick={handleFullscreenClick}
                >
                  <span class='bk-icon icon-full-screen'></span>
                </div>
              )}
            </div>
          </div>
        </div>
      );
    };
    const handleUpdateIsContentShow = val => {
      isPreviewSqlShow.value = val;
    };

    const debounceQuery = debounce(handleQueryBtnClick, 120);

    // 如果是来自收藏跳转，retrieveParams.value.chart_params 会保存之前的收藏查询
    // 这里会回填收藏的查询
    watch(
      () => [sqlContent.value],
      async (val, oldVal) => {
        if (!val[0] && !oldVal?.[0]) {
          await handleSyncAdditionToSQL();
          debounceQuery();
          return;
        }

        if (val[0] !== (editorInstance.value?.getValue() ?? '')) {
          editorInstance.value?.setValue(sqlContent.value);
          debounceQuery();
        }
      },
      {
        immediate: true,
      },
    );

    expose({
      handleQueryBtnClick,
    });

    return {
      refRootElement,
      refSqlBox,
      isPreviewSqlShow,
      sqlContent,
      renderTools,
      renderHeadTools,
      handleUpdateIsContentShow,
      handleQueryBtnClick,
    };
  },
  render() {
    return (
      <div
        ref='refSqlBox'
        class='bklog-sql-editor-root'
      >
        <div
          ref='refRootElement'
          class='bklog-sql-editor'
        >
          {this.renderHeadTools()}
        </div>
        {this.renderTools()}
      </div>
    );
  },
});
