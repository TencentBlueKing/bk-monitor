<template>
  <t-popup
    class="common-filter-popper"
    :visible="popoverVisible"
    placement="bottom-left"
    trigger="click"
    :overlay-inner-style="{ padding: '0', background: '#fff', width: '682px', overflow: 'hidden' }"
    @visible-change="handleVisibleChange"
  >
    <slot name="trigger">
      <div class="operation-icon">
        <span :class="['bklog-icon bklog-shezhi setting-icon']"></span>
        {{ $t('设置筛选') }}
      </div>
    </slot>
    <template #content>
      <div class="bklog-filter-setting-panel">
      <div
        class="bklog-common-field-filter fields-container"
        :class="{ 'is-start-text-ellipsis': isStartTextEllipsis }"
      >
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
            <div class="common-filter-search">
              <t-input
                ref="commonFilterSearchInputRef"
                v-model="searchKeyword"
                clearable
                borderless
                :placeholder="$t('请输入关键字')"
              >
                <template #prefix-icon>
                  <span class="bk-icon icon-search left-icon"></span>
                </template>
              </t-input>
            </div>
            <ul
                v-if="shadowTotal.length"
                class="select-list"
              >
                <li
                  v-for="item in shadowTotal"
                  :key="item.field_name"
                  style="cursor: pointer"
                  class="select-item"
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
                    v-log-overflow-tips="{ content: `${item.query_alias || item.field_name}(${item.field_name})` }"
                    class="display-container rtl-text"
                    :dir="textDir"
                  >
                    <bdi class="field-alias">{{ item.first_name }}</bdi>
                    <bdi
                      v-if="item.first_name !== item.last_name"
                      class="field-name"
                      >({{ item.last_name }})</bdi
                    >
                  </div>
                  <span class="icon bklog-icon bklog-filled-right-arrow"></span>
                </li>
              </ul>
              <bk-exception
                v-else
                style="justify-content: center; height: 260px"
                scene="part"
                type="500"
              >
                搜索为空
              </bk-exception>
          </div>
          <div class="sort-icon">
            <span class="icon bklog-icon bklog-double-arrow"></span>
          </div>
          <div class="visible-fields-list">
            <div class="title">
              <span>{{ $t('常驻筛选') + '(' + shadowVisible.length + ')' }}</span>
              <!-- <span
                class="icon bklog-icon bklog-info-fill"
                v-log-tooltip="$t('支持拖拽更改顺序，从上向下对应列表列从左到右顺序')"
              ></span> -->
              <span
                class="clear-all text-action"
                @click="deleteAllField"
                >{{ $t('清空') }}</span
              >
            </div>
            <vue-draggable
              v-model="shadowVisible"
              class="select-list permanent-list"
              item-key="field_name"
              tag="ul"
              handle=".bklog-ketuodong"
              ghost-class="sortable-ghost-class"
              :animation="150"
            >
              <template #item="{ element: item, index }">
                <li class="select-item">
                  <span class="icon bklog-icon bklog-ketuodong"></span>
                  <span
                    :style="{
                      backgroundColor: item.is_full_text ? false : getFieldIconColor(item.field_type),
                      color: item.is_full_text ? false : getFieldIconTextColor(item.field_type),
                    }"
                    :class="[item.is_full_text ? 'full-text' : getFieldIcon(item.field_type), 'field-type-icon']"
                  >
                  </span>
                  <div
                    v-log-overflow-tips="{ content: `${item.query_alias || item.field_name}(${item.field_name})` }"
                    class="display-container rtl-text"
                  >
                    <span class="field-alias">{{ item.query_alias || item.field_name }}</span>
                    <span class="field-name">({{ item.field_name }})</span>
                  </div>
                  <span
                    class="bk-icon icon-close-circle-shape delete"
                    @click="deleteField(item, index)"
                  ></span>
                </li>
              </template>
            </vue-draggable>
          </div>
        </div>
      </div>
      <div class="bklog-common-field-filter fields-button-container">
        <t-button
          class="mr10"
          :loading="isLoading"
          :theme="'primary'"
          type="submit"
          @click="confirmModifyFields"
        >
          {{ $t('确定') }}
        </t-button>
        <t-button
          :theme="'default'"
          type="submit"
          @click="cancelModifyFields"
        >
          {{ $t('取消') }}
        </t-button>
      </div>
      </div>
    </template>
  </t-popup>
</template>
<script setup>
  import { ref, computed, nextTick } from 'vue';

  import { getRegExp } from '@/shared/lib/util';
  import useLocale from '@/shared/composables/use-locale';
  import useStore from '@/shared/composables/use-store';
  import { Input as TInput, Popup as TPopup } from 'tdesign-vue-next';
  import VueDraggable from 'vuedraggable-vue3';

  import { excludesFields } from '../utils/const.common.ts';
  import { BK_LOG_STORAGE } from '@/app/state/store.type.ts';
  // 获取 store
  const store = useStore();
  const { $t } = useLocale();
  const searchKeyword = ref('');
  const popoverVisible = ref(false);
  const isStartTextEllipsis = computed(() => store.state.storage[BK_LOG_STORAGE.TEXT_ELLIPSIS_DIR] === 'start');

  // 定义响应式数据
  const isLoading = ref(false);
  const fieldList = computed(() => {
    return store.getters.filteredFieldList;
  });

  const filterFieldsList = computed(() => {
    if (Array.isArray(store.state.retrieve.catchFieldCustomConfig?.filterSetting)) {
      return store.state.retrieve.catchFieldCustomConfig?.filterSetting ?? [];
    }

    return [];
  });

  const textDir = computed(() => {
    const textEllipsisDir = store.state.storage[BK_LOG_STORAGE.TEXT_ELLIPSIS_DIR];
    return textEllipsisDir === 'start' ? 'rtl' : 'ltr';
  });

  const shadowTotal = computed(() => {
    const reg = getRegExp(searchKeyword.value);
    const filterFn = field =>
      !shadowVisible.value.some(shadowField => shadowField.field_name === field.field_name) &&
      field.field_type !== '__virtual__' &&
      !excludesFields.includes(field.field_name) &&
      (reg.test(field.field_name) || reg.test(field.query_alias ?? ''));

    const mapFn = item =>
      Object.assign({}, item, {
        first_name: item.query_alias || item.field_name,
        last_name: item.field_name,
      });

    return fieldList.value.filter(filterFn).map(mapFn);
  });

  const shadowVisible = ref([]);

  // 计算属性
  const toSelectLength = computed(() => {
    return shadowTotal.value.length;
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

  // 新建提交逻辑
  const handleCreateRequest = async () => {
    const param = {
      filterSetting: shadowVisible.value,
      filterAddition: [],
    };
    isLoading.value = true;

    store.dispatch('userFieldConfigChange', param).finally(() => {
      isLoading.value = false;
    });
  };

  const hidePopover = () => {
    popoverVisible.value = false;
  };

  const confirmModifyFields = async () => {
    handleCreateRequest();
    hidePopover();
  };

  const cancelModifyFields = () => {
    hidePopover();
  };

  const addField = fieldInfo => {
    shadowVisible.value.push(fieldInfo);
  };

  const deleteField = (fieldName, index) => {
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

  const setDefaultFilterList = () => {
    shadowVisible.value = [];
    shadowVisible.value.push(...filterFieldsList.value);
  };

  const commonFilterSearchInputRef = ref(null);
  const handlePopoverShow = () => {
    setDefaultFilterList();
    nextTick(() => {
      commonFilterSearchInputRef.value?.focus();
    });
  };
  const handleVisibleChange = visible => {
    popoverVisible.value = visible;
    if (visible) {
      handlePopoverShow();
    }
  };
</script>

<style lang="scss">
  @use '../../../../../shared/styles/mixins/scroller' as *;

  .bklog-filter-setting-panel {
    width: 682px;
    background: #fff;
  }

  .bklog-common-field-filter {
    .fields-list-container {
      display: flex;
      padding: 0;

      .total-fields-list,
      .visible-fields-list {
        width: 320px;
        height: 344px;
        border: 1px solid #dcdee5;
        border-bottom: none;

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
          padding: 0 16px;
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
          overflow: hidden;
          box-sizing: border-box;

          .t-input__wrap,
          .t-input {
            height: 32px;
            background: transparent;
            border: 0;
            border-bottom: 1px solid #eaebf0;
            border-radius: 0;
            box-shadow: none;
          }

          .left-icon {
            color: #979ba5;
          }
        }

        .select-list {
          height: 255px;
          padding: 8px 0;
          overflow: auto;

          @include scroller;

          .select-item {
            display: flex;
            align-items: center;
            width: 100%;
            height: 32px;
            padding: 0 16px;
            line-height: 32px;
            cursor: pointer;

            .bklog-ketuodong {
              margin-right: 4px;
              width: 18px;
              font-size: 14px;
              color: #4d4f56;
              text-align: left;
              cursor: move;
            }

            &.sortable-ghost-class {
              background: #eaf3ff;
              transition: background 0.2s linear;
            }

            &:hover {
              background: #eaf3ff;
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

            .display-container {
              overflow: hidden;
              text-overflow: ellipsis;
              white-space: nowrap;

              .field-alias {
                display: inline;
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
      }

      .total-fields-list {
        border-right: none;
      }

      .visible-fields-list {
        width: 320px;
        border-left: none;

        .permanent-list {
          /* stylelint-disable-next-line declaration-no-important */
          height: 290px !important;
        }
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
          right: 4px;
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
        }

        .delete:hover {
          color: #979ba5;
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
          color: #989ca5;

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
      border: 1px solid #dcdee5;
      border-radius: 0 0 2px 2px;
    }
  }

  .common-filter-popper {
    .setting-icon {
      font-size: 16px;
    }
  }
</style>
