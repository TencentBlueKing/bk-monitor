<template>
  <div>
    <vue-draggable
      v-bind="dragOptions"
      class="custom-select-list"
      v-model="sortList"
    >
      <transition-group>
        <li
          class="custom-select-item"
          :key="dtEventTimeStampSort?.key"
        >
          <span style="width:18px"></span>
          <div 
            v-bk-tooltips="{
              allowHTML:true,
              placement:'top',
              content: $t('综合时间排序,是基于：dtEventTimeStamp、gesIndex、iterationIndex 3个字段的排序结果'),
            }" 
            class="table-sort-option-time"
          >
            <span>
              {{$t('综合时间排序')}}
              <span class="badge" >{{ totalTimeCount }}</span>
            </span>
          </div>
          <bk-select
            style="width: 77px"
            v-model="dtEventTimeStampSort.sorts[1]"
            :placeholder="$t('请选择')"
          >
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
            style="width: 14px"
          ></span>
        </li>
        <li
          v-for="({ key, sorts }, index) in showFieldList"
          class="custom-select-item"
          :key="key"
        >
          <span class="icon bklog-icon bklog-ketuodong"></span>
          <bk-select
            style="width: 174px"
            class="rtl-text"
            v-model="sorts[0]"
            auto-focus
            searchable
          >
            <!-- bklog-v3-popover-tag 不要乱加，这里用来判定是否为select 弹出，只做标识，不做样式作用 -->
            <div
              class="table-sort-option-container"
              :class="{ 'is-start-text-ellipsis': isStartTextEllipsis }"
            >
              <bk-option
                v-for="option in selectList"
                class="custom-option bklog-v3-popover-tag"
                :disabled="option.disabled"
                :id="option.field_name"
                :key="option.field_name"
                :name="option.field_name"
              >
                <div class="custom-option-item bklog-v3-popover-tag">
                  <span
                    :style="{
                      backgroundColor: option.is_full_text ? false : getFieldIconColor(option.field_type),
                      color: option.is_full_text ? false : getFieldIconTextColor(option.field_type),
                    }"
                    :class="[option.is_full_text ? 'full-text' : getFieldIcon(option.field_type), 'field-type-icon']"
                  >
                  </span>
                  <div
                    v-if="option.query_alias"
                    class="display-container rtl-text"
                    v-bk-overflow-tips="{ placement: 'right' }"
                  >
                    <span class="field-alias">{{ option.query_alias || option.field_name }}</span>
                    <span class="field-name">({{ option.field_name }})</span>
                  </div>
                  <div 
                    v-else 
                    class="display-container rtl-text" 
                    v-bk-overflow-tips="{ placement: 'right' }"
                  >
                    <span class="field-name">{{ option.field_name }}</span>
                  </div>
                </div>
              </bk-option>
            </div>
          </bk-select>
          <bk-select
            style="width: 77px"
            v-model="sorts[1]"
            :placeholder="$t('请选择')"
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
      ><span style="margin-left: 4px; font-size: 12px">{{ $t('添加排序字段') }}</span></span
    >
  </div>
</template>
<script setup lang="ts">
  import { computed, ref, defineExpose, watch } from 'vue';
  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';
  import VueDraggable from 'vuedraggable';

  import { deepClone, random } from '../../../../common/util';
  import { BK_LOG_STORAGE } from '../../../../store/store.type';
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
  const { $t } = useLocale();
  const isStartTextEllipsis = computed(() => store.state.storage[BK_LOG_STORAGE.TEXT_ELLIPSIS_DIR] === 'start');
  const fieldTypeMap = computed(() => store.state.globals.fieldTypeMap);
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
  const sortList = ref<{ key: string; sorts: string[] }[]>([]);

  const shadowSort = computed(() => sortList.value.map(e => e.sorts));
  const fieldList = computed(() => store.state.indexFieldInfo.fields);
  const dtEventTimeStampSort = computed(() => {
    return sortList.value.find(e => e.sorts[0] === 'dtEventTimeStamp') || { key: random(8), sorts: ['dtEventTimeStamp', 'desc'] };
  });
  const showFieldList = computed(() => {
    return sortList.value.filter( e =>{
      return  isFieldHidden(e.sorts[0])
    })
  });
  const selectList = computed(() => {
    const filterFn = field => field.field_type !== '__virtual__'  && isFieldHidden(field.field_name);
    return fieldList.value.filter(filterFn).map(field => {
      return Object.assign({}, field, { disabled: shadowSort.value.some(item => item[0] === field.field_name) });
    });
  });
  const totalTimeCount = computed(()=>{
    const requiredFields = ['gseIndex', 'iterationIndex','dtEventTimeStamp'];
    return fieldList.value.filter(field =>{
      if (requiredFields.includes(field.field_name)) {
        return true;
      }
    }).length;
  })
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
  const isFieldHidden = (fieldName) => {
    const hiddenFields = ['gseIndex', 'iterationIndex','dtEventTimeStamp'];
    return !hiddenFields.includes(fieldName);
  };
  watch(
    () => [props.initData, props.shouldRefresh],
    ([newInitData, newShouldRefresh]) => {
      // 当有初始数据时，直接更新
      if (Array.isArray(newInitData) && newInitData.length) {
        sortList.value = deepClone(newInitData).map(sorts => ({ key: random(8), sorts }));
      } else {
        sortList.value = [];
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

  .table-sort-option-time{
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

    .badge{
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

  .bklog-circle-minus-filled{
    cursor: pointer;
  }
</style>
