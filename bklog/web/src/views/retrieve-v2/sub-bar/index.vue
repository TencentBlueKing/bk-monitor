<script setup>
  import { ref, computed } from 'vue';

  import FieldSetting from '@/global/field-setting.vue';
  import VersionSwitch from '@/global/version-switch.vue';
  import useStore from '@/hooks/use-store';
  import { ConditionOperator } from '@/store/condition-operator';
  import { isEqual } from 'lodash';
  import { useRoute, useRouter } from 'vue-router/composables';
  import { RetrieveUrlResolver } from '@/store/url-resolver';

  import SelectIndexSet from '../condition-comp/select-index-set.tsx';
  import { getInputQueryIpSelectItem } from '../search-bar/const.common';
  import QueryHistory from '../search-bar/query-history';
  import TimeSetting from '../search-bar/time-setting';
  import ClusterSetting from '../setting-modal/index.vue';
  import RetrieveSetting from './retrieve-setting.vue';
  import { bus } from '@/common/bus';

  const props = defineProps({
    showFavorites: {
      type: Boolean,
      default: true,
    },
  });
  const route = useRoute();
  const router = useRouter();
  const store = useStore();
  const isShowClusterSetting = ref(false);
  const indexSetParams = computed(() => store.state.indexItem);
  // 如果不是采集下发和自定义上报则不展示
  const hasCollectorConfigId = computed(() => {
    const indexSetList = store.state.retrieve.indexSetList;
    const indexSetId = route.params?.indexId;
    const currentIndexSet = indexSetList.find(item => item.index_set_id == indexSetId);
    return currentIndexSet?.collector_config_id;
  });

  const isExternal = computed(() => store.state.isExternal);

  const isFieldSettingShow = computed(() => {
    return !store.getters.isUnionSearch && !isExternal.value;
  });

  const setRouteParams = (ids, isUnionIndex) => {
    if (isUnionIndex) {
      router.replace({
        params: {
          ...route.params,
          indexId: undefined,
        },
        query: {
          ...route.query,
          unionList: JSON.stringify(ids),
          clusterParams: undefined,
        },
      });

      return;
    }

    router.replace({
      params: {
        ...route.params,
        indexId: ids[0],
      },
      query: { ...route.query, unionList: undefined, clusterParams: undefined },
    });
  };

  const setRouteQuery = () => {
    const query = { ...route.query };
    const { keyword, addition, ip_chooser, search_mode, begin, size } = store.getters.retrieveParams;
    const resolver = new RetrieveUrlResolver({
      keyword,
      addition,
      ip_chooser,
      search_mode,
      begin,
      size,
    });

    Object.assign(query, resolver.resolveParamsToUrl());

    router.replace({
      query,
    });
  };

  const handleIndexSetSelected = async payload => {
    if (!isEqual(indexSetParams.value.ids, payload.ids) || indexSetParams.value.isUnionIndex !== payload.isUnionIndex) {
      setRouteParams(payload.ids, payload.isUnionIndex);
      store.commit('updateUnionIndexList', payload.isUnionIndex ? payload.ids ?? [] : []);
      store.commit('retrieve/updateChartKey');

      store.commit('updateIndexItem', payload);
      if (!payload.isUnionIndex) {
        store.commit('updateIndexId', payload.ids[0]);
      }

      store.commit('updateSqlQueryFieldList', []);
      store.commit('updateIndexSetQueryResult', []);
      store.dispatch('requestIndexSetFieldInfo').then(() => {
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

    setRouteQuery();
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
      <!-- <SelectIndexSet
        style="min-width: 500px"
        :popover-options="{ offset: '-6,10' }"
        @selected="handleIndexSetSelected"
      ></SelectIndexSet> -->
      <div style="min-width: 500px; height: 32px; background-color: #f0f1f5">采集项选择器</div>
      <QueryHistory @change="updateSearchParam"></QueryHistory>
    </div>
    <div class="box-right-option">
      <TimeSetting class="border-solo"></TimeSetting>
      <FieldSetting
        v-if="isFieldSettingShow && store.state.spaceUid && hasCollectorConfigId"
        class="border-solo"
      />
      <ClusterSetting
        class="border-solo"
        v-model="isShowClusterSetting"
      ></ClusterSetting>
      <div
        v-if="!isExternal"
        class="more-setting"
      >
        <RetrieveSetting :is-show-cluster-setting.sync="isShowClusterSetting"></RetrieveSetting>
      </div>
      <VersionSwitch
        style="border-left: 1px solid #eaebf0"
        version="v2"
      />
    </div>
  </div>
</template>
<style lang="scss">
  @import './index.scss';

  .box-right-option {
    .border-solo {
      border-right: 1px solid #eaebf0;
    }
  }
</style>
