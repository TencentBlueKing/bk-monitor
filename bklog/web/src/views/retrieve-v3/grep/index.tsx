import { defineComponent, onBeforeUnmount, onMounted, onUnmounted, ref } from 'vue';
import GrepCli from './grep-cli';
import GrepCliResult from './grep-cli-result';
import RetrieveHelper, { RetrieveEvent } from '../../retrieve-helper';
import RequestPool from '@/store/request-pool';
import { axiosInstance } from '@/api';
import useStore from '@/hooks/use-store';
import { readBlobRespToJson } from '@/common/util';
import { messageError } from '@/common/bkmagic';
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
    const total = ref(0);
    const isLoading = ref(false);
    const matchMode = ref({
      caseSensitive: false,
      regexMode: false,
      wordMatch: false,
    });
    const currentIndex = ref(0);
    const totalMatches = ref(0);
    const list = ref([]);

    const grepQuery = ref('');

    const store = useStore();

    const requestGrepList = () => {
      if (total.value > 0 && list.value.length >= total.value) {
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
                total.value = data.total.toNumber();
                return;
              }
              messageError(message);
            });
          }
        })
        .catch((err: any) => {
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
      if (data.currentIndex) {
        currentIndex.value = data.currentIndex;
      }
    };

    // 处理匹配模式更新
    const handleMatchModeUpdate = (mode: any) => {
      matchMode.value = mode;
    };

    // 处理总匹配数更新
    const handleTotalMatchesUpdate = (total: number) => {
      totalMatches.value = total;
    };

    const handleFieldChange = (v: string) => {
      console.log('handleFieldChange', v);
      field.value = v;
    };

    // 处理grep enter
    const handleGrepEnter = (value: string) => {
      grepQuery.value = value;
      offset.value = 0;
      list.value.splice(0, list.value.length);

      if (grepQuery.value === '' || field.value === '') {
        return;
      }

      requestGrepList();
    };

    const handleLoadMore = () => {
      if (grepQuery.value === '' || field.value === '') {
        return;
      }

      offset.value += 100;
      requestGrepList();
    };

    RetrieveHelper.on(RetrieveEvent.SEARCH_VALUE_CHANGE, () => {
      offset.value = 0;
      total.value = 0;
      list.value.splice(0, list.value.length);

      requestGrepList();
    });

    const handleParamsChange = () => {
      offset.value = 0;
      total.value = 0;
      list.value.splice(0, list.value.length);

      requestGrepList();
    };

    onMounted(() => {
      offset.value = 0;
      total.value = 0;
    });

    onBeforeUnmount(() => {
      offset.value = 0;
      total.value = 0;
    });

    return () => (
      <div class='grep-view'>
        <GrepCli
          on-search-change={handleSearchUpdate}
          on-match-mode={handleMatchModeUpdate}
          on-grep-enter={handleGrepEnter}
          on-field-change={handleFieldChange}
        />
        <GrepCliResult
          isLoading={isLoading.value}
          searchValue={searchValue.value}
          fieldName={field.value}
          list={list.value}
          matchMode={matchMode.value}
          onUpdate:total-matches={handleTotalMatchesUpdate}
          on-params-change={handleParamsChange}
          on-load-more={handleLoadMore}
        />
      </div>
    );
  },
});
