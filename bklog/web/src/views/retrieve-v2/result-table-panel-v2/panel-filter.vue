<script setup>
  import { computed, ref, nextTick, watch } from 'vue';

  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';

  import FieldFilter from '../field-filter-comp';
  const store = useStore();
  const { $t } = useLocale();
  /** 时间选择器绑定的值 */
  const datePickerValue = computed(() => {
    const { start_time = 'now-15m', end_time = 'now' } = store.state.indexItem;
    return [start_time, end_time];
  });

  const indexSetItem = computed(() => {
    return store.state.indexItem;
  });
  const logSourceField = {
    description: null,
    es_doc_values: false,
    field_alias: '',
    field_name: $t('日志来源'),
    field_operator: [],
    field_type: 'union',
    filterExpand: false,
    filterVisible: false,
    is_analyzed: false,
    is_display: false,
    is_editable: false,
    minWidth: 0,
    tag: 'union-source',
    width: 230,
  };
  const sortList = computed(() => {
    return store.state.indexFieldInfo.sort_list;
  });
  const totalFields = computed(() => {
    return store.state.indexFieldInfo.fields;
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
      ...store.state.retrieveParams,
      start_time: datePickerValue.value[0],
      end_time: datePickerValue.value[1],
    };
  });

  const retrieveOption = computed(() => {
    const { retrieveSearchNumber = 0, tableLoading = false } = store.state;
    return {
      retrieveSearchNumber,
      tableLoading,
    };
  });

  const operatorConfig = ref({
    /** 当前日志来源是否展示  用于字段更新后还保持显示状态 */
    isShowSourceField: false,
  });
  const showFieldAlias = ref(localStorage.getItem('showFieldAlias') === 'true');
  const visibleFields = computed(() => store.state.visibleFields ?? []);

  // 接口中获取的字段
  const statisticalFieldsData = ref({});

  /**
   * @desc: 初始化展示字段
   * @param {Array<str>} displayFieldNames 显示字段
   */
  const initVisibleFields = displayFieldNames => {
    const displayFields = displayFieldNames
      .map(displayName => {
        for (const field of totalFields.value) {
          if (field.field_name === displayName) {
            return field;
          }
        }
      })
      .filter(Boolean);
    showShowUnionSource(true);
    store.commit('updateIsNotVisibleFieldsShow', !displayFields.length);
    // store.commit('updateVisibleFields', !displayFields.length);
  };
  const showShowUnionSource = (keepLastTime = false) => {
    // 非联合查询 或者清空了所有字段 不走逻辑
    if (!store.state.isUnionSearch || !visibleFields.value.length) return;
    const isExist = visibleFields.value.some(item => item.tag === 'union-source');
    // 保持之前的逻辑
    if (keepLastTime) {
      const isShowSourceField = operatorConfig.value.isShowSourceField;
      if (isExist) {
        !isShowSourceField && visibleFields.value.shift();
      } else {
        isShowSourceField && visibleFields.value.unshift(logSourceField.value);
      }
      return;
    }
    const visibleFields = isExist ? visibleFields.value.shift() : visibleFields.value.unshift(this.logSourceField);
    if (visibleFields) {
      store.commit('updateVisibleFields', visibleFields);
    }
  };
  /**
   * @desc: 字段设置更新了
   * @param {Array} displayFieldNames 展示字段
   * @param {Boolean} showFieldAlias 是否别名
   * @param {Boolean} isRequestFields 是否请求字段
   */
  const handleFieldsUpdated = async (displayFieldNames, showFieldAlias, isRequestFields = true) => {
    store.dispatch('updateClearTableWidth', 1);
    // 缓存展示字段
    const showFieldObj = this.sessionShowFieldObj();
    Object.assign(showFieldObj, { [this.indexId]: displayFieldNames });
    sessionStorage.setItem('showFieldSession', JSON.stringify(showFieldObj));
    if (showFieldAlias !== undefined) {
      showFieldAlias.value = showFieldAlias;
      window.localStorage.setItem('showFieldAlias', showFieldAlias);
    }
    await nextTick();
    if (!isRequestFields) {
      initVisibleFields(displayFieldNames);
    } else {
      isSetDefaultTableColumn.value = false;
      // this.requestFields(); // 该接口具体逻辑待确定
    }
  };
  watch(
    store.state.indexFieldInfo,
    () => {
      initVisibleFields(store.state.indexFieldInfo.display_fields);
    },
    { deep: true, immediate: true },
  );
</script>

<template>
  <div class="result-table-panel-filter">
    <!-- 字段过滤 -->
    <div class="tab-item-title field-filter-title">
      {{ $t('查询结果统计') }}
    </div>
    <FieldFilter
      ref="fieldFilterRef"
      :date-picker-value="datePickerValue"
      :field-alias-map="fieldAliasMap"
      :index-set-item="indexSetItem"
      :parent-loading="retrieveOption.tableLoading"
      :retrieve-params="retrieveParams"
      :retrieve-search-number="retrieveOption.retrieveSearchNumber"
      :show-field-alias="showFieldAlias"
      :sort-list="sortList"
      :statistical-fields-data="statisticalFieldsData"
      :total-fields="totalFields"
      :visible-fields="visibleFields"
      @fields-updated="handleFieldsUpdated"
    />
  </div>
</template>

<!-- <style scoped></style> -->
