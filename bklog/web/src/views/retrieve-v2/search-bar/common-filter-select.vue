<script setup lang="ts">
  import { ref, computed, watch } from 'vue';
  import useStore from '@/hooks/use-store';
  import { ConditionOperator } from '@/store/condition-operator';
  import useLocale from '@/hooks/use-locale';
  import CommonFilterSetting from './common-filter-setting.vue';

  const { $t } = useLocale();
  const store = useStore();

  const filterFieldsList = computed(() => {
    return store.state.retrieve.catchFieldCustomConfig?.filterSetting?.filterFields || [];
  });

  const condition = ref([]);
  const activeIndex = ref(-1);

  watch(filterFieldsList, val => {
    if (val?.length) {
      condition.value =
        filterFieldsList.value.map(item => {
          return {
            field: item?.field_name || '',
            operator: '=',
            value: [],
            list: [],
          };
        }) || [];
    }
  });

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
            condition.value[index].list = arr.filter(item => item);
          })
          .finally(() => {
            isRequesting.value = false;
          });
      }, 300);
    };
  })();

  const handleToggle = (visable, item, index) => {
    if (visable) {
      activeIndex.value = index;
      rquestFieldEgges(item, index, null, null, () => {});
    }
  };

  const handleInputVlaueChange = (value, item, index) => {
    rquestFieldEgges(item, index, condition.value[index].operator, value);
  };

  const handleChange = () => {
    store.commit('updateCommonFilter', condition.value);
    store.dispatch('requestIndexSetQuery');
  };
</script>

<template>
  <div class="filter-container-wrap">
    <div class="filter-setting-btn">
      <CommonFilterSetting></CommonFilterSetting>
    </div>
    <div
      v-if="condition.length"
      class="filter-container"
    >
      <div
        v-for="(item, index) in filterFieldsList"
        class="filter-select-wrap"
      >
        <div class="title">
          {{ item?.field_alias || item?.field_name || '' }}
        </div>
        <bk-select
          class="operator-select"
          v-model="condition[index].operator"
          :input-search="false"
          :popover-min-width="100"
          filterable
          @change="handleChange"
        >
          <template #trigger>
            <span class="operator-label">{{ $t(condition[index].operator) }}</span>
          </template>
          <bk-option
            v-for="(item, index) in item?.field_operator"
            :id="item.label"
            :key="index"
            :name="item.label"
          />
        </bk-select>
        <bk-select
          class="value-select"
          v-bkloading="{ isLoading: index === activeIndex ? isRequesting : false, size: 'mini' }"
          v-model="condition[index].value"
          allow-create
          display-tag
          multiple
          searchable
          :fix-height="true"
          @change="handleChange"
          @toggle="visible => handleToggle(visible, item, index)"
        >
          <template #search>
            <bk-input
              behavior="simplicity"
              :clearable="true"
              :left-icon="'bk-icon icon-search'"
              @input="e => handleInputVlaueChange(e, item, index)"
            ></bk-input>
          </template>
          <bk-option
            v-for="option in condition[index].list"
            :id="option"
            :key="option"
            :name="option"
          />
        </bk-select>
      </div>
    </div>
    <div
      v-else
      class="empty-tips"
    >
      （暂未设置常驻筛选，请点击左侧设置按钮）
    </div>
  </div>
</template>
<style lang="scss">
  .filter-container-wrap {
    display: flex;
    max-height: 95px;
    padding: 0 10px 4px 10px;
    overflow: scroll;
    background: #ffffff;

    .filter-setting-btn {
      width: 83px;
      height: 42px;
      font-size: 13px;
      line-height: 42px;
      color: #3880f8;
      cursor: pointer;
    }

    .empty-tips {
      font-size: 12px;
      line-height: 42px;
      color: #a1a5ae;
    }
  }

  .filter-container {
    display: flex;
    flex-wrap: wrap;
    width: calc(100% - 80px);
  }

  .filter-select-wrap {
    display: flex;
    align-items: center;
    min-width: 250px;
    max-width: 600px;
    margin-top: 8px;
    margin-right: 8px;
    border: 1px solid #dbdde1;
    border-radius: 3px;

    .title {
      max-width: 125px;
      margin-left: 8px;
      overflow: hidden;
      font-size: 12px;
      color: #313238;
      text-overflow: ellipsis;
    }

    .operator-select {
      border: none;

      .operator-label {
        padding: 4px;
        color: #ff9c01;
      }

      &.bk-select.is-focus {
        box-shadow: none;
      }
    }

    .value-select {
      min-width: 200px;
      max-width: 460px;

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
