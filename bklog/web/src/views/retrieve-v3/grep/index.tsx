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
import { defineComponent, onBeforeUnmount, onMounted, ref } from 'vue';

import { readBlobRespToJson } from '@/common/util';
import useFieldAliasRequestParams from '@/hooks/use-field-alias-request-params';
import useStore from '@/hooks/use-store';
import RequestPool from '@/store/request-pool';
import { debounce } from 'lodash';
import { useRoute, useRouter } from 'vue-router/composables';

import RetrieveHelper, { RetrieveEvent } from '../../retrieve-helper';
import GrepCli from './grep-cli';
import GrepCliResult from './grep-cli-result';
import { GrepRequestResult } from './types';
import { axiosInstance } from '@/api';

import './grep-cli.scss';

export default defineComponent({
  name: 'GrepView',
  components: {
    GrepCli,
    GrepCliResult,
  },
  setup() {
    const store = useStore();

    const route = useRoute();
    const router = useRouter();

    const searchValue = ref('');
    const field = ref((route.query.grep_field as string) ?? '');
    const grepQuery = ref((route.query.grep_query as string) ?? '');
    const grepRequestResult = ref<GrepRequestResult>({
      offset: 0,
      is_loading: true,
      list: [],
      has_more: true,
      is_error: false,
      exception_msg: '',
    });

    const matchMode = ref({
      caseSensitive: false,
      regexMode: false,
      wordMatch: false,
    });

    const totalMatches = ref(0);

    /**
     * 设置默认字段值
     * 如果字段值为空，检查是否有 log 字段，如果有则设置为 log 字段
     * 如果 log 字段不存在，则设置为第一个 field_type 为 text 的字段
     */
    const setDefaultFieldValue = () => {
      if (field.value === '' && store.state.indexFieldInfo.fields.length > 0) {
        const logField = store.state.indexFieldInfo.fields.find(field => field.field_name === 'log');
        if (logField) {
          field.value = logField.field_name;
        } else {
          const textField = store.state.indexFieldInfo.fields.find(field => field.field_type === 'text');
          if (textField) {
            field.value = textField.field_name;
          }
        }

        if (field.value) {
          router.replace({
            params: route.params,
            query: {
              ...route.query,
              grep_field: field.value,
            },
          });
        }
      }
    };

    const resetGrepRequestResult = () => {
      grepRequestResult.value.has_more = true;
      grepRequestResult.value.list.splice(0, grepRequestResult.value.list.length);
      grepRequestResult.value.offset = 0;
    };

    const requestGrepList = debounce(() => {
      if (!grepRequestResult.value.has_more) {
        return;
      }

      grepRequestResult.value.is_loading = true;
      grepRequestResult.value.is_error = false;
      grepRequestResult.value.exception_msg = '';

      const baseUrl = process.env.NODE_ENV === 'development' ? 'api/v1' : window.AJAX_URL_PREFIX;
      const cancelTokenKey = 'requestIndexSetGrepQueryToken';
      RequestPool.execCanceToken(cancelTokenKey);
      const requestCancelToken = RequestPool.getCancelToken(cancelTokenKey);

      const { start_time, end_time, keyword, addition } = store.state.indexItem;
      const { alias_settings, sort_list } = useFieldAliasRequestParams();

      const params: any = {
        method: 'post',
        url: `/search/index_set/${store.state.indexId}/grep_query/`,
        cancelToken: requestCancelToken,
        withCredentials: true,
        baseURL: baseUrl,
        responseType: 'blob',
        data: {
          start_time,
          end_time,
          keyword,
          addition,
          grep_query: grepQuery.value,
          grep_field: field.value,
          begin: grepRequestResult.value.offset,
          sort_list: sort_list.value,
          alias_settings: alias_settings.value,
          size: 100,
        },
      };

      if (store.state.isExternal) {
        Object.assign(params, {
          headers: {
            'X-Bk-Space-Uid': store.state.spaceUid,
          },
        });
      }

      return axiosInstance(params)
        .then((resp: any) => {
          if (resp.data && !resp.message) {
            return readBlobRespToJson(resp.data).then(({ data, result, message }) => {
              if (result) {
                grepRequestResult.value.has_more = data.list.length === 100;
                grepRequestResult.value.list.push(...data.list);
                setTimeout(() => {
                  RetrieveHelper.highLightKeywords([searchValue.value], true);
                });

                return;
              }

              grepRequestResult.value.is_loading = false;
              grepRequestResult.value.is_error = !result;
              grepRequestResult.value.exception_msg = message;
              return;
            });
          }

          grepRequestResult.value.is_loading = false;
          grepRequestResult.value.is_error = true;
          grepRequestResult.value.exception_msg = resp.message;
        })
        .catch((err: any) => {
          if (err.message === 'canceled') {
            return;
          }
          grepRequestResult.value.is_error = true;
          grepRequestResult.value.exception_msg = err.message || err;
        })
        .finally(() => {
          grepRequestResult.value.is_loading = false;
        });
    }, 120);

    // 处理搜索更新
    const handleSearchUpdate = (data: any) => {
      searchValue.value = data.searchValue;

      RetrieveHelper.highLightKeywords([searchValue.value], true);
    };

    // 处理匹配模式更新
    const handleMatchModeUpdate = (mode: any) => {
      Object.assign(matchMode.value, mode);
      RetrieveHelper.markInstance?.setCaseSensitive(matchMode.value.caseSensitive);
      RetrieveHelper.markInstance?.setRegExpMode(matchMode.value.regexMode);
      RetrieveHelper.markInstance?.setAccuracy(matchMode.value.wordMatch ? 'exactly' : 'partially');
      RetrieveHelper.highLightKeywords([searchValue.value], true);
    };

    const handleFieldChange = (v: string) => {
      field.value = v;
      resetGrepRequestResult();

      router.replace({
        params: route.params,
        query: {
          ...route.query,
          grep_field: v,
        },
      });
      requestGrepList();
    };

    // 处理grep enter
    const handleGrepEnter = (value: string) => {
      grepQuery.value = value;
      resetGrepRequestResult();
      router.replace({
        params: route.params,
        query: {
          ...route.query,
          grep_query: value,
        },
      });

      if (field.value === '') {
        return;
      }

      requestGrepList();
    };

    const handleLoadMore = () => {
      if (field.value === '') {
        return;
      }

      grepRequestResult.value.offset += 100;
      requestGrepList();
    };

    const handleRequestResult = (runRequest = true, setDefField = false) => {
      if (runRequest) {
        if (setDefField) {
          setDefaultFieldValue();
        }

        resetGrepRequestResult();
        requestGrepList();
      }
    };

    const handleSearchingChange = (isSearching: boolean) => {
      handleRequestResult(!isSearching);
    };

    RetrieveHelper.on([RetrieveEvent.SEARCH_VALUE_CHANGE, RetrieveEvent.SEARCH_TIME_CHANGE], handleRequestResult);
    RetrieveHelper.on([RetrieveEvent.SEARCHING_CHANGE, RetrieveEvent.INDEX_SET_ID_CHANGE], handleSearchingChange);

    const handleParamsChange = ({ isParamsChange, option }: { isParamsChange: boolean; option: any }) => {
      if (isParamsChange) {
        resetGrepRequestResult();
        requestGrepList();
      }

      if (option.operation === 'highlight') {
        RetrieveHelper.highLightKeywords([option.value], true);
        searchValue.value = option.value;
      }
    };

    onMounted(() => {
      RetrieveHelper.setMarkInstance();

      resetGrepRequestResult();
      setDefaultFieldValue();

      requestGrepList();
    });

    onBeforeUnmount(() => {
      resetGrepRequestResult();

      RetrieveHelper.destroyMarkInstance();
      RetrieveHelper.off(RetrieveEvent.SEARCH_VALUE_CHANGE, handleRequestResult);
      RetrieveHelper.off(RetrieveEvent.SEARCHING_CHANGE, handleSearchingChange);
      RetrieveHelper.off(RetrieveEvent.SEARCH_TIME_CHANGE, handleRequestResult);
      RetrieveHelper.off(RetrieveEvent.INDEX_SET_ID_CHANGE, handleRequestResult);
    });

    return () => (
      <div class='grep-view'>
        <GrepCli
          field-value={field.value}
          search-count={totalMatches.value}
          search-value={searchValue.value}
          on-field-change={handleFieldChange}
          on-grep-enter={handleGrepEnter}
          on-match-mode={handleMatchModeUpdate}
          on-search-change={handleSearchUpdate}
        />
        <GrepCliResult
          fieldName={field.value}
          grepRequestResult={grepRequestResult.value}
          on-load-more={handleLoadMore}
          on-params-change={handleParamsChange}
        />
      </div>
    );
  },
});
