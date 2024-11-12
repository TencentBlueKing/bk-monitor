<script setup>
  import { ref, computed } from 'vue';

  import VersionSwitch from '@/global/version-switch.vue';
  import useStore from '@/hooks/use-store';
  import { ConditionOperator } from '@/store/condition-operator';
  import FieldSetting from '@/global/field-setting.vue';
  import { isEqual } from 'lodash';
  import { useRoute } from 'vue-router/composables';
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
  const route = useRoute();
  const store = useStore();
  const isShowClusterSetting = ref(false);
  const indexSetParams = computed(() => store.state.indexItem);
  // 如果不是采集下发和自定义上报则不展示
  const hasCollectorConfigId = computed(() => {
    const indexSetList = store.state.retrieve.indexSetList;
    const indexSetId = route.params?.indexId;
    const currentIndexSet = indexSetList.find(item => item.index_set_id == indexSetId);
    return  currentIndexSet && currentIndexSet.collector_config_id
  });
  const FieldSettingShow = ref(true);
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
  // 监听单选还是多选,多选不展示字段配置
  const updateBtnSelect = payload => {
    if(payload === 'single'){
      FieldSettingShow.value = true
    }else{
      FieldSettingShow.value = false
    }
  }
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
        @change="updateBtnSelect"
      ></SelectIndexSet>
      <QueryHistory @change="updateSearchParam"></QueryHistory>
    </div>
    <div class="box-right-option">
      <VersionSwitch version="v2" />
      <FieldSetting v-show="FieldSettingShow && store.state.spaceUid && hasCollectorConfigId" />
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
