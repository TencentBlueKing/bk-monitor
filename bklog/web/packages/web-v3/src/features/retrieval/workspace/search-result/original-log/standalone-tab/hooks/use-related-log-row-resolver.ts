
import { useApplicationStore } from '@/app/state/domains/application-store';
import { type Ref } from 'vue';



import {
  getRelatedLogIndexSetId,
  getRelatedLogResolveOptions,
  resolveRelatedLogTargetRow,
} from './resolve-related-log-target-row';

export const useRelatedLogRowResolver = (options: { targetRow: Ref<Record<string, any>>; indexSetId: Ref<number> }) => {
  const store = useApplicationStore();

  const resolveByRowKey = async (rowKey?: string, fallbackRow?: Record<string, any>) => {
    if (!rowKey && (!fallbackRow || !Object.keys(fallbackRow).length)) {
      return false;
    }

    const resolved = await resolveRelatedLogTargetRow({
      rowKey,
      fallbackRow,
      ...getRelatedLogResolveOptions(store),
    });
    if (!resolved) {
      return false;
    }

    options.targetRow.value = resolved.row;
    options.indexSetId.value = getRelatedLogIndexSetId(resolved.fullRow, store);
    return !!options.indexSetId.value;
  };

  return {
    resolveByRowKey,
  };
};
