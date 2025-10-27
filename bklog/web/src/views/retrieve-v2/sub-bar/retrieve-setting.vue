<script setup>
  import { ref, computed, watch } from 'vue';
  import useStore from '@/hooks/use-store';
  import useRouter from '@/hooks/use-router';
  import useRoute from '@/hooks/use-route';
  import useLocale from '@/hooks/use-locale';

  const emit = defineEmits(['update:is-show-cluster-setting']);

  const showSettingMenuList = ref([]);

  const { $t } = useLocale();
  const router = useRouter();
  const route = useRoute();
  const store = useStore();

  const refTrigger = ref();
  const isExternal = computed(() => store.state.isExternal);
  // const spaceUid = computed(() => store.state.spaceUid);
  const indexSetId = computed(() => store.state.indexId);
  const indexSetItem = computed(() =>
    store.state.retrieve.flatIndexSetList.find(item => item.index_set_id === `${indexSetId.value}`),
  );
  const isPopoverShow = ref(false);
  const spaceUid = computed(() => {
    const indexSetList = store.state.retrieve.flatIndexSetList;
    const indexSetId = route.params?.indexId;
    const currentIndexSet = indexSetList.find(item => `${item.index_set_id}` == indexSetId);
    return currentIndexSet?.space_uid;
  });
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

  const settingMenuList = ref([{ id: 'clustering', name: $t('日志聚类') }]);
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
  /** 路由跳转name */
  const routeNameList = ref({
    log: 'manage-collection',
    custom: 'custom-report-detail',
    bkdata: 'bkdata-index-set-manage',
    es: 'es-index-set-manage',
    indexManage: 'log-index-set-manage',
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
    if (!['log', 'es', 'bkdata', 'custom', 'setIndex'].includes(detailStr)) {
      showSettingMenuList.value = isAiopsToggle.value ? settingMenuList.value : [];
      return;
    }
    // 赋值详情路由的key
    if (detailStr === 'setIndex') {
      detailJumpRouteKey.value = 'indexManage';
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
    const params = {
      indexSetId: indexSetItem.value?.index_set_id,
      collectorId: indexSetItem.value?.collector_config_id,
    };
    // 判断当前是否是脱敏配置 分别跳不同的路由
    const routeName =
      val === 'logMasking'
        ? maskingConfigRoute.value[maskingRouteKey.value]
        : routeNameList.value[detailJumpRouteKey.value];
    // 不同的路由跳转 传参不同
    const { href } = router.resolve({
      name: routeName,
      params,
      query: {
        spaceUid: spaceUid.value,
        type: val === 'logMasking' ? 'masking' : undefined,
      },
    });
    refTrigger.value?.click?.();
    window.open(href, '_blank');
  };

  const handlePopShow = val => {
    isPopoverShow.value = val;
    return true;
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
    placement="bottom-end"
    theme="light bk-select-dropdown"
    trigger="click"
  >
    <slot name="trigger">
      <div
        ref="refTrigger"
        class="more-operation"
      >
        <span class="bklog-icon bklog-setting-line"></span>{{ $t('全局设置') }}
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

<style lang="scss">
  .more-operation {
    display: flex;
    align-items: center;
    justify-content: center;

    span {
      margin: 0 6px 0 0;
      font-size: 14px;
    }
  }
</style>
