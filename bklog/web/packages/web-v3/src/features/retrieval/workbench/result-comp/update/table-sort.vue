<template>
  <div>
    <vue-draggable v-bind="dragOptions" :list="sortList" item-key="key" class="custom-select-list">
      <template #item="{ element }">
        <li class="custom-select-item">
          <span class="icon bklog-icon bklog-ketuodong"></span>
          <Select
            :value="element.sorts[0]"
            @change="(value) => updateSortValue(element.sorts, 0, value)"
            style="width: 174px"
            class="rtl-text"
            :popup-props="{
              overlayClassName: [
                'bklog-v3-popover-tag',
                'table-sort-option-container',
                { 'is-start-text-ellipsis': isStartTextEllipsis },
              ],
              overlayInnerStyle: { width: '174px' },
            }"
            :input-props="{ autofocus: true }"
            filterable
          >
            <!-- bklog-v3-popover-tag 不要乱加，这里用来判定是否为select 弹出，只做标识，不做样式作用 -->

            <Option
              v-for="option in selectList"
              :value="option.field_name"
              :key="option.field_name"
              class="custom-option bklog-v3-popover-tag"
              :disabled="option.disabled"
              :label="option.field_name"
            >
              <div class="custom-option-item bklog-v3-popover-tag">
                <span
                  :style="{
                    backgroundColor: option.is_full_text ? undefined : getFieldIconColor(option.field_type),
                    color: option.is_full_text ? undefined : getFieldIconTextColor(option.field_type),
                  }"
                  :class="[option.is_full_text ? 'full-text' : getFieldIcon(option.field_type), 'field-type-icon']"
                >
                </span>
                <div
                  v-if="option.query_alias"
                  v-log-overflow-tips="{ placement: 'right' }"
                  class="display-container rtl-text"
                >
                  <span class="field-alias">{{ option.query_alias || option.field_name }}</span>
                  <span class="field-name">({{ option.field_name }})</span>
                </div>
                <div v-else v-log-overflow-tips="{ placement: 'right' }" class="display-container rtl-text">
                  <span class="field-name">{{ option.field_name }}</span>
                </div>
              </div>
            </Option>
          </Select>
          <Select
            :value="element.sorts[1]"
            :popup-props="{
              overlayClassName: 'bklog-v3-popover-tag table-sort-option-container',
              overlayInnerStyle: { width: '77px' },
            }"
            @change="(value) => updateSortValue(element.sorts, 1, value)"
            style="width: 77px"
            :placeholder="$t('请选择')"
          >
            <!-- bklog-v3-popover-tag 不要乱加，这里用来判定是否为select 弹出，只做标识，不做样式作用 -->
            <Option
              v-for="option in orderList"
              :value="option.id"
              :key="option.id"
              class="bklog-v3-popover-tag"
              :label="option.name"
            >
            </Option>
          </Select>
          <button
            type="button"
            class="sort-field-remove bklog-v3-popover-tag"
            :aria-label="$t('删除')"
            @click="deleteTableItem(element.key)"
          >
            <span class="bklog-icon bklog-circle-minus-filled" aria-hidden="true"></span>
          </button>
        </li>
      </template>
    </vue-draggable>
    <button type="button" class="sort-field-add" @click="addTableItem()">
      <span class="bklog-icon bklog-log-plus-circle-shape" aria-hidden="true"></span>
      {{ $t('添加排序字段') }}
    </button>
  </div>
</template>
<script setup lang="ts">

import { useApplicationStore } from '@/app/state/domains/application-store';
import { useGlobalsStore } from '@/app/state/domains/globals-store';

import { computed, ref, watch, type PropType } from 'vue';
import useLocale from '@/shared/composables/use-locale';

import VueDraggable from 'vuedraggable-vue3';
import { preserveVue3ComponentModel } from '@/platform/compat/vue3-component-model';
preserveVue3ComponentModel(VueDraggable);
import type { FieldDefinition, FieldTypeStyle, SortPair } from './field-settings.types';
import { Select, Option } from 'tdesign-vue-next';
import { toWorkerMessage } from '@/shared/lib/worker-message';
import 'tdesign-vue-next/es/style/index.css';

import { random } from '../../../../../shared/lib/util';
import { BK_LOG_STORAGE } from '../../../../../app/state/store.type.ts';
const props = defineProps({
  initData: {
    type: Array as PropType<SortPair[]>,
    default: () => [],
  },
  shouldRefresh: {
    type: Boolean,
    default: false,
  },
});
const { $t } = useLocale();
const isStartTextEllipsis = computed(() => store.storage[BK_LOG_STORAGE.TEXT_ELLIPSIS_DIR] === 'start');
const fieldTypeMap = computed(() => useGlobalsStore().$state.fieldTypeMap as Record<string, FieldTypeStyle>);
const dragOptions = {
  animation: 150,
  tag: 'ul',
  handle: '.bklog-ketuodong',
  'ghost-class': 'sortable-ghost-class',
};
const orderList = [
  { id: 'desc', name: $t('降序') },
  { id: 'asc', name: $t('升序') },
];
const store = useApplicationStore();

/** 新增变量处理v-for时需要使用的 key 字段，避免重复新建 VNode */
const sortList = ref<{ key: string; sorts: SortPair }[]>([{ key: random(8), sorts: ['', ''] }]);

const shadowSort = computed(() => sortList.value.map((e) => e.sorts).filter((e) => e[0] !== '' && e[1] !== ''));
const fieldList = computed<FieldDefinition[]>(() => store.filteredFieldList as FieldDefinition[]);

const selectList = computed(() => {
  const filterFn = (field: FieldDefinition) =>
    field.es_doc_values && field.field_type !== '__virtual__' && field.field_type !== 'flattened';
  return fieldList.value.filter(filterFn).map((field: FieldDefinition) => {
    return Object.assign({}, field, { disabled: shadowSort.value.some((item) => item[0] === field.field_name) });
  });
});

const updateSortValue = (sorts: SortPair, index: 0 | 1, value: unknown) => {
  // TDesign clears a single Select with undefined; V2's draft contract is ''.
  sorts[index] = typeof value === 'string' ? value : '';
};
const deleteTableItem = (val: string) => {
  sortList.value = sortList.value.filter((item) => item.key !== val);
};
const addTableItem = () => {
  sortList.value.push({ key: random(8), sorts: ['', ''] });
};
const getFieldIconColor = (type: string | number) => {
  return fieldTypeMap.value?.[type] ? fieldTypeMap.value?.[type]?.color : 'var(--td-bg-color-component)';
};
const getFieldIconTextColor = (type: string | number) => {
  return fieldTypeMap.value?.[type]?.textColor;
};
const getFieldIcon = (fieldType: string | number) => {
  return fieldTypeMap.value?.[fieldType] ? fieldTypeMap.value?.[fieldType]?.icon : 'bklog-icon bklog-unkown';
};

watch(
  () => [props.initData, props.shouldRefresh] as const,
  ([newInitData]) => {
    // 当有初始数据时，直接更新
    if (Array.isArray(newInitData) && newInitData.length) {
      const filterList = newInitData;
      if (filterList.length) {
        sortList.value = structuredClone(toWorkerMessage(filterList)).map((sorts) => ({ key: random(8), sorts }));
      }
    }
  },
  { immediate: true, deep: true },
);
defineExpose({ shadowSort });
</script>
<style lang="scss" scoped>
.custom-select-list {
  .custom-select-item {
    display: flex;
    column-gap: 8px;
    align-items: center;
    justify-content: center;
    margin-bottom: 8px;

    .bklog-ketuodong {
      width: 18px;
      font-size: 18px;
      color: var(--td-text-color-placeholder);
      text-align: left;
      cursor: move;
    }
  }
}

.table-sort-option-time {
  box-sizing: border-box;
  width: 174px;
  padding: 0 36px 0 10px;
  font-size: 12px;
  line-height: 30px;
  color: var(--td-text-color-secondary);
  cursor: not-allowed;
  background-color: var(--td-bg-color-component-disabled);
  border: var(--bklog-border-width) solid var(--td-component-border);
  border-radius: var(--bklog-standard-control-radius);

  .badge {
    padding: 0px 7px;
    color: var(--td-text-color-placeholder);
    background-color: var(--td-bg-color-component);
    border-radius: 8px;
  }
}

.sort-field-add,
.sort-field-remove {
  display: inline-flex;
  align-items: center;
  padding: 0;
  font: inherit;
  cursor: pointer;
  background: transparent;
  border: 0;
  border-radius: var(--bklog-standard-control-radius);

  .bklog-icon {
    font-size: var(--bklog-font-action);
  }

  &:focus-visible {
    outline: var(--bklog-border-width) solid var(--td-brand-color);
  }
}

.sort-field-add {
  gap: var(--bklog-space-4);
  margin-inline-start: var(--bklog-space-20);
  color: var(--td-text-color-link);
}

.sort-field-remove {
  color: var(--td-text-color-secondary);

  &:hover {
    color: var(--td-error-color);
  }
}
</style>
<style lang="scss">
.table-sort-option-container {
  .t-select-option {
    height: var(--bklog-control-size-medium);
    padding-inline: var(--bklog-space-8);
    line-height: var(--bklog-control-size-medium);

    > span {
      display: flex;
      flex: 1;
      width: 100%;
      min-width: 0;
    }
  }

  .custom-option-item {
    display: flex;
    flex: 1;
    align-items: center;
    width: 100%;
    min-width: 0;

    .field-type-icon {
      flex: none;
      width: var(--bklog-space-16);
      height: var(--bklog-space-16);
      margin-inline-end: var(--bklog-space-4);
    }

    .display-container {
      flex: 1;
      width: auto;
      min-width: 0;
      padding-inline-end: var(--bklog-space-4);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }
}
</style>
