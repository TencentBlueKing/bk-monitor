<template>
  <div>
    <vue-draggable
      v-bind="dragOptions"
      class="custom-select-list"
      v-model="shadowSort"
    >
      <transition-group>
        <li
          v-for="(item, index) in shadowSort"
          class="custom-select-item"
          :key="item[0]"
        >
          <span class="icon bklog-icon bklog-drag-dots"></span>
          <bk-select
            style="width: 174px"
            v-model="item[0]"
            auto-focus
            filterable
          >
            <bk-option
              v-for="option in selectList"
              class="custom-option"
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
            v-model="item[1]"
          >
            <bk-option
              v-for="option in orderList"
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
      style="font-size: 14px; color: #3a84ff; margin-left: 20px"
      class="bklog-icon bklog-log-plus-circle-shape"
      @click="addTableItem()"
      ><span style="font-size: 12px; margin-left: 4px">添加排序字段</span></span
    >
  </div>
</template>
<script setup lang="ts">
  import { computed, ref, defineExpose, watch } from 'vue';

  import useStore from '@/hooks/use-store';
  import VueDraggable from 'vuedraggable';
  const props = defineProps({
    initData: {
      type: Array,
      default: () => [],
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
  const shadowSort = ref([]);
  const selectList = computed(() => {
    const data = store.state.indexFieldInfo.fields;
    const filterFn = field => field.field_type !== '__virtual__';
    return data.filter(filterFn);
  });
  const deleteTableItem = (val: number) => {
    shadowSort.value = shadowSort.value.slice(0, val).concat(shadowSort.value.slice(val + 1));
    console.log(val, shadowSort.value, 'shadowSort.value');
  };
  const addTableItem = () => {
    shadowSort.value.push(['', '']);
    console.log(shadowSort.value, 'shadowSort.value');
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
    () => props.initData,
    val => {
      if (val.length) {
        shadowSort.value = props.initData;
      } else {
        shadowSort.value = [];
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
      margin-bottom: 8px;
      justify-content: center;
      align-items: center;
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
