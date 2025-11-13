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
          {{ $t('该设置可以将采集设备的元数据信息补充至日志中') }}
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
        :display-tag="true"
        :show-empty="false"
        :auto-height="true"
      >
        <bk-option
          v-for="option in groupList"
          :key="option.field"
          :id="option.field"
          :name="`${option.field}(${option.name})`"
        >
        </bk-option>
      </bk-select>
      <div>
      <span class='addTagBtn' @click="handleAddExtraLabel">{{ $t('添加自定义标签') }}</span>
      <span>{{ $t('如果CMDB的元数据无法满足您的需求，可以自行定义匹配想要的结果') }}</span>
      <template v-if="extraLabelList.length">
        <div
          v-for="(item, index) in extraLabelList"
          class="add-log-label form-div"
          :key="index"
        >
          <div class="keyInputBox">
            <bk-input
              v-model.trim="item.key"
              :class="{ 'extra-error': item.key === '' && isExtraError }"
              @blur="isExtraError = false;item.duplicateKey=false"
            ></bk-input>
            <template v-if="item.duplicateKey">
              <i
                style="right: 8px"
                class="bk-icon icon-exclamation-circle-shape tooltips-icon"
                v-bk-tooltips.top="$t('自定义标签key与元数据key重复')"
              ></i>
            </template>
          </div>
          <span>=</span>
          <bk-input
            v-model.trim="item.value"
            :class="{ 'extra-error': item.value === '' && isExtraError }"
            @blur="isExtraError = false"
          ></bk-input>
          <div class="ml9">
            <i
              :class="['bk-icon icon-plus-circle-shape icons']"
              @click="handleAddExtraLabel"
            ></i>
            <i
              :class="[
                'bk-icon icon-minus-circle-shape icons ml9',
              ]"
              @click="handleDeleteExtraLabel(index)"
            ></i>
          </div>
        </div>
      </template>
      </div>
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
  const extraLabelList = ref([]);
  const isExtraError = ref(false);
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
        } 
      });
      extraLabelList.value = props.metadata.filter(metadataItem => {
        const isDuplicate = groupList.value.some(
          groupItem => groupItem.field === metadataItem.key.slice(5)
        );
        return !isDuplicate;
      }).map( item => {
        return { 
          key: item.key, 
          value: item.value,
          duplicateKey: false,
        };
      });
    } catch (e) {
      console.warn(e);
    }
  };

  const handleAddExtraLabel = () => {
    extraLabelList.value.push({ key: '', value: '' });
  }
  const handleDeleteExtraLabel = (index) => {
    extraLabelList.value.splice(index, 1);
  }
  
  const extraLabelsValidate = () => {
    if(!switcherValue.value){
      return true;
    }
    isExtraError.value = false;
    if (extraLabelList.value.length) {
      extraLabelList.value.forEach(item => {
        if (item.key === '' || item.value === '') {
          isExtraError.value = true;
        }
        if (groupList.value.find(group => group.field === item.key)) {
          item.duplicateKey = true;
          isExtraError.value = true;
        }
      });
    }
    if (isExtraError.value) {
      throw new Error
    }
    handleExtraLabelsChange()
    return true
  }
  const handleExtraLabelsChange = () => {
    if (extraLabelList.value.length) {
      const result = groupList.value.reduce((accumulator, item) => {
        if (selectValue.value.includes(item.field)) {
          accumulator.push({ key: item.field, value: item.key });
        }
        return accumulator;
      }, []);
      result.push(...extraLabelList.value);
      emit('extra-labels-change', result);
    }
  }
  onMounted(() => {
    getDeviceMetaData();
    if (props.metadata.filter(item => item.key).length) {
      switcherValue.value = true;
    }
  });

  watch(selectValue, () => {
    emitExtraLabels();
  });
  defineExpose({
    extraLabelsValidate,
  });
</script>
<style lang="scss" scoped>
  .filter-table-container {
    width: 580px;
    margin-top: 10px;
    color: #63656e;

    .bk-select{
      width: 518px;
    }

    .addTagBtn{
      margin-right: 10px;
      color:#2b7cc7;
      cursor: pointer;
    }

    .add-log-label {
      display: flex;
      align-items: center;

      .keyInputBox{
        position: relative;
 
      }

      span {
        margin: 0 7px;
        color: #ff9c01;
      }

      .bk-form-control {
        width: 240px;
      }
    }

    .extra-error {
      .bk-form-input {
        border-color: #ff5656;
      }
    }
  }
</style>
