<script setup>
  import { ref, computed } from 'vue';

  import VersionSwitch from '@/global/version-switch.vue';
  import useStore from '@/hooks/use-store';
  import { ConditionOperator } from '@/store/condition-operator';
  import { isEqual } from 'lodash';

  import SelectIndexSet from '../condition-comp/select-index-set.tsx';
  import { getInputQueryIpSelectItem } from '../search-bar/const.common';
  import QueryHistory from '../search-bar/query-history';
  import TimeSetting from '../search-bar/time-setting';
  import ClusterSetting from '../setting-modal/index.vue';
  import RetrieveSetting from './retrieve-setting.vue';

  const props = defineProps({
    showFavorites: {
      type: Boolean,
      default: true,
    },
  });

  const store = useStore();
  const isShowClusterSetting = ref(false);
  const indexSetParams = computed(() => store.state.indexItem);

  const handleIndexSetSelected = payload => {
    if (!isEqual(indexSetParams.value.ids, payload.ids) || indexSetParams.value.isUnionIndex !== payload.isUnionIndex) {
      store.commit('updateUnionIndexList', payload.isUnionIndex ? (payload.ids ?? []) : []);
      store.dispatch('requestIndexSetItemChanged', payload ?? {}).then(() => {
        store.commit('retrieve/updateChartKey');
        store.dispatch('requestIndexSetQuery');
      });
    }
  };

  const updateSearchParam = payload => {
    const { keyword, addition, ip_chooser, search_mode } = payload;
    const foramtAddition = (addition ?? []).map(item => {
      const instance = new ConditionOperator(item);
      return instance.formatApiOperatorToFront();
    });

    if (Object.keys(ip_chooser).length) {
      foramtAddition.unshift(getInputQueryIpSelectItem(ip_chooser));
    }

    store.commit('updateIndexItemParams', {
      keyword,
      addition: foramtAddition,
      ip_chooser,
      begin: 0,
      search_mode,
    });

    setTimeout(() => {
      store.dispatch('requestIndexSetQuery');
    });
  };
</script>
<template>
  <div class="subbar-container">
    <div
      :style="{ 'margin-left': props.showFavorites ? '4px' : '0' }"
      class="box-biz-select"
    >
      <SelectIndexSet
        style="min-width: 500px"
        :popover-options="{ offset: '-6,10' }"
        @selected="handleIndexSetSelected"
      ></SelectIndexSet>
      <QueryHistory @change="updateSearchParam"></QueryHistory>
    </div>
    <div class="box-right-option">
      <VersionSwitch version="v2" />
      <TimeSetting></TimeSetting>
      <ClusterSetting v-model="isShowClusterSetting"></ClusterSetting>
      <div class="more-setting">
        <RetrieveSetting :is-show-cluster-setting.sync="isShowClusterSetting"></RetrieveSetting>
      </div>
    </div>
  </div>
</template>
<style lang="scss">
  @import './index.scss';
</style>
