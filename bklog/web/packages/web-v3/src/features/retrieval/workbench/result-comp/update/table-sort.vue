<template>
  <div>
    <vue-draggable v-bind="dragOptions" v-model="sortList" item-key="key" class="custom-select-list">
      <template #item="{ element: { key, sorts } }">
        <li class="custom-select-item">
          <span class="icon bklog-icon bklog-ketuodong"></span>
          <Select
            :value="sorts[0]"
            clearable
            @change="(value) => updateSortValue(sorts, 0, value)"
            style="width: 174px"
            class="rtl-text"
            :popup-props="{
              overlayClassName: [
                'bklog-v3-popover-tag',
                'table-sort-option-container',
                { 'is-start-text-ellipsis': isStartTextEllipsis },
              ],
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
            :value="sorts[1]"
            clearable
            :popup-props="{ overlayClassName: 'bklog-v3-popover-tag table-sort-option-container' }"
            @change="(value) => updateSortValue(sorts, 1, value)"
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
          <span
            style="font-size: 14px; color: #c4c6cc"
            class="bklog-icon bklog-circle-minus-filled bklog-v3-popover-tag"
            @click="deleteTableItem(key)"
          ></span>
        </li>
      </template>
    </vue-draggable>
    <span
      style="margin-left: 20px; font-size: 14px; color: #3a84ff"
      class="bklog-icon bklog-log-plus-circle-shape"
      @click="addTableItem()"
      ><span style="margin-left: 4px; font-size: 12px" class="add-sort-field">{{ $t('添加排序字段') }}</span></span
    >
  </div>
</template>
<script setup lang="ts">
import { computed, ref, watch, type PropType } from 'vue';
import useLocale from '@/shared/composables/use-locale';
import useStore from '@/shared/composables/use-store';
import VueDraggable from 'vuedraggable-vue3';
Object.assign(VueDraggable, { compatConfig: { MODE: 3 } });
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
const isStartTextEllipsis = computed(() => store.state.storage[BK_LOG_STORAGE.TEXT_ELLIPSIS_DIR] === 'start');
const fieldTypeMap = computed(() => store.state.globals.fieldTypeMap as Record<string, FieldTypeStyle>);
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
const store = useStore();

/** 新增变量处理v-for时需要使用的 key 字段，避免重复新建 VNode */
const sortList = ref<{ key: string; sorts: SortPair }[]>([{ key: random(8), sorts: ['', ''] }]);

const shadowSort = computed(() => sortList.value.map((e) => e.sorts).filter((e) => e[0] !== '' && e[1] !== ''));
const fieldList = computed<FieldDefinition[]>(() => store.getters.filteredFieldList as FieldDefinition[]);

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
  return fieldTypeMap.value?.[type] ? fieldTypeMap.value?.[type]?.color : '#EAEBF0';
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
      color: hsl(223, 7%, 62%);
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
  color: #63656e;
  cursor: not-allowed;
  background-color: #fafbfc;
  border: 1px solid #c4c6cc;
  border-radius: 2px;

  .badge {
    padding: 0px 7px;
    color: #979bb4;
    background-color: #eaebee;
    border-radius: 8px;
  }
}

.table-sort-option-container {
  .custom-option-item {
    display: flex;
    align-items: center;

    .display-container {
      width: calc(100% - 12px);
      padding: 0 4px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }
}

.bklog-circle-minus-filled {
  cursor: pointer;
}

.add-sort-field {
  cursor: pointer;
}
</style>
