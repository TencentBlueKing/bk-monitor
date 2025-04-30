<script setup>
  import { ref, computed } from 'vue';
  import { bkMessage } from 'bk-magic-vue';

  import FieldSetting from '@/global/field-setting.vue';
  import VersionSwitch from '@/global/version-switch.vue';
  import useStore from '@/hooks/use-store';
  import { ConditionOperator } from '@/store/condition-operator';
  import { RetrieveUrlResolver } from '@/store/url-resolver';
  import { isEqual } from 'lodash';
  import { useRoute, useRouter } from 'vue-router/composables';

  import SelectIndexSet from '../condition-comp/select-index-set.tsx';
  import IndexSetChoice from '../components/index-set-choice/index';
  import { getInputQueryIpSelectItem } from '../search-bar/const.common';
  import QueryHistory from './query-history';
  import TimeSetting from './time-setting';
  import ClusterSetting from '../setting-modal/index.vue';
  import BarGlobalSetting from './bar-global-setting.tsx';
  import MoreSetting from './more-setting.vue';
  import WarningSetting from './warning-setting.vue';
  import RetrieveHelper, { RetrieveEvent } from '../../retrieve-helper';

  const props = defineProps({
    showFavorites: {
      type: Boolean,
      default: true,
    },
  });
  const route = useRoute();
  const router = useRouter();
  const store = useStore();

  const fieldSettingRef = ref(null);

  const isShowClusterSetting = ref(false);
  const indexSetParams = computed(() => store.state.indexItem);

  // 索引集列表
  const indexSetList = computed(() => store.state.retrieve.indexSetList);

  // 索引集选择结果
  const indexSetValue = computed(() => store.state.indexItem.ids);

  // 索引集类型
  const indexSetType = computed(() => (store.state.indexItem.isUnionIndex ? 'union' : 'single'));

  // 索引集当前激活Tab
  const indexSetTab = computed(() => {
    if (store.state.storage.indexSetActiveTab) {
      return store.state.storage.indexSetActiveTab;
    }

    return indexSetType.value;
  });

  const spaceUid = computed(() => store.state.spaceUid);

  const textDir = computed(() => {
    const textEllipsisDir = store.state.storage.textEllipsisDir;
    return textEllipsisDir === 'start' ? 'rtl' : 'ltr';
  });

  // 如果不是采集下发和自定义上报则不展示
  const hasCollectorConfigId = computed(() => {
    const indexSetId = route.params?.indexId;
    const currentIndexSet = indexSetList.value.find(item => item.index_set_id == indexSetId);
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
      RetrieveHelper.setIndexsetId(payload.ids, payload.isUnionIndex ? 'union' : 'single');

      setRouteParams(payload.ids, payload.isUnionIndex);
      store.commit('updateUnionIndexList', payload.isUnionIndex ? payload.ids ?? [] : []);
      store.commit('retrieve/updateChartKey');

      store.commit('updateIndexItem', payload);
      if (!payload.isUnionIndex) {
        store.commit('updateIndexId', payload.ids[0]);
      }

      store.commit('updateSqlQueryFieldList', []);
      store.commit('updateIndexSetQueryResult', {
        origin_log_list: [],
        list: [],
      });
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
      RetrieveHelper.fire(RetrieveEvent.TREND_GRAPH_SEARCH);
    });
  };

  const handleActiveTypeChange = type => {
    store.commit('updateStorage', { indexSetActiveTab: type });

    if (['union', 'single'].includes(type)) {
      RetrieveHelper.setIndexsetId(indexSetParams.value.ids, type);
      store.commit('updateIndexItem', {
        isUnionIndex: type === 'union',
      });
    }
  };

  const handleIndexSetValueChange = values => {
    handleIndexSetSelected({ ids: values, isUnionIndex: indexSetType.value === 'union' });
  };

  /**
   * @description: 打开 索引集配置 抽屉页
   */
  function handleIndexConfigSliderOpen() {
    if (isFieldSettingShow.value && store.state.spaceUid && hasCollectorConfigId.value) {
      fieldSettingRef.value?.handleShowSlider?.();
    } else {
      bkMessage({
        theme: 'primary',
        message: '第三方ES、计算平台索引集类型不支持自定义分词',
      });
    }
  }
</script>
<template>
  <div class="subbar-container">
    <div
      :style="{ 'margin-left': props.showFavorites ? '4px' : '0' }"
      class="box-biz-select"
    >
      <IndexSetChoice
        :index-set-list="indexSetList"
        :index-set-value="indexSetValue"
        :active-type="indexSetType"
        :active-tab="indexSetTab"
        :text-dir="textDir"
        :spaceUid="spaceUid"
        width="100%"
        @value-change="handleIndexSetValueChange"
        @type-change="handleActiveTypeChange"
      ></IndexSetChoice>
      <QueryHistory @change="updateSearchParam"></QueryHistory>
    </div>

    <div class="box-right-option">
      <TimeSetting class="custom-border-right"></TimeSetting>
      <FieldSetting
        v-if="isFieldSettingShow && store.state.spaceUid && hasCollectorConfigId"
        ref="fieldSettingRef"
        class="custom-border-right"
      />
      <WarningSetting
        v-if="!isExternal"
        class="custom-border-right"
      ></WarningSetting>
      <ClusterSetting
        class="custom-border-right"
        v-model="isShowClusterSetting"
      ></ClusterSetting>
      <!-- <div
        v-if="!isExternal"
      >
        <RetrieveSetting :is-show-cluster-setting.sync="isShowClusterSetting"></RetrieveSetting>
      </div> -->
      <BarGlobalSetting
        class="custom-border-right"
        @show-index-config-slider="handleIndexConfigSliderOpen"
      ></BarGlobalSetting>
      <div
        v-if="!isExternal"
        class="more-setting"
      >
        <MoreSetting :is-show-cluster-setting.sync="isShowClusterSetting"></MoreSetting>
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
    .more-setting {
      height: 100%;

      &:hover {
        background: #f5f7fa;
      }
    }

    .custom-border-right {
      display: flex;
      align-items: center;
      height: 100%;
      line-height: 20px;
      border-right: 1px solid #eaebf0;

      &:hover {
        background: #f5f7fa;
      }

      &.query-params-wrap {
        .__bk_date_picker__ {
          color: #4d4f56;

          .date-icon {
            color: #4d4f56;
          }

          .date-content {
            padding: 0;

            & > svg {
              fill: #4d4f56;
            }
          }
        }
      }
    }
  }
</style>
