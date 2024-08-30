<script setup>
  import { computed, ref, watch } from 'vue';
  import useStore from '@/hooks/use-store';

  const store = useStore();
  const searchValue = ref('');
  const indexFieldInfo = computed(() => store.state.indexFieldInfo);
  const fieldTypeMap = computed(() => store.state.globals.fieldTypeMap);

  const getRegExp = (searchValue, flags = 'ig') => {
    return new RegExp(`${searchValue}`.replace(/[-[\]{}()*+?.,\\^$|#\s]/g, '\\$&'), flags);
  };

  const filterFieldList = computed(() => {
    const regExp = getRegExp(searchValue.value);
    return indexFieldInfo.value.fields.filter(field => regExp.test(field.field_alias) || regExp.test(field.field_name));
  });

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
            v-model="searchValue"
            left-icon="bk-icon icon-search"
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
            v-for="item in filterFieldList"
            class="ui-search-result-row"
            :key="item.field_name"
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
