<script setup lang="ts">
  import { ref, computed, watch } from 'vue';
  import useStore from '@/hooks/use-store';
  import { ConditionOperator } from '@/store/condition-operator';
  import useLocale from '@/hooks/use-locale';

  import CommonFilterSetting from './common-filter-setting.vue';
  import { FulltextOperator, FulltextOperatorKey, withoutValueConditionList } from './const.common';
  import { getOperatorKey, deepClone } from '@/common/util';
  import { operatorMapping, translateKeys } from './const-values';
  import useFieldEgges from './use-field-egges';
  import { debounce } from 'lodash';
  const { $t } = useLocale();
  const store = useStore();
  const debouncedHandleChange = debounce(() => handleChange(), 300);
  const filterFieldsList = computed(() => {
    if (Array.isArray(store.state.retrieve.catchFieldCustomConfig?.filterSetting)) {
      return store.state.retrieve.catchFieldCustomConfig?.filterSetting ?? [];
    }

    return [];
  });

  // 判定当前选中条件是否需要设置Value
  const isShowConditonValueSetting = operator => !withoutValueConditionList.includes(operator);

  const commonFilterAddition = computed({
    get() {
      const additionValue = JSON.parse(localStorage.getItem('commonFilterAddition'));
      // 将本地存储的JSON字符串解析为对象并创建映射
      const parsedValueMap = additionValue
        ? additionValue.value.reduce((acc, item) => {
            acc[item.field] = item.value;
            return acc;
          }, {})
        : {};
      // 如果本地存储的字段列表不为空，则将本地存储的字段列表与当前字段列表合并
      const filterAddition = (store.getters.common_filter_addition || []).map(commonItem => ({
        ...commonItem,
        value: parsedValueMap[commonItem.field] || commonItem.value,
      }));
      return filterFieldsList.value.map(item => {
        const matchingItem = filterAddition.find(addition => addition.field === item.field_name);
        return (
          matchingItem ?? {
            field: item.field_name || '',
            operator: '=',
            value: [],
            list: [],
          }
        );
      });
    },
    set(val) {
      const target = val.map(item => {
        if (!isShowConditonValueSetting(item.operator)) {
          item.value = [];
        }

        return item;
      });

      store.commit('retrieve/updateCatchFieldCustomConfig', {
        filterAddition: target,
      });
    },
  });
  watch(
    () => store.state.indexId,
    () => {
      const additionValue = JSON.parse(localStorage.getItem('commonFilterAddition'));
      if (additionValue?.indexId !== store.state.indexId) {
        localStorage.removeItem('commonFilterAddition');
      } else {
        const currentConfig = store.state.retrieve.catchFieldCustomConfig;
        const updatedConfig = { ...currentConfig, filterAddition: additionValue.value };
        store.commit('retrieve/updateCatchFieldCustomConfig', updatedConfig);
      }
    },
    { immediate: true },
  );
  const activeIndex = ref(-1);
  let requestTimer = null;
  const isRequesting = ref(false);

  const operatorDictionary = computed(() => {
    const defVal = {
      [getOperatorKey(FulltextOperatorKey)]: { label: $t('包含'), operator: FulltextOperator },
    };
    return {
      ...defVal,
      ...store.state.operatorDictionary,
    };
  });

  /**
   * 获取操作符展示文本
   * @param {*} item
   */
  const getOperatorLabel = item => {
    if (item.field === '_ip-select_') {
      return '';
    }

    const key = item.field === '*' ? getOperatorKey(`*${item.operator}`) : getOperatorKey(item.operator);
    if (translateKeys.includes(operatorMapping[item.operator])) {
      return $t(operatorMapping[item.operator] ?? item.operator);
    }

    return operatorMapping[item.operator] ?? operatorDictionary.value[key]?.label ?? item.operator;
  };

  const { requestFieldEgges } = useFieldEgges();
  const handleToggle = (visable, item, index) => {
    if (visable) {
      activeIndex.value = index;
      isRequesting.value = true;
      requestFieldEgges(
        item,
        null,
        resp => {
          if (typeof resp === 'boolean') {
            return;
          }
          commonFilterAddition.value[index].list = store.state.indexFieldInfo.aggs_items[item.field_name] ?? [];
        },
        () => {
          isRequesting.value = false;
        },
      );
    }
  };

  const handleInputVlaueChange = (value, item, index) => {
    activeIndex.value = index;
    isRequesting.value = true;
    requestFieldEgges(
      item,
      value,
      resp => {
        if (typeof resp === 'boolean') {
          return;
        }
        commonFilterAddition.value[index].list = store.state.indexFieldInfo.aggs_items[item.field_name] ?? [];
      },
      () => {
        isRequesting.value = false;
      },
    );
  };

  // 新建提交逻辑
  const updateCommonFilterAddition = async () => {
    try {
      const Additionvalue = deepClone(commonFilterAddition.value);
      const target = Additionvalue.map(item => {
        if (!isShowConditonValueSetting(item.operator)) {
          item.value = [];
        }
        item.value = [];
        return item;
      });

      const param = {
        filterAddition: target,
        isUpdate: true,
      };
      const res = await store.dispatch('userFieldConfigChange', param);
      const {
        data: { index_set_config },
      } = res;
      index_set_config.filterAddition = commonFilterAddition.value;
      store.commit('retrieve/updateCatchFieldCustomConfig', index_set_config);
    } catch (error) {
      console.error('Failed to change user field config:', error);
    }
  };

  const handleChange = () => {
    localStorage.setItem(
      'commonFilterAddition',
      JSON.stringify({
        indexId: store.state.indexId,
        value: commonFilterAddition.value,
      }),
    );
    updateCommonFilterAddition();
    store.dispatch('requestIndexSetQuery');
  };

  const focusIndex = ref(null);
  const handleRowFocus = (index, e) => {
    if (document.activeElement === e.target) {
      focusIndex.value = index;
    }
  };

  const handleRowBlur = () => {
    focusIndex.value = null;
  };
</script>

<template>
  <div class="filter-container-wrap">
    <div class="filter-setting-btn">
      <CommonFilterSetting></CommonFilterSetting>
    </div>
    <div
      v-if="commonFilterAddition.length"
      class="filter-container"
    >
      <div
        v-for="(item, index) in filterFieldsList"
        :class="['filter-select-wrap', { 'is-focus': focusIndex === index }]"
        @blur.capture="handleRowBlur"
        @focus.capture="e => handleRowFocus(index, e)"
      >
        <div
          class="title"
          v-bk-overflow-tips
        >
          {{ item?.field_alias || item?.field_name || '' }}
        </div>
        <bk-select
          class="operator-select"
          v-model="commonFilterAddition[index].operator"
          :input-search="false"
          :popover-min-width="100"
          filterable
          @change="debouncedHandleChange"
        >
          <template #trigger>
            <span class="operator-label">{{ getOperatorLabel(commonFilterAddition[index]) }}</span>
          </template>
          <bk-option
            v-for="(child, childIndex) in item?.field_operator"
            :id="child.operator"
            :key="childIndex"
            :name="child.label"
          />
        </bk-select>
        <template v-if="isShowConditonValueSetting(commonFilterAddition[index].operator)">
          <bk-select
            class="value-select"
            v-model="commonFilterAddition[index].value"
            v-bkloading="{ isLoading: index === activeIndex ? isRequesting : false, size: 'mini' }"
            :fix-height="true"
            allow-create
            display-tag
            multiple
            searchable
            @change="debouncedHandleChange"
            @toggle="visible => handleToggle(visible, item, index)"
          >
            <template #search>
              <bk-input
                :clearable="true"
                :left-icon="'bk-icon icon-search'"
                behavior="simplicity"
                @input="e => handleInputVlaueChange(e, item, index)"
              ></bk-input>
            </template>
            <bk-option
              v-for="option in commonFilterAddition[index].list"
              :id="option"
              :key="option"
              :name="option"
            />
          </bk-select>
        </template>
      </div>
    </div>
    <div
      v-else
      class="empty-tips"
    >
      （{{ $t('暂未设置常驻筛选，请点击左侧设置按钮') }}）
    </div>
  </div>
</template>
<style lang="scss" scoped>
  .filter-container-wrap {
    display: flex;
    align-items: center;
    max-height: 95px;
    padding: 0 10px 0px 10px;
    overflow: auto;
    background: #ffffff;
    box-shadow:
      0 2px 8px 0 rgba(0, 0, 0, 0.1490196078),
      0 1px 0 0 #eaebf0;

    .filter-setting-btn {
      min-width: 83px;
      height: 40px;
      font-size: 12px;
      line-height: 40px;
      color: #3880f8;
      cursor: pointer;
    }

    .empty-tips {
      font-size: 12px;
      color: #979ba5;
    }
  }

  .filter-container {
    display: flex;
    flex-wrap: wrap;
    width: calc(100% - 80px);
    margin-top: 4px;
  }

  .filter-select-wrap {
    display: flex;
    align-items: center;
    min-width: 180px;
    max-width: 560px;
    margin-right: 4px;
    margin-bottom: 4px;
    border: 1px solid #dbdde1;
    border-radius: 3px;

    &.is-focus {
      border-color: #3a84ff;
    }

    .title {
      max-width: 120px;
      margin-left: 8px;
      overflow: hidden;
      font-size: 12px;
      color: #313238;
      text-overflow: ellipsis;
    }

    .operator-select {
      border: none;

      .operator-label {
        display: inline-block;
        width: 100%;
        // padding: 4px;
        padding-left: 2px;
        color: #3a84ff;
        white-space: nowrap;
      }

      &.bk-select.is-focus {
        box-shadow: none;
      }
    }

    .value-select {
      min-width: 120px;
      max-width: 460px;

      :deep(.bk-select-dropdown .bk-select-tag-container) {
        padding-left: 4px;

        .bk-select-tag {
          &.width-limit-tag {
            max-width: 200px;

            > span {
              max-width: 180px;
            }
          }
        }
      }

      :deep(.bk-select-tag-input) {
        min-width: 0;
      }

      &.bk-select {
        border: none;

        &.is-focus {
          box-shadow: none;
        }

        .bk-select-name {
          padding: 0 25px 0 0px;
        }
      }

      .bk-loading .bk-loading1 {
        margin-top: 10px;
        margin-left: -20px;
      }
    }

    .bk-select-angle {
      font-size: 22px;
      color: #979ba5;
    }
  }
</style>
