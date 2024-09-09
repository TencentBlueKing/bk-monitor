<script setup>
  import { computed, ref, nextTick, watch } from 'vue';

  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';

  import FieldFilterComp from '../field-filter-comp';
  const store = useStore();
  const { $t } = useLocale();
  const props = defineProps({
    isShowFieldStatistics: { type: Boolean, default: true },
  });
  const emit = defineEmits(['update:is-show-field-statistics']);
  /** 时间选择器绑定的值 */
  const datePickerValue = computed(() => {
    const { start_time = 'now-15m', end_time = 'now' } = store.state.indexItem;
    return [start_time, end_time];
  });

  const indexSetItem = computed(() => {
    return store.state.indexItem;
  });

  const sortList = computed(() => {
    return store.state.indexFieldInfo.sort_list;
  });
  const totalFields = computed(() => {
    return store.state.indexFieldInfo.fields;
  });
  const indexId = computed(() => {
    return store.state.indexId;
  });
  const fieldAliasMap = computed(() => {
    const fieldAliasMap = {};
    store.state.indexFieldInfo.fields.forEach(item => {
      item.minWidth = 0;
      item.filterExpand = false; // 字段过滤展开
      item.filterVisible = true;
      // if (item.field_type !== 'text') {
      //   notTextTypeFields.push(item.field_name);
      // }
      fieldAliasMap[item.field_name] = item.field_alias || item.field_name;
    });
    return fieldAliasMap;
  });

  const retrieveParams = computed(() => {
    return {
      bk_biz_id: store.state.bkBizId,
      ...store.getters.retrieveParams,
      start_time: datePickerValue.value[0],
      end_time: datePickerValue.value[1],
    };
  });

  const showFieldAlias = ref(localStorage.getItem('showFieldAlias') === 'true');
  const visibleFields = computed(() => store.state.visibleFields ?? []);

  // 接口中获取的字段
  const statisticalFieldsData = ref({});
  const sessionShowFieldObj = () => {
    // 显示字段缓存
    const showFieldStr = sessionStorage.getItem('showFieldSession');
    return !showFieldStr ? {} : JSON.parse(showFieldStr);
  };
  /**
   * @desc: 字段设置更新了
   * @param {Array} displayFieldNames 展示字段
   * @param {Boolean} showFieldAlias 是否别名
   * @param {Boolean} isRequestFields 是否请求字段
   */
  const handleFieldsUpdated = async (displayFieldNames, showFieldAlias, isRequestFields = true) => {
    store.commit('updateClearTableWidth', 1);
    // 缓存展示字段
    const showFieldObj = sessionShowFieldObj();
    Object.assign(showFieldObj, { [indexId.value]: displayFieldNames });
    sessionStorage.setItem('showFieldSession', JSON.stringify(showFieldObj));
    if (showFieldAlias !== undefined) {
      showFieldAlias.value = showFieldAlias;
      window.localStorage.setItem('showFieldAlias', showFieldAlias);
    }
    await nextTick();
    if (!isRequestFields) {
      store.commit('resetVisibleFields', displayFieldNames);
    } else {
      // isSetDefaultTableColumn.value = false;
      store.dispatch('requestIndexSetFieldInfo');
    }
  };
  const handleCloseFilterTitle = () => {
    emit('update:is-show-field-statistics', !props.isShowFieldStatistics);
  };
</script>

<template>
  <div :class="['search-field-filter', { 'is-close': !isShowFieldStatistics }]">
    <!-- 字段过滤 -->
    <div class="tab-item-title field-filter-title">
      <div class="left-title">
        {{ $t('字段列表') }}
      </div>
      <div
        class="close-total"
        @click="handleCloseFilterTitle"
      >
        <span
          v-show="isShowFieldStatistics"
          class="collect-title"
        >
          {{ $t('收起') }}
        </span>
        <span class="bklog-icon bklog-collapse-small"></span>
      </div>
    </div>
    <FieldFilterComp
      ref="fieldFilterRef"
      v-show="isShowFieldStatistics"
      :date-picker-value="datePickerValue"
      :field-alias-map="fieldAliasMap"
      :index-set-item="indexSetItem"
      :retrieve-params="retrieveParams"
      :show-field-alias="showFieldAlias"
      :sort-list="sortList"
      :total-fields="totalFields"
      :visible-fields="visibleFields"
      @fields-updated="handleFieldsUpdated"
    />
  </div>
</template>

<style scoped>
  @import './field-filter.scss';
</style>
