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
  emits: ['change', 'sql-change'],
  setup(props, { emit, expose }) {
    const store = useStore();
    const refRootElement: Ref<HTMLElement> = ref();
    const refSqlBox: Ref<HTMLElement> = ref();
    const isRequesting = ref(false);
    const isSyncSqlRequesting = ref(false);
    const isPreviewSqlShow = ref(false);
    const sqlContent = ref('');
    const isFullscreen = ref(false);
    const onValueChange = (value: any) => {
      if (value !== sqlContent.value) {
        sqlContent.value = value;
        emit('sql-change', value);
      }
    };
    const { editorInstance } = useEditor({ refRootElement, sqlContent, onValueChange });

    const editorConfig = ref({
      height: 400,
    });

    const indexSetId = computed(() => store.state.indexId);
    const retrieveParams = computed(() => store.getters.retrieveParams);
    const storedParams = computed(() => store.state.indexItem.chart_params ?? {});

    const chartParams = computed(() => {
      const target = props.extendParams ?? {};

      return {
        ...target,
        chart_params: {
          ...target.chart_params,
          sql: sqlContent.value,
        },
      };
    });

    useResizeObserve(refRootElement, entry => {
      editorConfig.value.height = entry.target?.offsetHeight ?? 400;
    });

    const storeChartOptions = () => {
      store.commit('updateIndexItem', { chart_params: chartParams.value.chart_params });
    };

    const requestId = 'graphAnalysis_searchSQL';
    const handleQueryBtnClick = (updateStore = true) => {
      isRequesting.value = true;

      const requestCancelToken = RequestPool.getCancelToken(requestId);
      const baseUrl = process.env.NODE_ENV === 'development' ? 'api/v1' : (window as any).AJAX_URL_PREFIX;
      const params = {
        method: 'post',
        url: `/search/index_set/${indexSetId.value}/chart/`,
        cancelToken: requestCancelToken,
        withCredentials: true,
        baseURL: baseUrl,
        data: {
          query_mode: 'sql',
          sql: editorInstance.value.getValue(), // 使用获取到的内容
        },
      };

      return axios(params)
        .then(resp => {
          if (updateStore) {
            storeChartOptions();
          }
          isRequesting.value = false;
          emit('change', resp.data);
        })
        .finally(() => {
          isRequesting.value = false;
        });
    };

    const handleStopBtnClick = () => {
      RequestPool.execCanceToken(requestId);
      isRequesting.value = false;
    };

    const handleSyncAdditionToSQL = (storeResult = true) => {
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
          onValueChange(resp.data.sql);
          editorInstance.value.setValue(resp.data.sql);
          formatMonacoSqlCode();
          editorInstance.value.focus();
          if (storeResult) {
            storeChartOptions();
          }
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
    const formatMonacoSqlCode = () => {
      const val = format(editorInstance.value.getValue(), { language: 'mysql' });
      editorInstance.value.setValue([val].join('\n'));
    };
    const renderTools = () => {
      return (
        <div class='sql-editor-tools'>
          <bk-button
            class='sql-editor-query-button'
            v-bk-tooltips={{ content: '查询' }}
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
            v-bk-tooltips={{ content: '中止' }}
            size='small'
            onClick={handleStopBtnClick}
          >
            <i class='bk-icon icon-stop-shape' />
            {/* <span>{$t('中止')}</span> */}
          </bk-button>
          <bk-popconfirm
            width='288'
            content='此操作会覆盖当前SQL，请谨慎操作'
            trigger='click'
            onConfirm={handleSyncAdditionToSQL}
          >
            <bk-button
              class='sql-editor-view-button'
              v-bk-tooltips={{ content: '同步查询条件到SQL' }}
              loading={isSyncSqlRequesting.value}
              size='small'
            >
              <i class='bklog-icon bklog-tongbu'></i>
            </bk-button>
          </bk-popconfirm>
          <BookmarkPop
            class='bklog-sqleditor-bookmark'
            v-bk-tooltips={{ content: '收藏' }}
            addition={[]}
            extendParams={chartParams.value}
            search-mode='sqlChart'
            sql=''
          ></BookmarkPop>
        </div>
      );
    };
    const renderHeadTools = () => {
      return (
        <div
          v-if='toolsConfig.enabled'
          class='bk-monaco-tools'
        >
          <span>SQL查询</span>
          <div>
            <div class='fr header-tool-right'>
              <bk-popover
                class='sqlFormat'
                content='格式化'
              >
                <div onClick={formatMonacoSqlCode}>
                  <span class='bk-icon icon-script-file'></span>
                </div>
              </bk-popover>
              {isFullscreen.value ? (
                <bk-popover content='取消全屏'>
                  <div onClick={handleFullscreenClick}>
                    <span class='bk-icon icon-un-full-screen'></span>
                  </div>
                </bk-popover>
              ) : (
                <bk-popover content='全屏'>
                  <div onClick={handleFullscreenClick}>
                    <span class='bk-icon icon-full-screen'></span>
                  </div>
                </bk-popover>
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
      () => storedParams.value.sql,
      () => {
        if (sqlContent.value !== storedParams.value.sql) {
          if (storedParams.value.sql) {
            sqlContent.value = storedParams.value.sql;
          } else {
            handleSyncAdditionToSQL(false);
          }

          debounceQuery(false);
        }
      },
      {
        immediate: true,
        deep: true,
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