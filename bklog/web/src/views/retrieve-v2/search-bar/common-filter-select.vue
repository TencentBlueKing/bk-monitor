<script setup lang="ts">
  import { ref, computed, watch, nextTick } from 'vue';

  import { getOperatorKey } from '@/common/util';
  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';

  import bklogTagChoice from './bklog-tag-choice';
  import CommonFilterSetting from './common-filter-setting.vue';
  import { FulltextOperator, FulltextOperatorKey, withoutValueConditionList } from './const.common';
  import { operatorMapping, translateKeys } from './const-values';
  import useFieldEgges from '@/hooks/use-field-egges';
  import RetrieveHelper from '../../retrieve-helper';
  import { useRoute } from 'vue-router/composables';
  import { getCommonFilterAddition, getCommonFilterFieldsList, setStorageCommonFilterAddition } from '../../../store/helper';
  import { BK_LOG_STORAGE } from '../../../store/store.type';

  const { $t } = useLocale();
  const store = useStore();
  const route = useRoute();
  const filterFieldsList = computed(() => getCommonFilterFieldsList(store.state));

  // 判定当前选中条件是否需要设置Value
  const isShowConditonValueSetting = operator => !withoutValueConditionList.includes(operator);
  const commonFilterAddition = ref([]);

  const setCommonFilterAddition = () => {
    commonFilterAddition.value.length = 0;
    commonFilterAddition.value = [];
    // 合并策略优化
    commonFilterAddition.value = getCommonFilterAddition(store.state);
  };


  watch(
    () => [filterFieldsList.value, store.state.indexId], // 同时监听 indexId
    () => {
      setCommonFilterAddition();
    },
    { immediate: true, deep: true },
  );
  const activeIndex = ref(-1);

  const operatorDictionary = computed(() => {
    const defVal = {
      [getOperatorKey(FulltextOperatorKey)]: { label: $t('包含'), operator: FulltextOperator },
    };
    return {
      ...defVal,
      ...store.state.operatorDictionary,
    };
  });

  const textDir = computed(() => {
    const textEllipsisDir = store.state.storage[BK_LOG_STORAGE.TEXT_ELLIPSIS_DIR];
    return textEllipsisDir === 'start' ? 'rtl' : 'ltr';
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

  const { requestFieldEgges, isRequesting } = useFieldEgges();
  const handleToggle = (visable, item, index) => {
    if (visable) {
      activeIndex.value = index;
      requestFieldEgges(item, null, resp => {
        if (typeof resp === 'boolean') {
          return;
        }
        commonFilterAddition.value[index].list = store.state.indexFieldInfo.aggs_items[item.field_name] ?? [];
      });
    }
  };

  const handleInputVlaueChange = (value, item, index) => {
    activeIndex.value = index;
    requestFieldEgges(item, value, resp => {
      if (typeof resp === 'boolean') {
        return;
      }
      commonFilterAddition.value[index].list = store.state.indexFieldInfo.aggs_items[item.field_name] ?? [];
    });
  };

  const handleChange = () => {
    commonFilterAddition.value.forEach(item => {
      if (!isShowConditonValueSetting(item.operator)) {
        item.value = [];
      }
    });

    setStorageCommonFilterAddition(store.state, commonFilterAddition.value);

    store.commit('retrieve/updateCatchFilterAddition', { addition: commonFilterAddition.value });

    if (route.query.tab !== 'graphAnalysis') {
      store.dispatch('requestIndexSetQuery');
    }

    RetrieveHelper.searchValueChange('filter', commonFilterAddition.value);
  };

  const focusIndex = ref(null);
  const handleRowFocus = (index, e) => {
    if (document.activeElement === e.target) {
      focusIndex.value = index;
    }
  };

  const isChoiceInputFocus = ref(false);

  const handleChoiceFocus = index => {
    isChoiceInputFocus.value = true;
    focusIndex.value = index;
  };

  const handleChoiceBlur = index => {
    if (focusIndex.value === index) {
      focusIndex.value = null;
      isChoiceInputFocus.value = null;
    }
  };

  const handleRowBlur = () => {
    if (isChoiceInputFocus.value) {
      return;
    }

    focusIndex.value = null;
  };

  const handleDeleAllOptions = () => {
    commonFilterAddition.value.forEach(item => {
      item.value = [];
    });

    handleChange();
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
      >
        <div
          class="title"
          v-bk-overflow-tips
          @blur.capture="handleRowBlur"
          @focus.capture="e => handleRowFocus(index, e)"
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
          @blur.native.capture="handleRowBlur"
          @focus.native.capture="e => handleRowFocus(index, e)"
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
          <bklogTagChoice
            :class="['value-select', { 'is-focus': focusIndex === index }]"
            v-model="commonFilterAddition[index].value"
            :foucs-fixed="true"
            :list="commonFilterAddition[index].list"
            :loading="activeIndex === index && isRequesting"
            :placeholder="$t('请选择 或 输入')"
            :bdiDir="textDir"
            max-width="460px"
            @focus="() => handleChoiceFocus(index)"
            @blur="() => handleChoiceBlur(index)"
            @change="handleChange"
            @input="val => handleInputVlaueChange(val, item, index)"
            @toggle="visible => handleToggle(visible, item, index)"
            @custom-tag-enter="() => handleToggle(true, item, index)"
          ></bklogTagChoice>
        </template>
      </div>
      <span
        @click="handleDeleAllOptions"
        class="btn-del-action bklog-icon bklog-qingkong"
      ></span>
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
    max-height: 114px;
    margin-top: 4px;
    overflow: auto;
    position: relative;
    padding-right: 30px;

    .btn-del-action {
      position: absolute;
      right: 5px;
      top: 5px;
      cursor: pointer;
    }
  }

  .filter-select-wrap {
    display: flex;
    align-items: center;
    max-width: 560px;
    margin-right: 4px;
    margin-bottom: 4px;
    box-sizing: content-box;

    .title {
      max-width: 120px;
      padding-left: 8px;
      overflow: hidden;
      font-size: 12px;
      color: #313238;
      text-overflow: ellipsis;
      border-top-left-radius: 3px;
      border-bottom-left-radius: 3px;
      border-left: 1px solid #dbdde1;
      border-top: 1px solid #dbdde1;
      border-bottom: 1px solid #dbdde1;
      line-height: 32px;
      height: 32px;
      border-right: none;
    }

    .operator-select {
      border: none;
      border-top: 1px solid #dbdde1;
      border-bottom: 1px solid #dbdde1;
      line-height: 32px;
      height: 32px;
      border-left: none;
      border-right: none;
      border-radius: 0;

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

        &[data-operator^='exists'],
        &[data-operator^='does not exists'] {
          padding-right: 4px;
        }
      }

      &.bk-select.is-focus {
        box-shadow: none;
      }
    }

    .value-select {
      min-width: 120px;
      border-left: none;
      border-radius: 0;

      &:not(.is-focus) {
        border-top-right-radius: 3px;
        border-bottom-right-radius: 3px;
        border-right: 1px solid #dbdde1;
        border-top: 1px solid #dbdde1;
        border-bottom: 1px solid #dbdde1;
      }

      &.is-focus {
        border-top-right-radius: 3px;
        border-top: 1px solid #3a84ff;
        border-bottom: 1px solid #3a84ff;

        &.is-ellipsis {
          border-bottom-color: transparent;
        }
      }
    }

    .bk-select-angle {
      font-size: 22px;
      color: #979ba5;
    }

    &.is-focus {
      border-color: #3a84ff;
      .title {
        border-left-color: #3a84ff;
        border-top-color: #3a84ff;
        border-bottom-color: #3a84ff;
      }

      .operator-select {
        border-top-color: #3a84ff;
        border-bottom-color: #3a84ff;
      }

      > div {
        &:last-child {
          &:not(.is-choice-active) {
            border-top-right-radius: 3px;
            border-bottom-right-radius: 3px;
            border-right: 1px solid #3a84ff;
            padding-right: 4px;
          }
        }
      }
    }

    > div {
      &:last-child {
        &:not(.value-select) {
          border-top-right-radius: 3px;
          border-bottom-right-radius: 3px;
          border-right: 1px solid #dbdde1;
          padding-right: 4px;
        }
      }
    }
  }
</style>
