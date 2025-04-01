<template>
  <div>
    <vue-draggable
      v-bind="dragOptions"
      class="custom-select-list"
      v-model="shadowSort"
    >
      <transition-group>
        <li
          v-for="({ key, sorts }, index) in sortList"
          class="custom-select-item"
          :key="key"
        >
          <span class="icon bklog-icon bklog-drag-dots"></span>
          <bk-select
            style="width: 174px"
            v-model="sorts[0]"
            auto-focus
            filterable
          >
            <!-- bklog-v3-popover-tag 不要乱加，这里用来判定是否为select 弹出，只做标识，不做样式作用 -->
            <bk-option
              v-for="option in selectList"
              class="custom-option bklog-v3-popover-tag"
              :disabled="option.disabled"
              :id="option.field_name"
              :key="option.field_name"
              :name="option.field_name"
            >
              <div
                style="width: 130px"
                class="title-overflow"
                v-bk-overflow-tips="{ placement: 'right' }"
              >
                <span
                  :style="{
                    backgroundColor: option.is_full_text ? false : getFieldIconColor(option.field_type),
                    color: option.is_full_text ? false : getFieldIconTextColor(option.field_type),
                  }"
                  :class="[option.is_full_text ? 'full-text' : getFieldIcon(option.field_type), 'field-type-icon']"
                >
                </span>
                <span class="field-alias">{{ option.query_alias || option.field_name }}</span>
                <span class="field-name">({{ option.field_name }})</span>
              </div>
            </bk-option>
          </bk-select>
          <bk-select
            style="width: 75px"
            v-model="sorts[1]"
          >
            <!-- bklog-v3-popover-tag 不要乱加，这里用来判定是否为select 弹出，只做标识，不做样式作用 -->
            <bk-option
              v-for="option in orderList"
              class="bklog-v3-popover-tag"
              :id="option.id"
              :key="option.id"
              :name="option.name"
            >
            </bk-option>
          </bk-select>
          <span
            style="font-size: 14px; color: #c4c6cc"
            class="bklog-icon bklog-circle-minus-filled"
            @click="deleteTableItem(index)"
          ></span>
        </li>
      </transition-group>
    </vue-draggable>
    <span
      style="margin-left: 20px; font-size: 14px; color: #3a84ff"
      class="bklog-icon bklog-log-plus-circle-shape"
      @click="addTableItem()"
      ><span style="margin-left: 4px; font-size: 12px">添加排序字段</span></span
    >
  </div>
</template>
<script setup lang="ts">
  import { computed, ref, defineExpose, watch } from 'vue';

  import useStore from '@/hooks/use-store';
  import VueDraggable from 'vuedraggable';

  import { deepClone, random } from '../../../../common/util';
  const props = defineProps({
    initData: {
      type: Array,
      default: () => [],
    },
    shouldRefresh: {
      type: Boolean,
      default: false,
    },
  });
  const fieldTypeMap = computed(() => store.state.globals.fieldTypeMap);
  const dragOptions = {
    animation: 150,
    tag: 'ul',
    handle: '.bklog-drag-dots',
    'ghost-class': 'sortable-ghost-class',
  };
  const orderList = [
    { id: 'desc', name: '降序' },
    { id: 'asc', name: '升序' },
  ];
  const store = useStore();

  /** 新增变量处理v-for时需要使用的 key 字段，避免重复新建 VNode */
  const sortList = ref<{ key: string; sorts: string[] }[]>([]);

  const shadowSort = computed(() => sortList.value.map(e => e.sorts));
  const selectList = computed(() => {
    const data = store.state.indexFieldInfo.fields;
    const filterFn = field => field.field_type !== '__virtual__';
    return data.filter(filterFn).map(field => {
      return Object.assign({}, field, { disabled: shadowSort.value.some(item => item[0] === field.field_name) });
    });
  });

  const deleteTableItem = (val: number) => {
    sortList.value = sortList.value.slice(0, val).concat(sortList.value.slice(val + 1));
  };
  const addTableItem = () => {
    sortList.value.push({ key: random(8), sorts: ['', ''] });
  };
  const getFieldIconColor = type => {
    return fieldTypeMap.value?.[type] ? fieldTypeMap.value?.[type]?.color : '#EAEBF0';
  };
  const getFieldIconTextColor = type => {
    return fieldTypeMap.value?.[type]?.textColor;
  };
  const getFieldIcon = fieldType => {
    return fieldTypeMap.value?.[fieldType] ? fieldTypeMap.value?.[fieldType]?.icon : 'bklog-icon bklog-unkown';
  };
  watch(
    () => [props.initData, props.shouldRefresh],
    () => {
      if (props.shouldRefresh && props.initData.length) {
        sortList.value = deepClone(props.initData).map(sorts => ({ key: random(8), sorts }));
      } else {
        sortList.value = [];
      }
    },
    { immediate: true, deep: true },
  );
  defineExpose({ shadowSort });
</script>
<style lang="scss">
  .custom-select-list {
    .custom-select-item {
      display: flex;
      column-gap: 8px;
      align-items: center;
      justify-content: center;
      margin-bottom: 8px;

      .bklog-drag-dots {
        font-size: 18px;
        color: #979ba5;
      }
    }

    .title-overflow {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }
</style>
