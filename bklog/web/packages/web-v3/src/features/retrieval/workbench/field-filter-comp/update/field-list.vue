<!--
* Tencent is pleased to support the open source community by making
* 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
*
* Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
*
* 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
*
* License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
*
* ---------------------------------------------------
* Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
* documentation files (the "Software"), to deal in the Software without restriction, including without limitation
* the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
* to permit persons to whom the Software is furnished to do so, subject to the following conditions:
*
* The above copyright notice and this permission notice shall be included in all copies or substantial portions of
* the Software.
*
* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
* THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
* AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
* CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
* IN THE SOFTWARE.
-->

<script setup lang="ts">
import { BK_LOG_STORAGE } from '@/app/state/store.type';
import { ServicesInstance } from '@/platform/services';

import { computed, ref, nextTick } from 'vue';

import { Popup as TPopup, Input as TInput } from 'tdesign-vue-next';
import type { Props as TippyProps } from 'tippy.js';
import BklogLoading from '@/shared/ui/loading';
import type { SortPair } from '../../result-comp/update/field-settings.types';
import useLocale from '@/shared/composables/use-locale';
import useStore from '@/shared/composables/use-store';
import { useRoute } from 'vue-router';

import FieldsSetting from '../../result-comp/update/fields-setting.vue';
import BkLogPopover from '@/shared/ui/bklog-popover/index';
import RetrieveHelper, { RetrieveEvent } from '@/features/retrieval/retrieve-helper';

interface FieldConfig {
  name: string;
  id: number;
  display_fields: string[];
  sort_list: SortPair[];
}
interface SettingPopover {
  show: (target?: HTMLElement) => void;
  hide: () => void;
}

const store = useStore();
const route = useRoute();
const { $t } = useLocale();

const emit = defineEmits(['select-fields-config', 'handle-popover-hide', 'selectFieldsConfig', 'handlePopoverHide']);

/** popover 弹窗实例 */
const dropdownVisible = ref(false);

const showFieldsSetting = ref(false);
const isLoading = ref(false);
const configList = ref<FieldConfig[]>([]);
const searchKeyword = ref('');

/** 打开 popover 弹窗时获取相对位置需要依据的目标节点 */
const popoverTrigger = ref<HTMLElement>();
/** 字段设置弹窗 BkLogPopover 组件引用 */
const settingPopoverRef = ref<SettingPopover>();
/** 考虑字段配置管理内容较多，增加简易的懒加载机制 */
const popoverLazyLoaded = ref({
  dropdown: false,
  setting: false,
});

const unionIndexList = computed(() => store.state.unionIndexList);
const isUnionSearch = computed(() => store.getters.isUnionSearch);
const isSceneMode = computed(() => store.getters.isSceneMode);
const isStartTextEllipsis = computed(() => store.state.storage[BK_LOG_STORAGE.TEXT_ELLIPSIS_DIR] === 'start');

/** 字段配置管理组件所需参数 */
const retrieveParams = computed(() => store.getters.retrieveParams);
/** 字段配置管理组件所需参数 */
const fieldAliasMap = computed(() => {
  return store.getters.fieldAliasMap;
});

const searchConfigList = computed(() => {
  return configList.value.filter((item) => {
    // 确保 item.name 是一个字符串
    const name = String(item.name);
    // 检查 name 是否包含 searchString
    return name.includes(searchKeyword.value);
  });
});

/** 字段设置 popover 配置 */
const settingTippyOptions: Partial<TippyProps> = {
  placement: 'top-start',
  arrow: false,
  hideOnClick: false,
  maxWidth: 1200,
  offset: [-16, -40],
  appendTo: document.body,
  // Keep the full panel usable when neither vertical placement fits a short
  // viewport. Popper otherwise preserves the preferred, clipped top position.
  popperOptions: {
    modifiers: [{ name: 'preventOverflow', options: { altAxis: true, padding: 8 } }],
  },
};

/**
 * @description 字段设置弹窗隐藏前的钩子
 */
function handleSettingBeforeHide(e: MouseEvent) {
  // 点击弹窗内部元素时不关闭
  if ((e.target as Element | null)?.closest?.('.bklog-v3-popover-tag')) {
    return false;
  }
  showFieldsSetting.value = false;
  return true;
}

/**
 * @description 打开字段模板 menu popover
 * @param {Event} e click 点击触发事件 targetEvent
 *
 */
function handleDropdownVisibleChange(visible: boolean) {
  if (visible === dropdownVisible.value) return;
  dropdownVisible.value = visible;
  if (visible) {
    popoverLazyLoaded.value.dropdown = true;
    getFiledConfigList();
  } else {
    emit('handle-popover-hide');
  }
}

/**
 * @description 打开 字段设置 popover
 *
 */
async function handleFieldSettingPopoverShow() {
  handlePopoverHide();
  if (!popoverLazyLoaded.value.setting) {
    popoverLazyLoaded.value.setting = true;
    await nextTick();
  }

  // 使用 BkLogPopover 组件打开字段设置弹窗
  settingPopoverRef.value?.show?.(popoverTrigger.value);
  showFieldsSetting.value = true;
}

/**
 * @description 关闭 popover
 *
 */
function handlePopoverHide() {
  if (!dropdownVisible.value) return;
  dropdownVisible.value = false;
  emit('handle-popover-hide');
}

/**
 * @description 由于 fields-setting 组件中自定义监听click事件关闭popover，防止导致字段模板下拉菜单也失效单独处理关闭逻辑
 *
 */
function handleFieldsSettingHide() {
  if (!showFieldsSetting.value) {
    return;
  }
  settingPopoverRef.value?.hide?.();
  showFieldsSetting.value = false;
}

const getFiledConfigList = async () => {
  isLoading.value = true;
  try {
    const requestName = isSceneMode.value
      ? ServicesInstance.retrieve.sceneListConfig
      : ServicesInstance.retrieve.getFieldsListConfig;
    const data = isSceneMode.value
      ? {
          bk_biz_id: store.state.bkBizId,
          scene_id: store.state.indexItem.scene_active,
          scope: 'default',
        }
      : {
          ...(isUnionSearch.value
            ? { index_set_ids: unionIndexList.value }
            : { index_set_id: window.__IS_MONITOR_COMPONENT__ ? route.query.indexId : route.params.indexId }),
          scope: 'default',
          index_set_type: isUnionSearch.value ? 'union' : 'single',
        };
    const res = await requestName({ data });
    configList.value = res.data as FieldConfig[];
  } catch {
    // 配置加载失败时保留当前列表，错误由请求层统一处理
  } finally {
    isLoading.value = false;
  }
};

const handleClickSelectConfig = async (item: FieldConfig) => {
  handlePopoverHide();
  store.commit('retrieve/updateFiledSettingConfigID', item.id);
  store.commit('updateState', { localSort: false });
  store.commit('updateIsSetDefaultTableColumn', false);

  // 先等待用户配置保存完成
  await store.dispatch('userFieldConfigChange', {
    displayFields: item.display_fields,
    sortList: item.sort_list,
    fieldsWidth: {},
  });

  // 更新本地显示字段状态
  store.commit('resetVisibleFields', item.display_fields);
  store.commit('updateIsSetDefaultTableColumn');
  emit('select-fields-config', item.display_fields);

  // 应用模板后重新请求数据
  await store.dispatch('requestIndexSetFieldInfo');
  await store.dispatch('requestIndexSetQuery');
  RetrieveHelper.fire(RetrieveEvent.SORT_LIST_CHANGED);
};

const isPopoverInstance = () => {
  return dropdownVisible.value;
};
defineExpose({
  isPopoverInstance,
});
</script>
<template>
  <div class="field-select-config-v2">
    <TPopup
      :visible="dropdownVisible"
      trigger="click"
      placement="right"
      overlay-class-name="bklog-v3-popover-tag field-template-menu-theme light-theme field-template-menu-expand-theme"
      @visible-change="handleDropdownVisibleChange"
    >
      <div ref="popoverTrigger" class="dropdown-trigger">
        <span class="bklog-icon bklog-overview1"></span>
        <span class="trigger-label">{{ $t('字段模板') }}</span>
        <i class="bk-icon icon-angle-right-line"></i>
      </div>
      <template #content>
        <div v-if="popoverLazyLoaded.dropdown" class="dropdown-content">
          <div class="dropdown-search">
            <TInput v-model:value="searchKeyword" class="field-input" :placeholder="$t('请输入模板名称')" clearable>
              <template #prefix-icon><span class="bk-icon icon-search" /></template>
            </TInput>
          </div>
          <div class="underline-box"></div>
          <BklogLoading :loading="isLoading">
            <ul class="dropdown-list">
              <li
                v-for="item in searchConfigList"
                :key="item.name"
                class="dropdown-item"
                @click="handleClickSelectConfig(item)"
              >
                <span>{{ item.name }}</span>
              </li>
            </ul>
          </BklogLoading>
          <div class="dropdown-setting bklog-v3-popover-tag" @click="handleFieldSettingPopoverShow">
            <span class="bklog-icon bklog-shezhi" /><span>{{ $t('管理配置') }}</span>
          </div>
        </div>
      </template>
    </TPopup>
    <div style="display: none">
      <!-- 字段设置弹窗使用 BkLogPopover -->
      <BkLogPopover
        v-if="popoverLazyLoaded.setting"
        ref="settingPopoverRef"
        :options="settingTippyOptions"
        :before-hide="handleSettingBeforeHide"
      >
        <template #content>
          <div class="fields-setting-container" :class="{ 'is-start-text-ellipsis': isStartTextEllipsis }">
            <fields-setting
              :field-alias-map="fieldAliasMap"
              :is-show="showFieldsSetting"
              :retrieve-params="retrieveParams"
              config-type="template"
              @cancel="handleFieldsSettingHide"
              @set-popper-instance="() => {}"
            />
          </div>
        </template>
      </BkLogPopover>
    </div>
  </div>
</template>
<style lang="scss">
@use './field-list.scss' as *;
</style>
