<script setup>

import { useApplicationStore } from '@/app/state/domains/application-store';
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';

  import useLocale from '@/shared/composables/use-locale';

  import { BK_LOG_STORAGE } from '@/app/state/store.type.ts';
  import RetrieveHelper, { RetrieveEvent } from '@/features/retrieval/retrieve-helper';

  import FieldFilterComp from '../field-filter-comp/index';
  const store = useApplicationStore();
  const { $t } = useLocale();
  const props = defineProps({
    value: { type: Boolean, default: true },
    width: { type: Number, default: 200 },
  });
  const emit = defineEmits(['input', 'field-status-change', "fieldStatusChange"]);

  const showFieldAlias = computed(() => store.storage[BK_LOG_STORAGE.SHOW_FIELD_ALIAS]);
  /** 时间选择器绑定的值 */
  const datePickerValue = computed(() => {
    const { start_time: startTime = 'now-15m', end_time: endTime = 'now' } = store.indexItem;
    return [startTime, endTime];
  });

  const indexSetItem = computed(() => {
    return store.indexItem;
  });

  const sortList = computed(() => {
    return store.indexFieldInfo.sort_list;
  });

  const sourceFields = computed(() => store.filteredFieldList ?? []);
  // 千级字段进 store 后先让 search XHR 出去，下一帧再把列表交给左侧面板，避免首屏 flush 挡住检索。
  // 帧回调只读最新快照：取消已排队的帧会把后续字段更新丢掉，左侧列表就一直空着。
  const deferredFields = ref([]);
  let fieldPaintFrame = 0;
  let pendingFields = [];
  const flushDeferredFields = () => {
    fieldPaintFrame = 0;
    deferredFields.value = pendingFields;
  };
  watch(
    sourceFields,
    fields => {
      pendingFields = Array.isArray(fields) ? fields : [];
      if (fieldPaintFrame) {
        return;
      }
      fieldPaintFrame = requestAnimationFrame(flushDeferredFields);
    },
    { immediate: true },
  );
  onBeforeUnmount(() => {
    if (fieldPaintFrame) {
      cancelAnimationFrame(fieldPaintFrame);
    }
  });

  const totalFields = computed(() => deferredFields.value);

  const fieldAliasMap = computed(() => {
    const fieldAliasMap = {};
    totalFields.value.forEach(item => {
      if (!item?.field_name || item.is_virtual_alias_field) {
        return;
      }
      fieldAliasMap[item.field_name] = item.query_alias || item.field_name;
    });

    return fieldAliasMap;
  });

  const requestAddition = computed(() => store.requestAddition);

  const retrieveParams = computed(() => {
    return {
      bk_biz_id: store.bkBizId,
      ...store.retrieveParams,
      start_time: datePickerValue.value[0],
      end_time: datePickerValue.value[1],
      addition: requestAddition.value ?? [],
      showFieldAlias: store.storage[BK_LOG_STORAGE.SHOW_FIELD_ALIAS],
    };
  });

  const visibleFields = computed(() => store.resolvedVisibleFields ?? []);
  const rootStyle = computed(() => ({
    '--root-width': `${props.width}px`,
  }));

  /**
   * @desc: 字段设置更新了
   * @param {Array} displayFieldNames 展示字段
   */
  const handleFieldsUpdated = async displayFieldNames => {
    store.userFieldConfigChange({
      displayFields: displayFieldNames,
    });
    await nextTick();
    store.resetVisibleFields({ displayFieldNames, version: 'v2' });
    store.updateIsSetDefaultTableColumn(false);
    RetrieveHelper.fire(RetrieveEvent.VISIBLE_FIELD_COLUMN_LAYOUT_CHANGE);
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
    <div class="tab-item-title field-filter-title">
      <div
        class="close-total"
        @click="handleCloseFilterTitle(false)"
      >
        <span
          v-log-tooltip="{ content: value ? $t('收起') : $t('打开') }"
          :style="{ transform: value ? '' : 'rotate(180deg)' }"
          style="font-size: 14px"
          class="bklog-icon bklog-collapse"
        ></span>
      </div>
    </div>
    <FieldFilterComp
      v-show="value"
      ref="fieldFilterRef"
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
  @use './field-filter.scss' as *;
</style>
