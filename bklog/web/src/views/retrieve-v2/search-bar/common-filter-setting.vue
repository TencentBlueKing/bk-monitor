<template>
  <bk-popover
    ref="fieldsSettingPopperRef"
    animation="slide-toggle"
    placement="bottom"
    theme="light bk-select-dropdown"
    trigger="click"
    class="common-filter-popper"
  >
    <slot name="trigger">
      <div class="operation-icon">
        <span :class="['bklog-icon bklog-log-setting']"></span>
        设置筛选
      </div>
    </slot>
    <template #content>
      <div class="fields-container">
        <div class="fields-list-container">
          <div class="total-fields-list">
            <div class="title">
              <span>{{ $t('待选列表') + '(' + toSelectLength + ')' }}</span>
              <span
                class="text-action add-all"
                @click="addAllField"
                >{{ $t('全部添加') }}</span
              >
            </div>
            <ul class="select-list">
              <li
                v-for="item in shadowTotal"
                style="cursor: pointer"
                class="select-item"
                v-show="!item.is_display"
                :key="item.field_name"
                @click="addField(item)"
              >
                <span
                  :style="{ backgroundColor: item.is_full_text ? false : getFieldIconColor(item.field_type) }"
                  :class="[item.is_full_text ? 'full-text' : getFieldIcon(item.field_type), 'field-type-icon']"
                >
                </span>
                <span class="field-alias">{{ item.field_alias || item.field_name }}</span>
                <span class="field-name">({{ item.field_name }})</span>
                <span class="icon bklog-icon bklog-filled-right-arrow"></span>
              </li>
            </ul>
          </div>
          <div class="sort-icon">
            <span class="icon bklog-icon bklog-double-arrow"></span>
          </div>
          <div class="visible-fields-list">
            <div class="title">
              <span>{{ $t('常驻筛选') + '(' + shadowVisible.length + ')' }}</span>
              <span
                class="icon bklog-icon bklog-info-fill"
                v-bk-tooltips="$t('支持拖拽更改顺序，从上向下对应列表列从左到右顺序')"
              ></span>
              <span
                class="clear-all text-action"
                @click="deleteAllField"
                >{{ $t('清空') }}</span
              >
            </div>
            <vue-draggable
              v-bind="dragOptions"
              class="select-list"
              v-model="shadowVisible"
            >
              <transition-group>
                <li
                  v-for="(item, index) in shadowVisible"
                  class="select-item"
                  :key="item.field_name"
                >
                  <span class="icon bklog-icon bklog-drag-dots"></span>
                  <span
                    :style="{ backgroundColor: item.is_full_text ? false : getFieldIconColor(item.field_type) }"
                    :class="[item.is_full_text ? 'full-text' : getFieldIcon(item.field_type), 'field-type-icon']"
                  >
                  </span>
                  <span class="field-alias">{{ item.field_alias || item.field_name }}</span>
                  <span class="field-name">({{ item.field_name }})</span>
                  <span
                    class="bk-icon icon-close-circle-shape delete"
                    @click="deleteField(item, index)"
                  ></span>
                </li>
              </transition-group>
            </vue-draggable>
          </div>
        </div>
      </div>
      <div class="fields-button-container">
        <bk-button
          class="mr10"
          :theme="'primary'"
          type="submit"
          @click="confirmModifyFields"
        >
          {{ $t('保存') }}
        </bk-button>
        <bk-button
          :theme="'default'"
          type="submit"
          @click="cancelModifyFields"
        >
          {{ $t('取消') }}
        </bk-button>
      </div>
    </template>
  </bk-popover>
</template>
<script setup>
  import { ref } from 'vue';

  // 定义响应式数据
  const rtxList = ref([
    { name: 'zhangsan', code: 1 },
    { name: 'lisi', code: 2 },
    { name: 'laowang', code: 3 },
    { name: 'zhaosi', code: 4 },
    { name: 'liuer', code: 5 },
    { name: 'zhousan', code: 6 },
    { name: 'huangwu', code: 7 },
    { name: 'tianliu', code: 8 },
  ]);

  const rtxValue = ref([1, 5, 7]);
  const sourceLength = ref(0);
  const targetLength = ref(0);

  // 定义方法
  const change = (sourceList, targetList, targetValueList) => {
    sourceLength.value = sourceList.length;
    targetLength.value = targetList.length;
    console.log(sourceList);
    console.log(targetList);
    console.log(targetValueList);
  };

  const addAll = () => {
    const list = [];
    rtxList.value.forEach(item => {
      list.push(item.code);
    });
    rtxValue.value = [...list];
  };

  const removeAll = () => {
    rtxValue.value = [];
  };
</script>
<script setup>
  import { ref, computed, onMounted } from 'vue';
  import useStore from '@/hooks/use-store';
  import { deepClone } from '@/components/monitor-echarts/utils';
  import VueDraggable from 'vuedraggable';
  import { excludesFields } from './const.common';

  // 获取 store
  const store = useStore();

  // 定义响应式数据
  const isLoading = ref(false);
  const showFieldAlias = ref(localStorage.getItem('showFieldAlias') === 'true');
  const fieldList = computed(() => {
    return store.state.indexFieldInfo.fields;
  });

  const shadowTotal = computed(() => {
    const filterFn = field => field.field_type !== '__virtual__' && !excludesFields.includes(field.field_name);
    return fieldList.value.filter(filterFn);
  });

  const shadowVisible = ref([]);
  const dragOptions = ref({
    animation: 150,
    tag: 'ul',
    handle: '.bklog-drag-dots',
    'ghost-class': 'sortable-ghost-class',
  });

  // 计算属性
  const toSelectLength = computed(() => {
    return shadowTotal.value.length - shadowVisible.value.length;
  });

  const fieldAliasMap = computed(() => {
    return (store.state.indexFieldInfo.fields ?? []).reduce(
      (out, field) => ({ ...out, [field.field_name]: field.field_alias || field.field_name }),
      {},
    );
  });

  const fieldTypeMap = computed(() => store.state.globals.fieldTypeMap);
  const getFieldIcon = fieldType => {
    return fieldTypeMap.value?.[fieldType] ? fieldTypeMap.value?.[fieldType]?.icon : 'bklog-icon bklog-unkown';
  };

  const getFieldIconColor = type => {
    return fieldTypeMap.value?.[type] ? fieldTypeMap.value?.[type]?.color : '#EAEBF0';
  };

  const confirmModifyFields = async () => {
    // todo 提交功能还未做
    // if (shadowVisible.value.length === 0) {
    //   store.$messageWarn(store.state.$t('显示字段不能为空'));
    //   return;
    // }
    // try {
    //   const confirmConfigData = {
    //     display_fields: shadowVisible.value,
    //   };
    //   await store.$http.request('retrieve/postFieldsConfig', {
    //     data: {
    //       index_set_id: store.$route.params.indexId,
    //       index_set_ids: store.getters.unionIndexList,
    //       index_set_type: store.getters.isUnionSearch ? 'union' : 'single',
    //       ...confirmConfigData,
    //     },
    //   });
    //   // 触发确认事件
    //   const emit = defineEmits(['confirm']);
    //   emit('confirm', shadowVisible.value, showFieldAlias.value);
    // } catch (error) {
    //   console.warn(error);
    // }
  };

  const fieldsSettingPopperRef = ref('');
  const cancelModifyFields = () => {
    fieldsSettingPopperRef?.value.instance.hide();
  };

  const addField = fieldInfo => {
    fieldInfo.is_display = true;
    shadowVisible.value.push(fieldInfo);
  };

  const deleteField = (fieldName, index) => {
    shadowVisible.value.splice(index, 1);
    const arr = shadowTotal.value;
    for (let i = 0; i < arr.length; i++) {
      if (arr[i].field_name === fieldName) {
        arr[i].is_display = false;
        return;
      }
    }
  };

  const addAllField = () => {
    shadowTotal.value.forEach(fieldInfo => {
      if (!fieldInfo.is_display) {
        fieldInfo.is_display = true;
        shadowVisible.value.push(fieldInfo);
      }
    });
  };

  const deleteAllField = () => {
    shadowTotal.value.forEach(fieldInfo => {
      fieldInfo.is_display = false;
    });
    shadowVisible.value = [];
  };
</script>

<style lang="scss">
  @import '../../../scss/mixins/scroller';

  .fields-list-container {
    display: flex;
    width: 723px;
    padding: 0 10px 14px 10px;

    .total-fields-list,
    .visible-fields-list,
    .sort-fields-list {
      width: 330px;
      height: 268px;
      border: 1px solid #dcdee5;

      .text-action {
        font-size: 12px;
        color: #3a84ff;
        cursor: pointer;
      }

      .title {
        position: relative;
        display: flex;
        align-items: center;
        height: 41px;
        padding: 0 16px;
        line-height: 40px;
        color: #313238;
        border-bottom: 1px solid #dcdee5;

        .bklog-info-fill {
          margin-left: 8px;
          font-size: 14px;
          color: #979ba5;
          outline: none;
        }

        .add-all,
        .clear-all {
          position: absolute;
          top: 0;
          right: 16px;
        }
      }

      .select-list {
        height: 223px;
        padding: 4px 0;
        overflow: auto;

        @include scroller;

        .select-item {
          display: flex;
          align-items: center;
          width: 100%;
          height: 32px;
          padding: 0 12px;
          text-overflow: ellipsis;
          white-space: nowrap;
          cursor: pointer;

          .bklog-drag-dots {
            width: 16px;
            font-size: 14px;
            color: #979ba5;
            text-align: left;
            cursor: move;
            opacity: 0;
            transition: opacity 0.2s linear;
          }

          &.sortable-ghost-class {
            background: #eaf3ff;
            transition: background 0.2s linear;
          }

          &:hover {
            background: #eaf3ff;
            transition: background 0.2s linear;

            .bklog-drag-dots {
              opacity: 1;
              transition: opacity 0.2s linear;
            }
          }

          .field-type-icon {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 16px;
            height: 16px;
            background: #dcdee5;
            border-radius: 2px;

            &.full-text {
              position: relative;

              &::after {
                position: absolute;
                top: 1px;
                left: 5px;
                width: 4px;
                height: 4px;
                content: '*';
              }
            }

            &.bklog-ext {
              font-size: 8px;
            }
          }

          .field-alias {
            padding: 0 4px;
            font-size: 12px;
            line-height: 20px;
            color: #63656e;
            letter-spacing: 0;
          }

          .field-name {
            font-size: 12px;
            font-weight: 400;
            line-height: 20px;
            color: #9b9da1;
            letter-spacing: 0;
          }
        }
      }
    }

    /* stylelint-disable-next-line no-descending-specificity */
    .total-fields-list .select-list .select-item {
      .field-name {
        width: calc(100% - 24px);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .bklog-filled-right-arrow {
        width: 24px;
        font-size: 16px;
        color: #3a84ff;
        text-align: right;
        cursor: pointer;
        opacity: 0;
        transition: opacity 0.2s linear;
        transform: scale(0.5);
        transform-origin: right center;
      }

      &:hover .bklog-filled-right-arrow {
        opacity: 1;
        transition: opacity 0.2s linear;
      }
    }

    /* stylelint-disable-next-line no-descending-specificity */
    .visible-fields-list .select-list .select-item {
      .field-name {
        // 16 38
        width: calc(100% - 30px);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .delete {
        font-size: 16px;
        color: #c4c6cc;
        text-align: right;
        cursor: pointer;
      }
    }

    .sort-fields-list {
      flex-shrink: 0;

      .sort-list-header {
        display: flex;
        align-items: center;
        height: 31px;
        font-size: 12px;
        line-height: 30px;
        background: rgba(250, 251, 253, 1);
        border-bottom: 1px solid rgba(221, 228, 235, 1);
      }

      /* stylelint-disable-next-line no-descending-specificity */
      .select-list .select-item {
        .field-name {
          // 16 42 50 38
          width: calc(100% - 146px);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .status {
          font-weight: 700;

          &.icon-arrows-down-line {
            color: #ea3636;
          }

          &.icon-arrows-up-line {
            color: #2dcb56;
          }
        }

        .option {
          width: 50px;
          margin: 0 8px;
          color: #3a84ff;
        }

        .delete {
          font-size: 16px;
          color: #c4c6cc;
          text-align: right;
          cursor: pointer;
        }
      }
    }

    .sort-icon {
      display: flex;
      flex-shrink: 0;
      align-items: center;
      justify-content: center;
      width: 35px;

      .bklog-double-arrow {
        font-size: 12px;
        color: #989ca5;
      }
    }
  }

  .fields-button-container {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    width: 100%;
    height: 51px;
    padding: 0 24px;
    background-color: #fafbfd;
    border-top: 1px solid #dcdee5;
    border-radius: 0 0 2px 2px;
  }
</style>
