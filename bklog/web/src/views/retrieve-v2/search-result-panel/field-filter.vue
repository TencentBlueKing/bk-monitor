<script setup>
  import { computed, nextTick, ref, onMounted } from 'vue';
  import useLocale from '@/hooks/use-locale';
  import useStore from '@/hooks/use-store';

  import FieldFilterComp from '../field-filter-comp';
  const store = useStore();
  const { $t } = useLocale();
  const props = defineProps({
    value: { type: Boolean, default: true },
  });
  const fieldShowName = ref('field_name');
  const emit = defineEmits(['input', 'field-status-change']);
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

  const fieldAliasMap = computed(() => {
    const fieldAliasMap = {};
    store.state.indexFieldInfo.fields.forEach(item => {
      item.minWidth = 0;
      item.filterExpand = false; // 字段过滤展开
      item.filterVisible = true;
      // fieldAliasMap[item.field_name] = item.field_alias || item.field_name;
      fieldAliasMap[item.field_name] = fieldShowName.value === 'field_name'
        ?  item.field_name || item.field_alias
        : item.query_alias || item.field_alias  || item.field_name;
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

  // const showFieldAlias = computed(() => store.state.showFieldAlias);
  const visibleFields = computed(() => store.state.visibleFields ?? []);

  /**
   * @desc: 字段设置更新了
   * @param {Array} displayFieldNames 展示字段
   */
  const handleFieldsUpdated = async displayFieldNames => {
    store.dispatch('userFieldConfigChange', {
      displayFields: displayFieldNames,
    });
    await nextTick();
    store.commit('resetVisibleFields', displayFieldNames);
    store.commit('updateIsSetDefaultTableColumn', false);
  };
  const handleCloseFilterTitle = isTextClick => {
    if (isTextClick && props.value) return;
    emit('field-status-change', !props.value);
    emit('input', !props.value);
  };
  const handlerChange = (value) => {
    localStorage.setItem('showFieldAlias', value);
    store.commit('updateShowFieldAlias', value);
  }
  onMounted(()=>{
    fieldShowName.value = localStorage.getItem('showFieldAlias') === 'true'
  })
</script>

<template>
  <div :class="['search-field-filter-new', { 'is-close': !value }]">
    <!-- 字段过滤 -->
    <div class="tab-item-title field-filter-title">
      <div
        class="left-title"
        :class="{ 'is-text-click': !value }"
        @click="handleCloseFilterTitle(true)"
      >
        {{ $t('字段统计') }}
        <bk-popconfirm
          trigger="click"
          width="260"
          class="left-title-setting"
          ext-popover-cls="field-filter-content"
        >
          <div slot="content">
            <bk-radio-group v-model="fieldShowName" style="margin-bottom: 10px;" @change="handlerChange">
              <bk-radio-button :value="false">
                {{ $t('展示字段名') }}
              </bk-radio-button>
              <bk-radio-button :value="true">
                {{ $t('展示别名') }}
              </bk-radio-button>
            </bk-radio-group>
          </div>
        <span class="bklog-icon bklog-log-setting"></span>
      </bk-popconfirm>
      </div>
      <div
        class="close-total"
        @click="handleCloseFilterTitle(false)"
      >
        <span
          v-show="value"
          class="collect-title"
        >
          {{ $t('收起') }}
        </span>
        <span class="bklog-icon bklog-collapse-small"></span>
      </div>
    </div>
    <FieldFilterComp
      ref="fieldFilterRef"
      v-show="value"
      :date-picker-value="datePickerValue"
      :field-alias-map="fieldAliasMap"
      :index-set-item="indexSetItem"
      :retrieve-params="retrieveParams"
      :show-field-alias="!fieldShowName"
      :sort-list="sortList"
      :total-fields="totalFields"
      :visible-fields="visibleFields"
      @fields-updated="handleFieldsUpdated"
    />
  </div>
</template>

<style lang="scss">
  @import './field-filter.scss';
</style>
