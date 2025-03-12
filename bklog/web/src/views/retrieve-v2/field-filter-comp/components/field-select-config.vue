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
  import { computed, ref } from 'vue';
  import useStore from '@/hooks/use-store';
  import useLocale from '@/hooks/use-locale';
  import { useRoute } from 'vue-router/composables';

  import $http from '@/api';

  const store = useStore();
  const route = useRoute();
  const { $t } = useLocale();

  const emit = defineEmits(['select-fields-config']);

  const isDropdownShow = ref(false);
  const isLoading = ref(false);
  const configList = ref([]);

  const unionIndexList = computed(() => store.state.unionIndexList);
  const isUnionSearch = computed(() => store.state.isUnionSearch);
  const dropdownShow = () => {
    isDropdownShow.value = true;
    getFiledConfigList();
  };
  const dropdownHide = () => {
    isDropdownShow.value = false;
  };

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
  const handleClickManagementConfig = () => {
    store.commit('updateShowFieldsConfigPopoverNum', 1);
  };

  const handleClickSelectConfig = item => {
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
  <div class="field-select-config">
    <bk-dropdown-menu
      trigger="click"
      align="left"
      ref="dropdown"
      @show="dropdownShow"
      @hide="dropdownHide"
    >
      <div
        class="dropdown-trigger-text"
        slot="dropdown-trigger"
      >
        <span class="bklog-icon bklog-overview1"></span>
        <span> {{ $t('字段模板') }} </span>
      </div>
      <ul
        v-bkloading="{ isLoading: isLoading, size: 'small' }"
        class="bk-dropdown-list"
        slot="dropdown-content"
      >
        <li
          v-for="(item, index) in configList"
          :key="index"
        >
          <a
            href="javascript:;"
            @click="() => handleClickSelectConfig(item)"
          >
            {{ item.name }}
          </a>
        </li>
        <li>
          <a
            href="javascript:;"
            style="color: #3a84ff; background-color: #fafbfd"
            @click="handleClickManagementConfig"
          >
            {{ $t('管理配置') }}
          </a>
        </li>
      </ul>
    </bk-dropdown-menu>
  </div>
</template>
<style lang="scss">
  @import './field-select-config.scss';
</style>
