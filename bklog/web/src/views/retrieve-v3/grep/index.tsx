import { defineComponent, onBeforeUnmount, onMounted, onUnmounted, ref } from 'vue';
import GrepCli from './grep-cli';
import GrepCliResult from './grep-cli-result';
import RetrieveHelper, { RetrieveEvent } from '../../retrieve-helper';
import RequestPool from '@/store/request-pool';
import { axiosInstance } from '@/api';
import useStore from '@/hooks/use-store';
import { readBlobRespToJson } from '@/common/util';
import { messageError } from '@/common/bkmagic';
import { debounce } from 'lodash';
import './grep-cli.scss';

export default defineComponent({
  name: 'GrepView',
  components: {
    GrepCli,
    GrepCliResult,
  },
  setup() {
    const searchValue = ref('');
    const field = ref(null);
    const offset = ref(0);
    const hasMoreList = ref(true);
    const isLoading = ref(false);
    const matchMode = ref({
      caseSensitive: false,
      regexMode: false,
      wordMatch: false,
    });

    const totalMatches = ref(0);
    const list = ref([]);
    const grepQuery = ref('');

    const store = useStore();

    const requestGrepList = () => {
      if (!hasMoreList.value) {
        return;
      }

      isLoading.value = true;
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
          begin: offset.value,
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
                list.value.push(...data.list);
                hasMoreList.value = data.list.length > 0;
                setTimeout(() => {
                  RetrieveHelper.highLightKeywords([searchValue.value], true);
                });
                return;
              }
              messageError(message);
            });
          }

          isLoading.value = false;
        })
        .catch((err: any) => {
          if (err.message === 'canceled') {
            return;
          }
          messageError(err.message ?? err);
        })
        .finally(() => {
          isLoading.value = false;
        });
    };

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
      offset.value = 0;
      hasMoreList.value = true;
      list.value.splice(0, list.value.length);

      requestGrepList();
    };

    // 处理grep enter
    const handleGrepEnter = (value: string) => {
      grepQuery.value = value;
      offset.value = 0;
      list.value.splice(0, list.value.length);

      if (field.value === '') {
        return;
      }

      requestGrepList();
    };

    const handleLoadMore = () => {
      if (field.value === '') {
        return;
      }

      offset.value += 100;
      requestGrepList();
    };

    RetrieveHelper.on(RetrieveEvent.SEARCH_VALUE_CHANGE, () => {
      offset.value = 0;
      hasMoreList.value = true;
      list.value.splice(0, list.value.length);

      requestGrepList();
    });

    const handleParamsChange = () => {
      offset.value = 0;
      hasMoreList.value = true;
      list.value.splice(0, list.value.length);

      requestGrepList();
    };

    onMounted(() => {
      offset.value = 0;
      hasMoreList.value = true;
      RetrieveHelper.setMarkInstance();
    });

    onBeforeUnmount(() => {
      offset.value = 0;
      hasMoreList.value = true;
      RetrieveHelper.destroyMarkInstance();
    });

    return () => (
      <div class='grep-view'>
        <GrepCli
          search-count={totalMatches.value}
          on-search-change={handleSearchUpdate}
          on-match-mode={handleMatchModeUpdate}
          on-grep-enter={handleGrepEnter}
          on-field-change={handleFieldChange}
        />
        <GrepCliResult
          isLoading={isLoading.value}
          fieldName={field.value}
          list={list.value}
          on-params-change={handleParamsChange}
          on-load-more={handleLoadMore}
        />
      </div>
    );
  },
});
