<script setup>
import { computed, nextTick } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { BK_LOG_STORAGE } from '@/store/store.type';

import FieldFilterComp from '../field-filter-comp';
const store = useStore();
const { $t } = useLocale();
const props = defineProps({
  value: { type: Boolean, default: true },
  width: { type: Number, default: 200 },
});
const emit = defineEmits(['input', 'field-status-change']);

const showFieldAlias = computed(() => store.state.storage[BK_LOG_STORAGE.SHOW_FIELD_ALIAS]);
/** 时间选择器绑定的值 */
const datePickerValue = computed(() => {
  const { start_time = 'now-15m', end_time = 'now' } = store.state.indexItem;
  return [start_time, end_time];
});

const indexSetItem = computed(() => {
  return store.state.indexItem;
});

const sortList = computed(() => {
  return store.state.indexFieldInfo.sort_list;
});

const totalFields = computed(() => {
  return store.state.indexFieldInfo.fields;
});

const fieldAliasMap = computed(() => {
  const fieldAliasMap = {};
  store.state.indexFieldInfo.fields.forEach(item => {
    item.minWidth = 0;
    item.filterExpand = false; // 字段过滤展开
    item.filterVisible = true;
    fieldAliasMap[item.field_name] = item.query_alias || item.field_alias || item.field_name;
  });

  return fieldAliasMap;
});

const retrieveParams = computed(() => {
  return {
    bk_biz_id: store.state.bkBizId,
    ...store.getters.retrieveParams,
    start_time: datePickerValue.value[0],
    end_time: datePickerValue.value[1],
  };
});

const visibleFields = computed(() => store.state.visibleFields ?? []);
const rootStyle = computed(() => ({
  '--root-width': `${props.width}px`,
}));

/**
 * @desc: 字段设置更新了
 * @param {Array} displayFieldNames 展示字段
 */
const handleFieldsUpdated = async displayFieldNames => {
  store.dispatch('userFieldConfigChange', {
    displayFields: displayFieldNames,
  });
  await nextTick();
  store.commit('resetVisibleFields', { displayFieldNames, version: 'v2' });
  store.commit('updateIsSetDefaultTableColumn', false);
};
const handleCloseFilterTitle = isTextClick => {
  if (isTextClick && props.value) return;
  emit('field-status-change', !props.value);
  emit('input', !props.value);
};
</script>

<template>
  <div
    :class="['search-field-filter-new', { 'is-close': !value }]"
    :style="rootStyle"
  >
    <!-- 字段过滤 -->
    <div
      style="position: absolute; top: 64px; transform: translate(-50%, -50%)"
      class="tab-item-title field-filter-title"
    >
      <div
        class="close-total"
        @click="handleCloseFilterTitle(false)"
      >
        <span
          :style="{ transform: value ? '' : 'rotate(180deg)' }"
          style="font-size: 14px"
          class="bklog-icon bklog-collapse"
          v-bk-tooltips="{ content: value ? $t('收起') : $t('打开') }"
        ></span>
      </div>
    </div>
    <FieldFilterComp
      ref="fieldFilterRef"
      v-show="value"
      :date-picker-value="datePickerValue"
      :field-alias-map="fieldAliasMap"
      :index-set-item="indexSetItem"
      :retrieve-params="retrieveParams"
      :show-field-alias="showFieldAlias"
      :sort-list="sortList"
      :total-fields="totalFields"
      :visible-fields="visibleFields"
      @fields-updated="handleFieldsUpdated"
    />
  </div>
</template>

<style lang="scss">
  @import './field-filter.scss';
</style>
