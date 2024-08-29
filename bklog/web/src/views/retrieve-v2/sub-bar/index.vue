<script setup>
  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';
  import useRouter from '@/hooks/use-router';
  import BizMenuSelect from '@/components/biz-menu';
  import SettingModal from '../setting-modal';
  import FieldsSetting from '../result-comp/fields-setting';
  // import $http from '@/api';
  import { computed, ref, watch } from 'vue';

  const { $t } = useLocale();
  const store = useStore();
  const router = useRouter();

  const props = defineProps({
    indexSetItem: {
      type: Object,
      required: true,
      default: () => ({})
    },
    // totalFields: {
    //   type: Array,
    //   default: () => [],
    // },
    // configData: {
    //   type: Object,
    //   require: true,
    // },
    // cleanConfig: {
    //   type: Object,
    //   require: true,
    // },
    // datePickerValue: {
    //   type: Array,
    //   required: true,
    // },
    // retrieveParams: {
    //   type: Object,
    //   require: true,
    // },
  });

  const emit = defineEmits(['setting-menu-click', 'update-log-fields', 'fields-updated', 'should-retrieve']);

  const isExternal = computed(() => store.state.isExternal);
  const spaceUid = computed(() => store.state.spaceUid);
  const isShowRetrieveSetting = computed(() => !isExternal.value && !isUnionSearch.value);
  const bkBizId = computed(() => store.state.bkBizId);
  const isShowMaskingTemplate = computed(() => store.getters.isShowMaskingTemplate);
  const isUnionSearch = computed(() => store.getters.isUnionSearch);

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

  const fieldsSettingPopper = ref(null);
  const showSettingMenuList = ref([]);
  const settingMenuList = ref([{ id: 'clustering', name: $t('日志聚类') }]);
  const detailJumpRouteKey = ref('log');
  /** 日志脱敏路由跳转key */
  const maskingRouteKey = ref('log');
  const isShowSettingModal = ref(false);
  const isShowFieldsSetting = ref(false);
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
    {
      id: 'logMasking',
      name: $t('日志脱敏'),
    },
    {
      id: 'logInfo',
      name: $t('采集详情'),
    },
  ]);

  /**
   * @desc: 初始化选择列表
   * @param {String} detailStr 当前索引集类型
   * @param {Boolean} isFilterExtract 是否过滤字段设置
   */
  const initJumpRouteList = (detailStr, isFilterExtract = false) => {
    if (!['log', 'es', 'bkdata', 'custom', 'setIndex'].includes(detailStr)) {
      showSettingMenuList.value.push(...(isAiopsToggle.value ? settingMenuList.value : []));
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
    // 判断是否展示字段设置
    const filterMenuList = isAiopsToggle.value
      ? settingMenuList.value.filter(item => (isFilterExtract ? item.id !== 'extract' : true))
      : [];
    const filterList = accessList.value.filter(item => (isShowMaskingTemplate.value ? true : item.id !== 'logMasking'));
    // 合并其他
    showSettingMenuList.value.push(...filterMenuList.concat(filterList));
  };

  const setShowLiList = setItem => {
    if (JSON.stringify(setItem) === '{}') return;
    if (setItem.scenario_id === 'log') {
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
    initJumpRouteList(setItem.scenario_id, true);
  };

  watch(
    props.indexSetItem,
    () => {
      setShowLiList(props.indexSetItem);
    },
    { immediate: true },
  );

  const handleMenuClick = val => {
    // 不属于新开页面的操作
    if (['index', 'extract', 'clustering'].includes(val)) {
      emit('setting-menu-click', val);
      return;
    }
    const params = {
      indexSetId: props.indexSetItem?.index_set_id,
      collectorId: props.indexSetItem?.collector_config_id,
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
    window.open(href, '_blank');
  };

  const handleDropdownHide = () => {
    isShowFieldsSetting.value = false;
    requestFiledConfig();
  };
  const requestFiledConfig = () => {
    // !!TODO 用store监听去更新原始日志旁边的快速选中下拉框
  };
  const handleDropdownShow = () => {
    isShowFieldsSetting.value = true;
  };
  const closeDropdown = () => {
    isShowFieldsSetting.value = false;
    fieldsSettingPopper.value?.instance.hide();
  };
  const modifyFields = (displayFieldNames, showFieldAlias) => {
    emit('fields-updated', displayFieldNames, showFieldAlias);
    emit('should-retrieve');
  };

  const confirmModifyFields = (displayFieldNames, showFieldAlias) => {
    modifyFields(displayFieldNames, showFieldAlias);
    closeDropdown();
  };

  const cancelModifyFields = () => {
    closeDropdown();
  };

  const setPopperInstance = (status = true) => {
    fieldsSettingPopper.value?.instance.set({
      hideOnClick: status,
    });
  };

  const handleUpdateLogFields = () => {
    emit('update-log-fields');
  };
</script>
<template>
  <div class="subbar-container">
    <!-- <div class="box-favorites"><span class="bklog-icon bklog-collapse-small"></span>{{ $t('收藏夹') }}</div> -->
    <div class="box-biz-select"><BizMenuSelect theme="light"></BizMenuSelect></div>
    <div class="box-right-option">
      <bk-popover
        ref="fieldsSettingPopper"
        animation="slide-toggle"
        placement="bottom-end"
        theme="light bk-select-dropdown"
        trigger="click"
        :distance="15"
        :offset="0"
        :on-hide="handleDropdownHide"
        :on-show="handleDropdownShow"
      >
        <slot name="trigger">
          <div class="field-setting">
            <i class="bklog-icon bklog-setting"></i>
            {{ $t('字段配置') }}
          </div>
        </slot>
        <template #content>
          <div class="fields-setting-container">
            <FieldsSetting
              v-if="isShowFieldsSetting"
              v-on="$listeners"
              :field-alias-map="$attrs['field-alias-map']"
              :retrieve-params="retrieveParams"
              @cancel="cancelModifyFields"
              @confirm="confirmModifyFields"
              @modify-fields="modifyFields"
              @set-popper-instance="setPopperInstance"
            />
          </div>
        </template>
      </bk-popover>
      <div class="more-setting">
        <bk-popover
          v-if="isShowRetrieveSetting"
          :distance="11"
          :offset="0"
          animation="slide-toggle"
          placement="bottom-end"
          theme="light bk-select-dropdown"
          trigger="click"
        >
          <slot name="trigger">
            <div class="more-operation">
              <span class="bklog-icon bklog-ellipsis-more"></span>
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
      </div>
    </div>
    <SettingModal
      :clean-config="cleanConfig"
      :config-data="configData"
      :date-picker-value="datePickerValue"
      :index-set-item="indexSetItem"
      :is-show-dialog="isShowSettingModal"
      :retrieve-params="retrieveParams"
      :total-fields="totalFields"
      @close-setting="isShowSettingModal = false"
      @update-log-fields="handleUpdateLogFields"
    ></SettingModal>
  </div>
</template>
<style scoped>
  @import './index.scss';
</style>
