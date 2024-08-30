<script setup>
  import { computed, ref } from 'vue';
  import useStore from '@/hooks/use-store';

  const store = useStore();
  const searchValue = ref('');
  const indexFieldInfo = computed(() => store.state.indexFieldInfo);
  const fieldTypeMap = computed(() => store.state.globals.fieldTypeMap);
  const getFieldIcon = fieldType => {
    return fieldTypeMap.value?.[fieldType] ? fieldTypeMap.value?.[fieldType]?.icon : 'bklog-icon bklog-unkown';
  };

  const getFieldIconColor = type => {
    return fieldTypeMap.value?.[type] ? fieldTypeMap.value?.[type]?.color : '#EAEBF0';
  };
</script>
<template>
  <div class="ui-query-options">
    <div class="ui-query-option-content">
      <div class="field-list">
        <div class="ui-search-input">
          <bk-input
            :placeholder="$t('请输入关键字')"
            :left-icon="'bk-icon icon-search'"
            v-model="searchValue"
            behavior="simplicity"
            style="width: 100%"
          >
          </bk-input>
        </div>
        <div class="ui-search-result">
          <div class="ui-search-result-row">
            <span class="field-type-icon">*</span>
            <span class="field-alias">{{ $t('全文检索') }}</span>
            <span class="field-name"></span>
          </div>
          <div
            v-for="item in indexFieldInfo.fields"
            class="ui-search-result-row"
          >
            <span
              :class="[getFieldIcon(item.field_type), 'field-type-icon']"
              :style="{ backgroundColor: getFieldIconColor(item.field_type) }"
            ></span
            ><span class="field-alias">{{ item.field_alias || item.field_name }}</span
            ><span class="field-name">({{ item.field_name }})</span>
          </div>
        </div>
      </div>
      <div class="value-list"></div>
    </div>
    <div class="ui-query-option-footer"></div>
  </div>
</template>
<style scoped>
  @import './ui-input-option.scss';
</style>
