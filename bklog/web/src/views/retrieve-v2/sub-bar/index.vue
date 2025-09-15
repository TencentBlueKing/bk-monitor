<script setup>
  import { ref, computed } from 'vue';

  import useStore from '@/hooks/use-store';
  import { ConditionOperator } from '@/store/condition-operator';
  import { RetrieveUrlResolver } from '@/store/url-resolver';
  import { bkMessage } from 'bk-magic-vue';
  import { isEqual } from 'lodash-es';
  import { useRoute, useRouter } from 'vue-router/composables';

  import IndexSetChoice from '../components/index-set-choice/index';
  import { getInputQueryIpSelectItem } from '../search-bar/const.common';
  // #if MONITOR_APP !== 'trace'
  import QueryHistory from './query-history';
  // #else
  // #code const QueryHistory = () => null;
  // #endif
  // #if MONITOR_APP !== 'apm' && MONITOR_APP !== 'trace'
  import TimeSetting from './time-setting';
  import FieldSetting from '@/global/field-setting.vue';
  import VersionSwitch from '@/global/version-switch.vue';
  import ClusterSetting from '../setting-modal/index.vue';
  import BarGlobalSetting from './bar-global-setting.tsx';
  import MoreSetting from './more-setting.vue';
  import WarningSetting from './warning-setting.vue';
  // #else
  // #code const TimeSetting = () => null;
  // #code const FieldSetting = () => null;
  // #code const VersionSwitch = () => null;
  // #code const ClusterSetting = () => null;
  // #code const BarGlobalSetting = () => null;
  // #code const MoreSetting = () => null;
  // #code const WarningSetting = () => null;
  // #endif

  import * as authorityMap from '@/common/authority-map';
  import { BK_LOG_STORAGE } from '@/store/store.type';

  import RetrieveHelper, { RetrieveEvent } from '../../retrieve-helper';
  import ShareLink from './share-link.tsx';

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
    return store.state.storage[BK_LOG_STORAGE.INDEX_SET_ACTIVE_TAB] ?? indexSetType.value;
  });

  const spaceUid = computed(() => store.state.spaceUid);

  const textDir = computed(() => {
    const textEllipsisDir = store.state.storage[BK_LOG_STORAGE.TEXT_ELLIPSIS_DIR];
    return textEllipsisDir === 'start' ? 'rtl' : 'ltr';
  });

  /** 是否是监控组件 */
  const isMonitorComponent = window.__IS_MONITOR_COMPONENT__;
  const isMonitorTraceComponent = window.__IS_MONITOR_TRACE__;

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
    const queryTab = RetrieveHelper.routeQueryTabValueFix(indexSetParams.value.items[0], route.query.tab, isUnionIndex);
    const { search_mode, keyword, addition } = indexSetParams.value;
    if (isUnionIndex) {
      router.replace({
        // #if MONITOR_APP !== 'apm' && MONITOR_APP !== 'trace'
        params: {
          ...route.params,
          indexId: undefined,
        },
        // #endif
        query: {
          ...route.query,
          ...queryTab,
          // #if MONITOR_APP === 'apm' || MONITOR_APP === 'trace'
          indexId: undefined,
          // #endif
          search_mode,
          keyword,
          addition: JSON.stringify(addition),
          unionList: JSON.stringify(ids),
          clusterParams: undefined,
          [BK_LOG_STORAGE.HISTORY_ID]: store.state.storage[BK_LOG_STORAGE.HISTORY_ID],
          [BK_LOG_STORAGE.FAVORITE_ID]: store.state.storage[BK_LOG_STORAGE.FAVORITE_ID],
        },
      });

      return;
    }

    router.replace({
      // #if MONITOR_APP !== 'apm' && MONITOR_APP !== 'trace'
      params: {
        ...route.params,
        indexId: ids[0],
      },
      // #endif
      query: {
        ...route.query,
        ...queryTab,
        // #if MONITOR_APP === 'apm' || MONITOR_APP === 'trace'
        indexId: ids[0],
        // #endif
        search_mode,
        keyword,
        addition: JSON.stringify(addition),
        unionList: undefined,
        clusterParams: undefined,
        [BK_LOG_STORAGE.HISTORY_ID]: store.state.storage[BK_LOG_STORAGE.HISTORY_ID],
        [BK_LOG_STORAGE.FAVORITE_ID]: store.state.storage[BK_LOG_STORAGE.FAVORITE_ID],
      },
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
      [BK_LOG_STORAGE.HISTORY_ID]: store.state.storage[BK_LOG_STORAGE.HISTORY_ID],
      [BK_LOG_STORAGE.FAVORITE_ID]: store.state.storage[BK_LOG_STORAGE.FAVORITE_ID],
    });

    Object.assign(query, resolver.resolveParamsToUrl());

    router.replace({
      query,
    });
  };

  const handleIndexSetSelected = async payload => {
    if (!isEqual(indexSetParams.value.ids, payload.ids) || indexSetParams.value.isUnionIndex !== payload.isUnionIndex) {
      /** 索引集默认条件 */
      let indexSetDefaultCondition = {};
      /** 只选择一个索引集且ui模式和sql模式都没有值, 取索引集默认条件 */
      if (payload.items.length === 1 && !indexSetParams.value.addition.length && !indexSetParams.value.keyword) {
        if (payload.items[0]?.query_string) {
          indexSetDefaultCondition = {
            keyword: payload.items[0].query_string,
            search_mode: 'sql',
            addition: [],
          };
        } else if (payload.items[0]?.addition) {
          indexSetDefaultCondition = {
            addition: [...payload.items[0].addition],
            search_mode: 'ui',
            keyword: '',
          };
        }
        if (indexSetDefaultCondition.search_mode) {
          store.commit('updateStorage', {
            [BK_LOG_STORAGE.SEARCH_TYPE]: ['ui', 'sql'].indexOf(indexSetDefaultCondition.search_mode),
          });
        }
      }

      RetrieveHelper.setIndexsetId(payload.ids, payload.isUnionIndex ? 'union' : 'single', false);
      store.commit('updateUnionIndexList', payload.isUnionIndex ? payload.ids ?? [] : []);
      store.commit('updateIndexItem', { ...payload, ...indexSetDefaultCondition });

      if (!payload.isUnionIndex) {
        store.commit('updateState', { 'indexId': payload.ids[0]});
      }

      store.commit('updateSqlQueryFieldList', []);
      store.commit('updateIndexSetQueryResult', {
        origin_log_list: [],
        list: [],
        exception_msg: '',
        is_error: false,
      });

      store.dispatch('requestIndexSetFieldInfo').then(resp => {
        RetrieveHelper.fire(RetrieveEvent.TREND_GRAPH_SEARCH);

        if (resp?.data?.fields?.length) {
          store.dispatch('requestIndexSetQuery');
        }

        if (!resp?.data?.fields?.length) {
          store.commit('updateIndexSetQueryResult', {
            is_error: true,
            exception_msg: 'index-set-field-not-found',
          });
        }
      });

      setRouteParams(payload.ids, payload.isUnionIndex);
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

    const mode = ['ui', 'sql'].includes(search_mode) ? search_mode : 'ui';

    store.commit('updateIndexItemParams', {
      keyword,
      addition: foramtAddition,
      ip_chooser,
      begin: 0,
      search_mode: mode,
    });

    store.commit('updateStorage', { [BK_LOG_STORAGE.SEARCH_TYPE]: ['ui', 'sql'].indexOf(mode) });

    setRouteQuery();
    setTimeout(() => {
      store.dispatch('requestIndexSetQuery');
      RetrieveHelper.fire(RetrieveEvent.TREND_GRAPH_SEARCH);
    });
  };

  const handleActiveTypeChange = type => {
    const storage = { [BK_LOG_STORAGE.INDEX_SET_ACTIVE_TAB]: type };
    if (['union', 'single'].includes(type)) {
      Object.assign(storage, { [BK_LOG_STORAGE.FAVORITE_ID]: undefined, [BK_LOG_STORAGE.HISTORY_ID]: undefined });
      store.commit('updateIndexItem', {
        isUnionIndex: type === 'union',
      });
    }

    store.commit('updateStorage', storage);
  };

  const handleIndexSetValueChange = (values, type, id) => {
    const storage = {
      [BK_LOG_STORAGE.LAST_INDEX_SET_ID]: {
        ...(store.state.storage[BK_LOG_STORAGE.LAST_INDEX_SET_ID] ?? {}),
        [spaceUid.value]: values,
      },
    };
    if (['single', 'union'].includes(type)) {
      store.commit('updateIndexItem', {
        isUnionIndex: type === 'union',
      });

      if (type === 'union') {
        store.commit('updateUnionIndexList', { updateIndexItem: false, list: store.state.indexItem.ids });
      }

      Object.assign(storage, {
        [BK_LOG_STORAGE.FAVORITE_ID]: undefined,
        [BK_LOG_STORAGE.HISTORY_ID]: undefined,
      });
    }

    if ('favorite' === indexSetTab.value) {
      Object.assign(storage, { [BK_LOG_STORAGE.FAVORITE_ID]: id, [BK_LOG_STORAGE.HISTORY_ID]: undefined });
    }

    if ('history' === indexSetTab.value) {
      Object.assign(storage, { [BK_LOG_STORAGE.FAVORITE_ID]: undefined, [BK_LOG_STORAGE.HISTORY_ID]: id });
    }

    store.commit('updateStorage', storage);
    const items = indexSetList.value.filter(item => (values ?? []).includes(item.index_set_id));
    handleIndexSetSelected({ ids: values, isUnionIndex: indexSetType.value === 'union', items });
  };

  const handleAuthRequest = item => {
    try {
      store
        .dispatch('getApplyData', {
          action_ids: [authorityMap.SEARCH_LOG_AUTH],
          resources: [
            {
              type: 'indices',
              id: item.index_set_id,
            },
          ],
        })
        .then(res => {
          window.open(res.data.apply_url);
        });
    } catch (err) {
      console.warn(err);
    }
  };

  /**
   * @description: 打开 索引集配置 抽屉页
   */
  function handleIndexConfigSliderOpen() {
    if (isFieldSettingShow.value) {
      RetrieveHelper.setAliasConfigOpen(true);
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
        width="100%"
        :active-tab="indexSetTab"
        :active-type="indexSetType"
        :index-set-list="indexSetList"
        :index-set-value="indexSetValue"
        :space-uid="spaceUid"
        :text-dir="textDir"
        @auth-request="handleAuthRequest"
        @type-change="handleActiveTypeChange"
        @value-change="handleIndexSetValueChange"
      ></IndexSetChoice>

      <QueryHistory
        v-if="!isMonitorTraceComponent"
        @change="updateSearchParam"
      ></QueryHistory>
    </div>

    <div
      v-if="!isMonitorComponent"
      class="box-right-option"
    >
      <TimeSetting class="custom-border-right"></TimeSetting>
      <ShareLink v-if="!isExternal"></ShareLink>
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
