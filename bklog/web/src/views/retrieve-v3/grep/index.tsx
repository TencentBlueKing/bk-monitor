import { defineComponent, onMounted, onUnmounted, ref } from 'vue';
import GrepCli from './grep-cli';
import GrepCliResult from './grep-cli-result';
import RetrieveHelper from '../../retrieve-helper';
import RequestPool from '@/store/request-pool';
import { axiosInstance } from '@/api';
import './grep-cli.scss';
import useStore from '@/hooks/use-store';
import { readBlobRespToJson } from '@/common/util';
import { messageError } from '@/common/bkmagic';

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
    const matchMode = ref({
      caseSensitive: false,
      regexMode: false,
      wordMatch: false,
    });
    const currentIndex = ref(0);
    const totalMatches = ref(0);
    const store = useStore();

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
      field.value = v;
    };

    // 处理grep enter
    const handleGrepEnter = (value: string) => {
      console.log('handleGrepEnter', value);
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
          grep_query: value,
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
              console.log('data', data);
            });
          }
        })
        .catch((err: any) => {
          messageError(err.message ?? err);
        });
    };

    onMounted(() => {
      RetrieveHelper.setMarkInstance();
      offset.value = 0;
    });

    onUnmounted(() => {
      offset.value = 0;
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
          searchValue={searchValue.value}
          matchMode={matchMode.value}
          currentIndex={currentIndex.value}
          onUpdate:total-matches={handleTotalMatchesUpdate}
        />
      </div>
    );
  },
});
