<script setup>
  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';
  import BizMenuSelect from '@/components/biz-menu';
  import { computed, onMounted, ref } from 'vue';
  const { $t } = useLocale();
  const store = useStore();

  const isExternal = computed(() => store.state.isExternal);
  const isUnionSearch = computed(() => store.getters.isUnionSearch);
  const isShowRetrieveSetting = computed(() => isExternal.value && isUnionSearch.value || true);
  const bkBizId = computed(() => store.state.bkBizId);
  const isShowMaskingTemplate = computed(() => store.getters.isShowMaskingTemplate);

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

  const showSettingMenuList = ref([]);
  const settingMenuList = ref([{ id: 'clustering', name: $t('日志聚类') }]);
  const detailJumpRouteKey = ref('log');
  const maskingRouteKey = ref('log');

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

  onMounted(() => {
    initJumpRouteList('setIndex');
  })
</script>
<template>
  <div class="subbar-container">
    <div class="box-favorites"><span class="log-icon icon-collapse-small"></span>{{ $t('收藏夹') }}</div>
    <div class="box-biz-select"><BizMenuSelect theme="light"></BizMenuSelect></div>
    <div class="box-right-option">
      <div class="field-setting"><span class="log-icon icon-setting"></span>{{ $t('字段配置') }}</div>
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
              <span class="log-icon icon-ellipsis-more"></span>
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
                >
                  {{ menu.name }}
                </li>
              </ul>
            </div>
          </template>
        </bk-popover>
      </div>
    </div>
  </div>
</template>
<style scoped>
  @import './index.scss';
</style>
