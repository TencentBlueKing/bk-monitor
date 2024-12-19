<script setup lang="ts">
  import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
  import useStore from '@/hooks/use-store';
  import { bus } from '@/common/bus';
  import { ConditionOperator } from '@/store/condition-operator';

  const store = useStore();
  const userSettingConfig = computed(() => {
    return store.state.retrieve.catchFieldCustomConfig;
  });

  const SettingData = ref({
    switchingMode: false,
    filterFields: [],
  });
  const filterFieldList = computed(() => {
    return SettingData.value.filterFields;
  });

  const condition = ref([]);

  let requestTimer = null;
  const isRequesting = ref(false);

  const rquestFieldEgges = (() => {
    return (field, index, operator?, value?, callback?) => {
      const getConditionValue = () => {
        if (['keyword'].includes(field.field_type)) {
          return [`*${value}*`];
        }

        return [];
      };
      condition.value[index].list.splice(0, condition.value[index].list.length);

      if (value !== undefined && value !== null && !['keyword', 'text'].includes(field.field_type)) {
        return;
      }

      const size = ['keyword'].includes(field.field_type) && value?.length > 0 ? 10 : 100;
      isRequesting.value = true;

      requestTimer && clearTimeout(requestTimer);
      requestTimer = setTimeout(() => {
        const addition = value
          ? [{ field: field.field_name, operator: '=~', value: getConditionValue() }].map(val => {
              const instance = new ConditionOperator(val);
              return instance.getRequestParam();
            })
          : [];
        store
          .dispatch('requestIndexSetValueList', { fields: [field], addition, force: true, size })
          .then(res => {
            const arr = res.data?.aggs_items?.[field.field_name] || [];
            condition.value[index].list = arr.map(item => {
              return {
                id: item,
                name: item,
              };
            });
          })
          .finally(() => {
            isRequesting.value = false;
          });
      }, 300);
    };
  })();

  const activeIndex = ref(-1);
  const handleFocus = (item, index) => {
    activeIndex.value = index;
    rquestFieldEgges(item, index, null, null, () => {});
  };

  const handleChange = () => {
    store.commit('updateCommonFilter', condition.value);
    store.dispatch('requestIndexSetQuery');
  };

  const initData = data => {
    // const displayFields = userSettingConfig?.value.displayFields || [];
    const { switchingMode, filterFields } = data ? data?.filterSetting : userSettingConfig?.value?.filterSetting;
    SettingData.value.switchingMode = switchingMode || false;
    SettingData.value.filterFields = filterFields || [];
    const result =
      filterFields?.filter(item => {
        // console.log(item, displayFields.includes(item.field));
        // return displayFields.includes(item.field);
        return item;
      }) || [];
    condition.value =
      result?.map(item => {
        return {
          field: item?.field_name || '',
          operator: '=',
          value: [],
          list: [],
        };
      }) || [];
  };

  onMounted(() => {
    bus.$on('requestIndexSetFieldInfoDone', initData);
  });

  onBeforeUnmount(() => {
    bus.$off('requestIndexSetFieldInfoDone', initData);
  });
</script>

<template>
  <div class="filter-container">
    <div
      class="filter-select-wrap"
      v-for="(item, index) in filterFieldList"
    >
      <div class="title">{{ item?.field_alias || item?.field_name || '' }}</div>
      <bk-select
        class="operator-select"
        v-model="condition[index].operator"
        :input-search="false"
        filterable
        :popoverMinWidth="100"
        @change="handleChange"
      >
        <template #trigger="{ selected }">
          <span class="operator-label">{{ condition[index].operator }}</span>
        </template>
        <bk-option
          v-for="(item, index) in item.field_operator"
          :id="item.label"
          :key="index"
          :name="item.label"
        />
      </bk-select>
      <!-- 后续再确定是否加loading v-bkloading="{ isLoading: activeIndex === index ? isRequesting : false }" -->
      <bk-tag-input
        class="value-select"
        v-model="condition[index].value"
        :list="condition[index].list"
        placeholder="请选择"
        allow-auto-match
        trigger="focus"
        allow-create
        has-delete-icon
        :clearable="false"
        :collapse-tags="true"
        @focus="handleFocus(item, index)"
        @change="handleChange"
      >
      </bk-tag-input>
      <i class="bk-select-angle bk-icon icon-angle-down"></i>
    </div>
  </div>
</template>
<style lang="scss">
  .filter-container {
    display: flex;
    padding: 10px;
    background: #ffffff;
    box-shadow: 0 2px 4px 0 #1919290d;
  }
  .filter-select-wrap {
    border: 1px solid #dbdde1;
    display: flex;
    align-items: center;
    margin-right: 8px;

    .title {
      margin-left: 8px;
      font-size: 12px;
      color: #313238;
    }
    .operator-select {
      border: none;
      .operator-label {
        padding: 10px;
        color: #ff9c01;
      }
      &.bk-select.is-focus {
        -webkit-box-shadow: none;
        box-shadow: none;
      }
    }
    .value-select {
      min-width: 160px;
      &.bk-tag-selector .bk-tag-input {
        border: none;
      }
      &.bk-tag-selector .bk-tag-input .placeholder {
        left: 0;
      }
      &.bk-tag-selector .bk-tag-input {
        padding: 0;
      }
    }
    .bk-select-angle {
      color: #979ba5;
      font-size: 22px;
    }
  }
</style>
