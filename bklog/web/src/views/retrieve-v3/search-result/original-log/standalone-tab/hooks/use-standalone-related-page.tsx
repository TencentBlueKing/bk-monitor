import { computed, ref } from 'vue';

import useLocale from '@/hooks/use-locale';
import useRoute from '@/hooks/use-route';
import useRouter from '@/hooks/use-router';
import useStore from '@/hooks/use-store';

import { runStandaloneRelatedSearch, type StandaloneSearchResult } from '../search-runner';

const toNumber = (value: any, fallback = 0) => {
  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? numberValue : fallback;
};

const parseArray = (value: any, fallback: any[] = []) => {
  if (Array.isArray(value)) return value;
  try {
    const parsed = JSON.parse(String(value || '[]'));
    return Array.isArray(parsed) ? parsed : fallback;
  } catch {
    return fallback;
  }
};

const normalizeSearchList = (data: Record<string, any>) => {
  const originList = Array.isArray(data?.origin_log_list) ? data.origin_log_list : [];
  const renderList = Array.isArray(data?.list) ? data.list : originList;
  return {
    originList,
    renderList,
  };
};

export const useStandaloneRelatedPage = () => {
  const route = useRoute();
  const router = useRouter();
  const store = useStore();
  const { t } = useLocale();

  const loading = ref(true);
  const loadingText = ref('Init');
  const error = ref('');
  const result = ref<StandaloneSearchResult | null>(null);
  const targetFields = ref<string[]>([]);
  const targetRow = ref<Record<string, any>>({});
  const pageReady = ref(false);

  const indexSetId = computed(() => result.value?.payload.indexSetId || 0);
  const rowIndex = computed(() => result.value?.rowIndex || 0);
  const retrieveParams = computed(() => result.value?.retrieveParams || {});

  const initStoreState = async (searchResult: StandaloneSearchResult) => {
    loadingText.value = 'Load Fields';
    const { payload, data } = searchResult;
    const { originList, renderList } = normalizeSearchList(data);
    const total = data?.total?.toNumber?.() ?? data?.total ?? originList.length;

    store.commit('updateState', {
      indexId: payload.indexSetId,
      bkBizId: toNumber(payload.query.bk_biz_id, store.getters.bkBizId),
      spaceUid: payload.routeQuery.spaceUid || payload.routeQuery.space_uid || store.getters.spaceUid,
    });

    store.commit('updateIndexItem', {
      ids: [payload.indexSetId],
      start_time: payload.query.start_time,
      end_time: payload.query.end_time,
      begin: payload.query.begin || 0,
      size: payload.query.size || 50,
    });

    await store.dispatch('requestIndexSetFieldInfo');

    store.commit('updateIndexSetQueryResult', {
      ...data,
      list: renderList,
      origin_log_list: originList,
      total,
      is_loading: false,
      is_error: false,
      exception_msg: '',
    });
  };

  const init = async () => {
    loading.value = true;
    loadingText.value = 'Resolve URL';
    error.value = '';
    pageReady.value = false;
    try {
      loadingText.value = 'Run search';
      const searchResult = await runStandaloneRelatedSearch(route.query as Record<string, any>);
      result.value = searchResult;
      targetRow.value = searchResult.rowData;
      targetFields.value = parseArray(route.query.targetFields);
      await initStoreState(searchResult);
      loadingText.value = 'Render logs';
      pageReady.value = true;
    } catch (e) {
      error.value = e?.message || String(e);
    } finally {
      loading.value = false;
    }
  };

  const renderError = () => (
    <bk-exception scene='part' type='500'>
      <div>{error.value}</div>
      <bk-button theme='primary' onClick={() => router.replace({ name: 'retrieve' })}>{t('返回检索')}</bk-button>
    </bk-exception>
  );

  return {
    t,
    route,
    router,
    store,
    loading,
    loadingText,
    error,
    result,
    pageReady,
    indexSetId,
    rowIndex,
    targetRow,
    targetFields,
    retrieveParams,
    init,
    renderError,
  };
};
