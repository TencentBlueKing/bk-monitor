<script setup>
  import { ref, computed, watch } from 'vue';
  import useStore from '@/hooks/use-store';
  import useRouter from '@/hooks/use-router';
  import useLocale from '@/hooks/use-locale';
  import { isFeatureToggleOn } from '@/store/helper';

  const emit = defineEmits(['update:is-show-cluster-setting']);

  const showSettingMenuList = ref([]);

  const { $t } = useLocale();
  const router = useRouter();
  const store = useStore();

  const refTrigger = ref();
  const isExternal = computed(() => store.state.isExternal);
  const spaceUid = computed(() => store.state.spaceUid);
  const indexSetId = computed(() => store.state.indexId);
  const indexSetItem = computed(() =>
    store.state.retrieve.flatIndexSetList.find(item => item.index_set_id === `${indexSetId.value}`),
  );
  /** 判断当前索引集是否是索引组（有子节点） */
  const isIndexGroup = computed(() => {
    return (indexSetItem.value?.children?.length ?? 0) > 0;
  });
  const isPopoverShow = ref(false);

  const isUnionSearch = computed(() => store.isUnionSearch);
  const isShowRetrieveSetting = computed(() => !isExternal.value && !isUnionSearch.value);
  const isShowMaskingTemplate = computed(() => store.getters.isShowMaskingTemplate);
  const clusterIsActive = computed(() => store.state.indexSetFieldConfig.clustering_config.is_active);
  const storeIsShowClusterStep = computed(() => store.state.storeIsShowClusterStep);
  const bkBizId = computed(() => store.state.bkBizId);

  const isAiopsToggle = computed(() => {
    // 日志聚类总开关
    const { bkdata_aiops_toggle: bkdataAiopsToggle } = window.FEATURE_TOGGLE;
    const aiopsBizList = window.FEATURE_TOGGLE_WHITE_LIST?.bkdata_aiops_toggle;

    switch (bkdataAiopsToggle) {
      case 'on':
        return true;
      case 'off':
        return false;
      default:
        return aiopsBizList ? aiopsBizList.some(item => item.toString() === bkBizId.value) : false;
    }
  });

  const settingMenuList = ref([
    // { id: 'clustering', name: $t('日志聚类') }
  ]);
  const detailJumpRouteKey = ref('log');
  /** 日志脱敏路由跳转key */
  const maskingRouteKey = ref('log');
  const maskingConfigRoute = ref({
    log: 'collectMasking',
    es: 'es-index-set-masking',
    custom: 'custom-report-masking',
    bkdata: 'bkdata-index-set-masking',
    setIndex: 'log-index-set-masking',
  });
  const isV2Enabled = computed(() => {
    return isFeatureToggleOn('log_manage_v2', [String(bkBizId.value), String(spaceUid.value)]);
  });

  /** 路由跳转name */
  const routeNameList = computed(() => {
    if (isV2Enabled.value) {
      return {
        log: 'manage-collection',
        custom: 'manage-collection',
        bkdata: 'manage-collection',
        es: 'manage-collection',
        indexManage: 'log-index-set-manage',
        indexGroup: 'collection-item-list', // 索引组跳转到新版采集列表页
      };
    }
    return {
      log: 'manage-collection',
      custom: 'custom-report-detail',
      bkdata: 'bkdata-index-set-manage',
      es: 'es-index-set-manage',
      indexManage: 'log-index-set-manage',
    };
  });

  const accessList = ref([
    // {
    //   id: 'logMasking',
    //   name: $t('日志脱敏'),
    // },
    {
      id: 'logInfo',
      name: $t('采集详情'),
    },
  ]);

  /**
   * @desc: 初始化选择列表
   * @param {String} detailStr 当前索引集类型
   */
  const initJumpRouteList = detailStr => {
    if (!detailStr) return;
    if (!['log', 'es', 'bkdata', 'custom', 'setIndex', 'indexGroup'].includes(detailStr)) {
      showSettingMenuList.value = isAiopsToggle.value ? settingMenuList.value : [];
      return;
    }
    // 赋值详情路由的key
    if (detailStr === 'setIndex') {
      detailJumpRouteKey.value = 'indexManage';
    } else if (detailStr === 'indexGroup') {
      detailJumpRouteKey.value = 'indexGroup';
    } else {
      detailJumpRouteKey.value = detailStr;
    }
    // 日志脱敏的路由key
    maskingRouteKey.value = detailStr;
    const isShowClusterSet = clusterIsActive.value || storeIsShowClusterStep.value;
    // 判断是否展示字段设置
    const filterMenuList = isAiopsToggle.value
      ? settingMenuList.value.filter(item => (isShowClusterSet ? true : item.id !== 'clustering'))
      : [];
    const filterList = accessList.value.filter(item => (isShowMaskingTemplate.value ? true : item.id !== 'logMasking'));
    // 合并其他
    showSettingMenuList.value = [...filterMenuList.concat(filterList)];
  };

  const setShowLiList = setItem => {
    if (setItem?.scenario_id === 'log') {
      // 索引集类型为采集项或自定义上报
      if (setItem.collector_scenario_id === null) {
        // 新版采集页面启用时，判断是否是索引组（有子节点）
        if (isV2Enabled.value && isIndexGroup.value) {
          initJumpRouteList('indexGroup');
          return;
        }
        // 若无日志类型 则类型为索引集
        initJumpRouteList('setIndex');
        return;
      }
      // 判断是否是自定义上报类型
      initJumpRouteList(setItem.collector_scenario_id === 'custom' ? 'custom' : 'log');
      return;
    }
    // 当scenario_id不为log（采集项，索引集，自定义上报）时，不显示字段设置
    initJumpRouteList(setItem?.scenario_id);
  };

  const handleMenuClick = val => {
    // 不属于新开页面的操作
    if (['index', 'extract', 'clustering'].includes(val)) {
      emit('update:is-show-cluster-setting', true);
      return;
    }

    const currentKey = detailJumpRouteKey.value;
    const isBkDataOrEs = ['bkdata', 'es'].includes(currentKey);
    const isCustom = currentKey === 'custom';
    const isIndexGroupType = currentKey === 'indexGroup';

    const routeName =
      val === 'logMasking'
        ? maskingConfigRoute.value[maskingRouteKey.value]
        : routeNameList.value[currentKey];

    const params = {};
    const query = {
      spaceUid: spaceUid.value,
      bizId: bkBizId.value,
    };

    // 索引组跳转时传递 indexSetId 参数
    if (isIndexGroupType) {
      query.indexSetId = indexSetItem.value?.index_set_id;
    } else if (isV2Enabled.value && (isBkDataOrEs || isCustom)) {
      params.collectorId = isBkDataOrEs
        ? indexSetItem.value?.index_set_id
        : indexSetItem.value?.collector_config_id;
      query.typeKey = isCustom ? 'custom_report' : currentKey;
    } else {
      params.indexSetId = indexSetItem.value?.index_set_id;
      params.collectorId = indexSetItem.value?.collector_config_id;
    }

    if (val === 'logMasking') {
      query.type = 'masking';
    }

    const { href } = router.resolve({ name: routeName, params, query });
    refTrigger.value?.click?.();
    window.open(href, '_blank');
  };

  const handlePopShow = val => {
    isPopoverShow.value = val;
  };

  watch(
    [indexSetItem, clusterIsActive, storeIsShowClusterStep],
    () => {
      setShowLiList({
        scenario_id: indexSetItem.value?.scenario_id,
        collector_scenario_id: indexSetItem.value?.collector_scenario_id,
      });
    },
    { deep: true },
  );
</script>
<template>
  <bk-popover
    v-if="isShowRetrieveSetting"
    :distance="11"
    :offset="0"
    :on-hide="() => handlePopShow(false)"
    :on-show="() => handlePopShow(true)"
    animation="slide-toggle"
    placement="bottom-center"
    theme="light bk-select-dropdown bk-select-dropdown-expand"
    trigger="click"
  >
    <slot name="trigger">
      <div
        ref="refTrigger"
        class="more-operation"
      >
        {{ $t('更多') }}
        <span
          class="bklog-icon bklog-arrow-down-filled"
          :class="isPopoverShow ? 'transform' : ''"
        ></span>
      </div>
    </slot>
    <template #content>
      <div class="retrieve-setting-container">
        <ul
          ref="menu"
          class="list-menu"
        >
          <li
            v-for="menu in showSettingMenuList"
            class="list-menu-item"
            :key="menu.id"
            @click="handleMenuClick(menu.id)"
          >
            {{ menu.name }}
          </li>
        </ul>
      </div>
    </template>
  </bk-popover>
</template>

<style lang="scss" scoped>
  .more-operation {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 60px;
    height: 52px;

    span {
      margin: 0 -4px 0 0;
      font-size: 14px;
    }

    .transform {
      transform: rotate(180deg);
    }
  }
</style>
