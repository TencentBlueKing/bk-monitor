import { computed } from 'vue';
import useStore from './use-store';

export default () => {
  const store = useStore();

  const alias_settings = computed(() =>
    // eslint-disable-next-line @typescript-eslint/prefer-optional-chain
    (store.state.indexFieldInfo?.fields ?? {})
      .filter(f => f.query_alias)
      .map(f => ({
        field_name: f.field_name,
        query_alias: f.query_alias,
        path_type: f.field_type,
      })),
  );

  const sort_list = computed(() =>
    store.state.localSort ? store.getters.retrieveParams.sort_list : store.getters.custom_sort_list,
  );

  return {
    alias_settings,
    sort_list,
  };
};
