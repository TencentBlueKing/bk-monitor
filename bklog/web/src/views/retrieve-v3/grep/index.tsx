import { defineComponent, onBeforeUnmount, onMounted, onUnmounted, Ref, ref } from 'vue';
import GrepCli from './grep-cli';
import GrepCliResult from './grep-cli-result';
import RetrieveHelper, { RetrieveEvent } from '../../retrieve-helper';
import RequestPool from '@/store/request-pool';
import { axiosInstance } from '@/api';
import useStore from '@/hooks/use-store';
import { readBlobRespToJson } from '@/common/util';
import { debounce } from 'lodash';
import './grep-cli.scss';
import { useRoute, useRouter } from 'vue-router/composables';
import { GrepRequestResult } from './types';

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
    const grepRequestResult: Ref<GrepRequestResult> = ref({
      offset: 0,
      is_loading: false,
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
    // const list = ref([]);

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
            return readBlobRespToJson(resp.data).then(({ code, data, result, message }) => {
              if (result) {
                grepRequestResult.value.has_more = data.list.length > 0;
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
      matchMode.value = data.matchMode;

      RetrieveHelper.highLightKeywords([searchValue.value], true);
    };

    // 处理匹配模式更新
    const handleMatchModeUpdate = (mode: any) => {
      matchMode.value = mode;
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

    RetrieveHelper.on(RetrieveEvent.SEARCH_VALUE_CHANGE, () => {
      resetGrepRequestResult();
      requestGrepList();
    });

    RetrieveHelper.on(RetrieveEvent.SEARCHING_CHANGE, (value: boolean) => {
      if (!value) {
        resetGrepRequestResult();
        setDefaultFieldValue();
        requestGrepList();
      }
    });

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
    });

    onBeforeUnmount(() => {
      resetGrepRequestResult();

      RetrieveHelper.destroyMarkInstance();
      RetrieveHelper.off(RetrieveEvent.SEARCH_VALUE_CHANGE);
      RetrieveHelper.off(RetrieveEvent.SEARCHING_CHANGE);
    });

    return () => (
      <div class='grep-view'>
        <GrepCli
          search-count={totalMatches.value}
          search-value={searchValue.value}
          field-value={field.value}
          on-search-change={handleSearchUpdate}
          on-match-mode={handleMatchModeUpdate}
          on-grep-enter={handleGrepEnter}
          on-field-change={handleFieldChange}
        />
        <GrepCliResult
          fieldName={field.value}
          grepRequestResult={grepRequestResult.value}
          on-params-change={handleParamsChange}
          on-load-more={handleLoadMore}
        />
      </div>
    );
  },
});
