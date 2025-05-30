<template>
  <div>
    <div class="bklog-common-field-filter fields-container">
      <div class="fields-list-container">
        <div class="total-fields-list">
          <div class="title">
            <span>{{ $t('待选字段') + '(' + toSelectLength + ')' }}</span>
            <span
              class="text-action add-all"
              @click="addAllField"
              >{{ $t('全部添加') }}</span
            >
          </div>
          <div class="common-filter-search">
            <bk-input
              v-model="searchKeyword"
              :clearable="true"
              :placeholder="$t('请输入关键字')"
              behavior="simplicity"
              left-icon="bk-icon icon-search"
            ></bk-input>
          </div>
          <ul class="select-list">
            <li
              v-for="item in shadowTotal"
              style="cursor: pointer"
              class="select-item bklog-v3-popover-tag"
              :key="item.field_name"
              @click="addField(item)"
            >
              <span
                :style="{
                  backgroundColor: item.is_full_text ? false : getFieldIconColor(item.field_type),
                  color: item.is_full_text ? false : getFieldIconTextColor(item.field_type),
                }"
                :class="[item.is_full_text ? 'full-text' : getFieldIcon(item.field_type), 'field-type-icon']"
              >
              </span>
              <div
                class="display-container rtl-text"
                v-bk-overflow-tips="{ content: `${item.query_alias || item.field_name}(${item.field_name})` }"
                :dir="textDir"
              >
                <bdi>
                  <span class="field-alias">{{ item.first_name }}</span>
                  <span
                    class="field-name"
                    v-if="item.first_name !== item.last_name"
                  >
                    ({{ item.last_name }})
                  </span>
                </bdi>
              </div>
              <span class="icon bklog-icon bklog-filled-right-arrow"></span>
            </li>
            <bk-exception
              v-if="emptyType"
              :type="emptyType"
              scene="part"
            />
          </ul>
        </div>
        <div class="sort-icon">
          <span class="icon bklog-icon bklog-double-arrow"></span>
        </div>
        <div class="visible-fields-list">
          <div class="title">
            <span>{{ $t('已选字段') + '(' + shadowVisible.length + ')' }}</span>
            <!-- <span
                class="icon bklog-icon bklog-info-fill"
                v-bk-tooltips="$t('支持拖拽更改顺序，从上向下对应列表列从左到右顺序')"
              ></span> -->
            <span
              class="clear-all text-action"
              @click="deleteAllField"
              >{{ $t('清空') }}</span
            >
          </div>
          <vue-draggable
            v-bind="dragOptions"
            style="height: 295px"
            class="select-list"
            v-model="shadowVisible"
          >
            <transition-group>
              <li
                v-for="(item, index) in shadowVisible"
                class="select-item"
                :key="item.field_name"
                @click="e => deleteField(e, item, index)"
              >
                <span
                  class="icon bklog-icon bklog-ketuodong"
                  data-del-disabled
                ></span>
                <span
                  :style="{
                    backgroundColor: item.is_full_text ? false : getFieldIconColor(item.field_type),
                    color: item.is_full_text ? false : getFieldIconTextColor(item.field_type),
                  }"
                  :class="[item.is_full_text ? 'full-text' : getFieldIcon(item.field_type), 'field-type-icon']"
                >
                </span>
                <div
                  class="display-container rtl-text"
                  :dir="textDir"
                  v-bk-overflow-tips="{ content: `${item.query_alias || item.field_name}(${item.field_name})` }"
                >
                  <bdi>
                    <span class="field-alias">{{ item.first_name }}</span>
                    <span
                      class="field-name"
                      v-if="item.first_name !== item.last_name"
                    >
                      ({{ item.last_name }})
                    </span>
                  </bdi>
                </div>
                <span class="bk-icon icon-close-circle-shape delete"></span>
              </li>
            </transition-group>
          </vue-draggable>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup>
  import { ref, computed, watch, defineProps, defineExpose } from 'vue';

  import { formatHierarchy } from '@/common/field-resolver';
  import { getRegExp } from '@/common/util';
  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';
  import VueDraggable from 'vuedraggable';
  import { BK_LOG_STORAGE } from '@/store/store.type';

  // 获取 store
  const store = useStore();
  const { $t } = useLocale();
  const searchKeyword = ref('');

  const props = defineProps({
    initData: {
      type: Array,
      default: () => [],
    },
  });
  // 定义响应式数据
  const fieldList = computed(() => {
    return formatHierarchy(store.state.indexFieldInfo.fields);
  });

  /** 将 fieldList 数组转换成 kv 结构(k-field_name,v-fieldItem) ,控制字段渲染顺序使用 */
  const fieldListMap = computed(() => {
    return fieldList.value.reduce((prev, curr) => {
      prev[curr.field_name] = curr;
      return prev;
    }, {});
  });

  const shadowTotal = computed(() => {
    const reg = getRegExp(searchKeyword.value);
    const filterFn = field =>
      !shadowVisible.value.some(shadowField => shadowField.field_name === field.field_name) &&
      field.field_type !== '__virtual__' &&
      (reg.test(field.field_name) || reg.test(field.query_alias ?? ''));
    const mapFn = item =>
      Object.assign({}, item, {
        first_name: item.query_alias || item.field_name,
        last_name: item.field_name,
      });

    return fieldList.value.filter(filterFn).map(mapFn);
  });

  const emptyType = computed(() => {
    if (!!shadowTotal?.value?.length) {
      return '';
    }
    if (searchKeyword.value == '') {
      return 'empty';
    }
    return 'search-empty';
  });

  const shadowVisible = ref([]);

  const dragOptions = ref({
    animation: 150,
    tag: 'ul',
    handle: '.bklog-ketuodong',
    'ghost-class': 'sortable-ghost-class',
  });

  // 计算属性
  const toSelectLength = computed(() => {
    return shadowTotal.value.length;
  });

  const textDir = computed(() => {
    const textEllipsisDir = store.state.storage[BK_LOG_STORAGE.TEXT_ELLIPSIS_DIR];
    return textEllipsisDir === 'start' ? 'rtl' : 'ltr';
  });

  const fieldTypeMap = computed(() => store.state.globals.fieldTypeMap);
  const getFieldIcon = fieldType => {
    return fieldTypeMap.value?.[fieldType] ? fieldTypeMap.value?.[fieldType]?.icon : 'bklog-icon bklog-unkown';
  };

  const getFieldIconColor = type => {
    return fieldTypeMap.value?.[type] ? fieldTypeMap.value?.[type]?.color : '#EAEBF0';
  };

  const getFieldIconTextColor = type => {
    return fieldTypeMap.value?.[type]?.textColor;
  };

  const addField = fieldInfo => {
    shadowVisible.value.push(fieldInfo);
  };

  const deleteField = (e, fieldName, index) => {
    if (e.target.hasAttribute('data-del-disabled')) {
      return;
    }

    shadowVisible.value.splice(index, 1);
  };

  const addAllField = () => {
    shadowTotal.value.forEach(fieldInfo => {
      if (!shadowVisible.value.includes(fieldInfo)) {
        shadowVisible.value.push(fieldInfo);
      }
    });
  };

  const deleteAllField = () => {
    shadowVisible.value = [];
  };
  watch(
    () => props.initData,
    val => {
      if (val.length) {
        const mapFn = item =>
          Object.assign({}, item, {
            first_name: item.query_alias || item.field_name,
            last_name: item.field_name,
          });
        shadowVisible.value = val
          .map(fieldName => fieldListMap.value[fieldName])
          .filter(Boolean)
          .map(mapFn);
      } else {
        shadowVisible.value = [];
      }
    },
    { immediate: true, deep: true },
  );
  defineExpose({ shadowVisible });
</script>

<style lang="scss">
  @import '../../../../scss/mixins/scroller';

  .bklog-common-field-filter {
    .fields-list-container {
      display: flex;
      padding: 0;

      .total-fields-list,
      .visible-fields-list,
      .sort-fields-list {
        width: 320px;
        height: 344px;
        border: none;

        .text-action {
          font-size: 12px;
          color: #3a84ff;
          cursor: pointer;
        }

        .title {
          position: relative;
          display: flex;
          align-items: center;
          height: 44px;
          padding: 0px 8px 0px 16px;
          font-weight: 700;
          line-height: 40px;
          color: #313238;
          background: #fafbfd;
          border-top: 1px solid #dcdee5;
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
            font-weight: normal;
          }
        }

        .common-filter-search {
          height: 32px;
          padding: 0 8px;
          margin-top: 5px;

          .bk-form-control {
            .left-icon {
              color: #979ba5;
            }
          }
        }

        .select-list {
          height: 255px;
          padding: 8px;
          overflow: auto;

          @include scroller;

          .select-item {
            display: flex;
            align-items: center;
            width: 100%;
            height: 32px;
            padding: 0 8px;
            font-family: Roboto-Regular;
            line-height: 32px;
            cursor: pointer;

            .bklog-ketuodong {
              margin-right: 4px;
              width: 18px;
              font-size: 18px;
              color: hsl(223, 7%, 62%);
              text-align: left;
              cursor: move;
            }

            &.sortable-ghost-class {
              background: #eaf3ff;
              transition: background 0.2s linear;
            }

            &:hover {
              background: hsl(220, 100%, 97%);
            }

            .field-type-icon {
              display: inline-flex;
              align-items: center;
              justify-content: center;
              width: 16px;
              height: 16px;
              font-size: 14px;
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

            .display-container {
              overflow: hidden;
              text-overflow: ellipsis;
              white-space: nowrap;

              .field-alias {
                display: inline;
                padding: 0 4px;
                font-size: 12px;
                line-height: 20px;
                color: #313238;
                letter-spacing: 0;
              }

              .field-name {
                font-size: 12px;
                font-weight: 400;
                line-height: 20px;
                color: #757880;
                letter-spacing: 0;
              }
            }
          }

          .bk-exception {
            justify-content: center;
            height: 100%;
          }
        }
      }

      .total-fields-list {
        border-right: none;
        border-left: 1px solid #dcdee5;
      }

      .visible-fields-list {
        width: 264px;
        border-right: 1px solid #dcdee5;
        border-left: none;
      }

      /* stylelint-disable-next-line no-descending-specificity */
      .total-fields-list .select-list .select-item {
        position: relative;

        .display-container {
          width: calc(100% - 16px);
        }

        .bklog-filled-right-arrow {
          position: absolute;
          top: 8px;
          right: 8px;
          z-index: 10;
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

      /* stylelint-disable-next-line no-descending-specificity */
      .visible-fields-list .select-list .select-item {
        position: relative;

        .display-container {
          width: calc(100% - 38px);
        }

        .delete {
          position: absolute;
          top: 8px;
          right: 12px;
          display: none;
          font-size: 16px;
          color: #c4c6cc;
          text-align: right;
          cursor: pointer;
        }

        &:hover .delete {
          display: block;
          background-color: #f1f4ff;
        }
      }

      .sort-icon {
        display: flex;
        flex-shrink: 0;
        align-items: center;
        justify-content: center;
        width: 1px;
        background-color: #dcdee5;

        .bklog-double-arrow {
          position: absolute;

          display: flex;
          align-items: center;
          justify-content: center;

          width: 33px;
          height: 33px;
          font-size: 12px;
          color: #c4c6cc;

          pointer-events: none;
          background: #fafbfd;
          border-radius: 50%;
        }
      }
    }

    &.fields-button-container {
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
  }
</style>
