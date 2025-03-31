<script setup lang="ts">
  import { ref, computed, watch } from 'vue';
  import useStore from '@/hooks/use-store';
  import useLocale from '@/hooks/use-locale';

  import CommonFilterSetting from './common-filter-setting.vue';
  import { FulltextOperator, FulltextOperatorKey, withoutValueConditionList } from './const.common';
  import { getOperatorKey } from '@/common/util';
  import { operatorMapping, translateKeys } from './const-values';
  import useFieldEgges from './use-field-egges';

  import bklogTagChoice from './bklog-tag-choice';

  const { $t } = useLocale();
  const store = useStore();
  const filterFieldsList = computed(() => {
    if (Array.isArray(store.state.retrieve.catchFieldCustomConfig?.filterSetting)) {
      return store.state.retrieve.catchFieldCustomConfig?.filterSetting ?? [];
    }

    return [];
  });

  // 判定当前选中条件是否需要设置Value
  const isShowConditonValueSetting = operator => !withoutValueConditionList.includes(operator);
  const commonFilterAddition = ref([]);

  const setCommonFilterAddition = () => {
    commonFilterAddition.value.length = 0;
    commonFilterAddition.value = [];
    const additionValue = JSON.parse(localStorage.getItem('commonFilterAddition'));

    const isSameIndex = additionValue?.indexId === store.state.indexId;
    const storedValue = isSameIndex ? additionValue.value : [];

    // 合并策略优化
    commonFilterAddition.value = filterFieldsList.value.map(item => {
      const storedItem = storedValue.find(v => v.field === item.field_name);
      const storeItem = (store.getters.common_filter_addition || []).find(
        addition => addition.field === item.field_name,
      );

      // 优先级：本地存储 > store > 默认值
      return (
        storedItem ||
        storeItem || {
          field: item.field_name || '',
          operator: '=',
          value: [],
          list: [],
        }
      );
    });
  };
  watch(
    () => [filterFieldsList.value, store.state.indexId], // 同时监听 indexId
    () => {
      const additionValue = JSON.parse(localStorage.getItem('commonFilterAddition'));

      // indexId 变化时清除无效缓存
      if (additionValue?.indexId !== store.state.indexId) {
        localStorage.removeItem('commonFilterAddition');
      }

      setCommonFilterAddition();
    },
    { immediate: true, deep: true },
  );
  const activeIndex = ref(-1);
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

  const handleChange = () => {
    commonFilterAddition.value.forEach(item => {
      if (!isShowConditonValueSetting(item.operator)) {
        item.value = [];
      }
    });

    localStorage.setItem(
      'commonFilterAddition',
      JSON.stringify({
        indexId: store.state.indexId,
        value: commonFilterAddition.value,
      }),
    );

    store.commit('retrieve/updateCatchFilterAddition', { addition: commonFilterAddition.value });
    store.dispatch('requestIndexSetQuery');
  };

  const focusIndex = ref(null);
  const handleRowFocus = (index, e) => {
    if (document.activeElement === e.target) {
      focusIndex.value = index;
    }
  };

  const handleRowBlur = (agr?) => {
    focusIndex.value = null;
    console.log('-----', agr);
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
          @change="handleChange"
        >
          <template #trigger>
            <span
              class="operator-label"
              :data-operator="commonFilterAddition[index].operator"
              >{{ getOperatorLabel(commonFilterAddition[index]) }}</span
            >
          </template>
          <bk-option
            v-for="(child, childIndex) in item?.field_operator"
            :id="child.operator"
            :key="childIndex"
            :name="child.label"
          />
        </bk-select>
        <template v-if="isShowConditonValueSetting(commonFilterAddition[index].operator)">
          <!-- <bk-select
            class="value-select"
            v-model="commonFilterAddition[index].value"
            placeholder="请选择 或 输入"
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
          </bk-select> -->
          <bklogTagChoice
            class="value-select"
            v-model="commonFilterAddition[index].value"
            :list="commonFilterAddition[index].list"
            :loading="activeIndex === index && isRequesting"
            :placeholder="$t('请选择 或 输入')"
            :foucs-fixed="true"
            max-width="460px"
            @change="handleChange"
            @input="val => handleInputVlaueChange(val, item, index)"
            @toggle="visible => handleToggle(visible, item, index)"
          ></bklogTagChoice>
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
    background: #ffffff;
    border-radius: 0 0 2px 2px;
    box-shadow: 0 2px 4px 0 #19192914;

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
    max-height: 90px;
    margin-top: 4px;
    overflow: auto;
  }

  .filter-select-wrap {
    display: flex;
    align-items: center;
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

        &[data-operator^='not contains'],
        &[data-operator^='does not exists'],
        &[data-operator^='is false'],
        &[data-operator^='!='] {
          color: #ea3636;
        }
      }

      &.bk-select.is-focus {
        box-shadow: none;
      }
    }

    .value-select {
      min-width: 120px;
    }

    .bk-select-angle {
      font-size: 22px;
      color: #979ba5;
    }
  }
</style>
