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

<template>
  <div class="log-filter-container">
    <div class="switcher-container">
      <bk-switcher
        v-model="switcherValue"
        size="large"
        theme="primary"
        @change="switcherChange"
      ></bk-switcher>
      <div class="switcher-tips">
        <i class="bk-icon icon-info-circle" />
        <span>
          {{ this.$t('该设置可以将采集设备的元数据信息补充至日志中') }}
        </span>
      </div>
    </div>
    <div
      v-if="switcherValue"
      class="filter-table-container"
    >
      <bk-select
        ref="select"
        searchable
        multiple
        selected-style="checkbox"
        v-model="selectValue"
        :remote-method="remote"
        :display-tag="true"
        :show-empty="false"
        :auto-height="true"
        @tab-remove="handleValuesChange"
        @clear="handleClear"
      >
        <bk-option
          v-for="option in groupList"
          :key="option.field"
          :id="option.field"
          :name="`${option.field}(${option.name})`"
        >
        </bk-option>
      </bk-select>
    </div>
  </div>
</template>
<script setup>
  import { ref, onMounted, watch } from 'vue';
  import $http from '@/api';
  const props = defineProps({
    metadata: {
      type: Array,
      required: true,
    },
  });
  const switcherValue = ref(false);
  const selectValue = ref([]);
  const groupList = ref([]);
  const emit = defineEmits(['extra-labels-change']);
  const emitExtraLabels = () => {
    const result = groupList.value.reduce((accumulator, item) => {
      if (selectValue.value.includes(item.field)) {
        accumulator.push({ key: item.field, value: item.key });
      }
      return accumulator;
    }, []);
    emit('extra-labels-change', result);
  };

  const switcherChange = val => {
    if (!val) {
      emit('extra-labels-change', []);
    }
  };

  const remote = keyword => {
    if (treeRef.value) {
      treeRef.value.filter(keyword);
    }
  };

  const handleValuesChange = options => {
    if (treeRef.value) {
      treeRef.value.setChecked(options.id, { emitEvent: true, checked: false });
    }
  };

  const handleClear = () => {
    if (treeRef.value) {
      treeRef.value.removeChecked({ emitEvent: false });
    }
  };

  // 获取元数据
  const getDeviceMetaData = async () => {
    try {
      const res = await $http.request('linkConfiguration/getSearchObjectAttribute');
      const { scope = [], host = [] } = res.data;
      groupList.value.push(
        ...scope.map(item => {
          item.key = 'scope';
          return item;
        }),
      );
      groupList.value.push(
        ...host.map(item => {
          item.key = 'host';
          return item;
        }),
      );
      selectValue.value = props.metadata.map(item => {
        if (item.key.startsWith('host.')) {
          return item.key.slice(5);
        } else {
          return item.key;
        }
      });
    } catch (e) {
      console.warn(e);
    }
  };

  onMounted(() => {
    getDeviceMetaData();
    if (props.metadata.filter(item => item.key).length) {
      switcherValue.value = true;
    }
  });

  watch(selectValue, () => {
    emitExtraLabels();
  });
</script>
<style lang="scss" scoped>
  .filter-table-container {
    margin-top: 10px;
    width: 518px;
  }
</style>
