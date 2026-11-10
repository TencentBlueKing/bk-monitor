import { computed, getCurrentScope, onScopeDispose, ref, watch } from 'vue';
import { ServicesInstance, type ApplicationServices } from '@/platform/services';
import { ConditionOperator } from '@/app/state/condition-operator';
import type { ConsitionItem } from '@/app/state/store.type';

type FrontCondition = ReturnType<ConditionOperator['formatApiOperatorToFront']>;
export interface HistoryQueryParams {
  keyword?: string;
  addition: (ConsitionItem | FrontCondition)[];
  ip_chooser?: unknown;
  search_mode?: string;
  scene_filter_values?: unknown;
  table_id_conditions?: unknown;
}
export interface QueryHistoryRecord {
  id: string | number;
  query_string: string;
  created_at: string;
  search_mode?: string;
  params: HistoryQueryParams;
}
type ApiHistoryRecord = Omit<QueryHistoryRecord, 'params'> & {
  params: Omit<HistoryQueryParams, 'addition'> & { addition: ConsitionItem[] };
};
export interface HistoryContext {
  isSceneMode: boolean;
  isUnionSearch: boolean;
  indexId: string | number;
  unionIndexList: (string | number)[];
  retrieveParams: Record<string, unknown>;
}
type HistoryServices = {
  retrieve: Pick<ApplicationServices['retrieve'], 'getSearchHistory' | 'getSceneSearchHistory'>;
  unionSearch: Pick<ApplicationServices['unionSearch'], 'unionSearchHistory'>;
};

/** V2 query history semantics, with popup ownership and stale-response cleanup. */
export function useQueryHistory(
  context: () => HistoryContext,
  change: (params: HistoryQueryParams) => void,
  services: HistoryServices = ServicesInstance,
) {
  const visible = ref(false);
  const historyLoading = ref(false);
  const historyRecords = ref<QueryHistoryRecord[]>([]);
  const searchInput = ref('');
  const bookmarkPopRefsShow = ref(false);
  let generation = 0;
  const filterHistoryRecords = computed(() => {
    if (!searchInput.value.trim()) return historyRecords.value;
    const searchTerm = searchInput.value.toLowerCase();
    return historyRecords.value.filter((item) => item.query_string?.toLowerCase().includes(searchTerm));
  });
  function reset() {
    generation++;
    historyLoading.value = false;
    historyRecords.value = [];
    visible.value = false;
    bookmarkPopRefsShow.value = false;
  }
  async function requestSearchHistory() {
    const request = ++generation;
    historyLoading.value = true;
    const current = context();
    try {
      let response: { data: ApiHistoryRecord[] };
      if (current.isSceneMode) {
        const { space_uid, table_id_conditions, scene_filter_values } = current.retrieveParams;
        response = await services.retrieve.getSceneSearchHistory({
          data: { space_uid, table_id_conditions, scene_filter_values },
        });
      } else if (current.isUnionSearch) {
        response = await services.unionSearch.unionSearchHistory({ params: { index_set_ids: current.unionIndexList } });
      } else {
        response = await services.retrieve.getSearchHistory({ params: { index_set_id: current.indexId } });
      }
      if (request !== generation) return;
      historyRecords.value = response.data
        .filter((item) => item.query_string !== '*')
        .map((item) => ({
          ...item,
          params: {
            ...item.params,
            addition: item.params.addition.map((condition) =>
              new ConditionOperator(condition).formatApiOperatorToFront(),
            ),
          },
        }));
    } catch {
      // The shared HTTP client retains V2's request error feedback.
    } finally {
      if (request === generation) historyLoading.value = false;
    }
  }
  function handleVisibleChange(next: boolean) {
    if (!next && bookmarkPopRefsShow.value) return;
    if (next) {
      if (visible.value) return;
      visible.value = true;
      void requestSearchHistory();
    } else reset();
  }
  function handleClickHistory(item: QueryHistoryRecord) {
    const {
      keyword,
      addition,
      ip_chooser,
      search_mode = item.search_mode,
      scene_filter_values,
      table_id_conditions,
    } = item.params;
    change({ keyword, addition, ip_chooser, search_mode, scene_filter_values, table_id_conditions });
    reset();
  }
  watch(context, reset, { deep: true });
  if (getCurrentScope()) onScopeDispose(reset);
  return {
    visible,
    historyLoading,
    historyRecords,
    searchInput,
    filterHistoryRecords,
    bookmarkPopRefsShow,
    handleVisibleChange,
    handleClickHistory,
    requestSearchHistory,
  };
}
