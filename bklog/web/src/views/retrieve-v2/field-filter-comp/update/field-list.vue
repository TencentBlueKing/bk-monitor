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

<script setup>
  import Vue, { computed, ref, nextTick } from 'vue';

  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';
  import { useRoute } from 'vue-router/composables';

  import FieldsSetting from '../../result-comp/update/fields-setting';
  import $http from '@/api';

  const store = useStore();
  const route = useRoute();
  const { $t } = useLocale();
  const { $bkPopover } = Vue.prototype;

  const emit = defineEmits(['select-fields-config']);

  /** popover 弹窗实例 */
  let popoverInstance = null;

  const showFieldsSetting = ref(false);
  const isLoading = ref(false);
  const configList = ref([]);
  const searchKeyword = ref('');
  /** 字段模版下拉菜单容器实例 */
  const dropdownRef = ref(null);
  /** 字段配置管理 组件实例  */
  const settingRef = ref(null);
  /** 考虑字段配置管理内容较多，增加简易的懒加载机制 */
  const popoverLazyLoaded = ref({
    dropdown: false,
    setting: false,
  });

  const unionIndexList = computed(() => store.state.unionIndexList);
  const isUnionSearch = computed(() => store.state.isUnionSearch);

  /** 字段配置管理组件所需参数 */
  const retrieveParams = computed(() => store.getters.retrieveParams);
  /** 字段配置管理组件所需参数 */
  const fieldAliasMap = computed(() => {
    return (store.state.indexFieldInfo.fields ?? []).reduce(
      (out, field) => ({ ...out, [field.field_name]: field.field_alias || field.field_name }),
      {},
    );
  });

  const searchConfigList = computed(() => {
    return configList.value.filter(item => {
      // 确保 item.name 是一个字符串
      const name = String(item.name);
      // 检查 name 是否包含 searchString
      return name.includes(searchKeyword.value);
    });
  });

  /**
   * @description 打开字段模板 menu popover
   * @param {Event} e click 点击触发事件 targetEvent
   *
   */
  async function handleDropdownPopoverShow(e) {
    if (popoverInstance) {
      return;
    }
    if (!popoverLazyLoaded.value.dropdown) {
      popoverLazyLoaded.value.dropdown = true;
      await nextTick();
    }
    popoverInstance = $bkPopover(e.currentTarget, {
      content: dropdownRef.value,
      trigger: 'click',
      animateFill: false,
      placement: 'bottom-start',
      theme: 'light field-template-menu field-template-menu-expand',
      arrow: false,
      interactive: true,
      boundary: 'viewport',
      onHidden: () => {
        popoverInstance?.destroy?.();
        popoverInstance = null;
      },
    });
    await nextTick();
    popoverInstance?.show();
    getFiledConfigList();
  }

  /**
   * @description 打开 字段设置 popover
   *
   */
  async function handleFieldSettingPopoverShow() {
    if (popoverInstance) {
      handlePopoverHide();
    }
    if (!popoverLazyLoaded.value.setting) {
      popoverLazyLoaded.value.setting = true;
      await nextTick();
    }
    const triggerDom = document.querySelector('.dropdown-trigger');
    popoverInstance = $bkPopover(triggerDom, {
      content: settingRef.value,
      trigger: 'click',
      animation: 'slide-toggle',
      animateFill: false,
      placement: 'bottom-start',
      theme: 'light bk-select-dropdown field-template-menu',
      arrow: false,
      interactive: true,
      boundary: 'viewport',
      hideOnClick: false,
      zIndex: 3000,
      onHidden: () => {
        showFieldsSetting.value = false;
        popoverInstance?.destroy?.();
        popoverInstance = null;
      },
    });
    await nextTick();
    showFieldsSetting.value = true;
    popoverInstance?.show();
  }

  /**
   * @description 关闭 popover
   *
   */
  function handlePopoverHide() {
    popoverInstance?.hide?.();
    popoverInstance?.destroy?.();
    popoverInstance = null;
  }

  const getFiledConfigList = async () => {
    isLoading.value = true;
    try {
      const res = await $http.request('retrieve/getFieldsListConfig', {
        data: {
          ...(isUnionSearch.value
            ? { index_set_ids: unionIndexList.value }
            : { index_set_id: window.__IS_MONITOR_COMPONENT__ ? route.query.indexId : route.params.indexId }),
          scope: 'default',
          index_set_type: isUnionSearch.value ? 'union' : 'single',
        },
      });
      configList.value = res.data;
    } catch (error) {
    } finally {
      isLoading.value = false;
    }
  };

  const handleClickSelectConfig = item => {
    handlePopoverHide();
    store.commit('retrieve/updateFiledSettingConfigID', item.id);
    store.commit('updateIsSetDefaultTableColumn', false);
    store
      .dispatch('userFieldConfigChange', {
        displayFields: item.display_fields,
        fieldsWidth: {},
      })
      .then(() => {
        store.commit('resetVisibleFields', item.display_fields);
        store.commit('updateIsSetDefaultTableColumn');
        emit('select-fields-config', item.display_fields);
      });
  };
</script>
<template>
  <div class="field-select-config-v2">
    <div
      class="dropdown-trigger"
      @click="handleDropdownPopoverShow"
    >
      <span class="bklog-icon bklog-overview1"></span>
      <span> {{ $t('字段模板') }} </span>
    </div>
    <div style="display: none">
      <div
        v-if="popoverLazyLoaded.dropdown"
        class="dropdown-content"
        :ref="
          vm => {
            dropdownRef = vm;
          }
        "
      >
        <div class="dropdown-search">
          <bk-input
            class="field-input"
            v-model="searchKeyword"
            left-icon="icon-search"
            placeholder="搜索 模板名称"
            clearable
          />
        </div>
        <div class="underline-box"></div>
        <ul
          class="dropdown-list"
          v-bkloading="{ isLoading: isLoading, size: 'small' }"
        >
          <li
            v-for="item in searchConfigList"
            class="dropdown-item"
            :key="item.name"
            @click="() => handleClickSelectConfig(item)"
          >
            <span> {{ item.name }} </span>
          </li>
        </ul>
        <div
          class="dropdown-setting bklog-v3-popover-tag"
          @click="handleFieldSettingPopoverShow"
        >
          <span class="bklog-icon bklog-shezhi" />
          <span>
            {{ $t('管理配置') }}
          </span>
        </div>
      </div>
      <div
        v-if="popoverLazyLoaded.setting"
        class="fields-setting-container"
        :ref="
          vm => {
            settingRef = vm;
          }
        "
      >
        <fields-setting
          v-if="showFieldsSetting"
          :field-alias-map="fieldAliasMap"
          :is-show-left="true"
          :retrieve-params="retrieveParams"
          @cancel="handlePopoverHide"
          @set-popper-instance="() => {}"
        />
      </div>
    </div>
  </div>
</template>
<style lang="scss">
  @import './field-list.scss';
</style>
