<script setup lang="ts">
  import { ref, computed, watch } from 'vue';
  import useStore from '@/hooks/use-store';
  import { ConditionOperator } from '@/store/condition-operator';
  import useLocale from '@/hooks/use-locale';

  const { $t } = useLocale();
  const store = useStore();

  const filterFieldsList = computed(() => {
    return store.state.retrieve.catchFieldCustomConfig?.filterSetting?.filterFields || [];
  });

  const condition = ref([]);
  const activeIndex = ref(-1);

  watch(filterFieldsList, val => {
    if (val && val.length) {
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

  const isShowCommonFilter = ref(true);
  const handleCollapseChange = val => {
    isShowCommonFilter.value = !val;
  };
</script>

<template>
  <bk-resize-layout
    class="resize-layout-wrap"
    v-if="filterFieldsList.length"
    placement="top"
    :collapsible="true"
    :border="false"
    @collapse-change="handleCollapseChange"
  >
    <div slot="aside">
      <div
        class="filter-container"
        v-if="isShowCommonFilter && condition.length"
      >
        <div
          class="filter-select-wrap"
          v-for="(item, index) in filterFieldsList"
        >
          <div
            class="title"
            v-bk-tooltips.top="{
              content: item?.field_alias || item?.field_name,
            }"
          >
            {{ item?.field_alias || item?.field_name || '' }}
          </div>
          <bk-select
            class="operator-select"
            v-model="condition[index].operator"
            :input-search="false"
            filterable
            :popoverMinWidth="100"
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
            v-bkloading="{ isLoading: index === activeIndex ? isRequesting : false }"
            v-model="condition[index].value"
            multiple
            searchable
            allow-create
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
              :key="option"
              :id="option"
              :name="option"
            />
          </bk-select>
        </div>
      </div>
    </div>
  </bk-resize-layout>
</template>
<style lang="scss">
  .resize-layout-wrap {
    box-shadow: 0 2px 4px 0 #1919290d;

    .bk-resize-trigger {
      display: none;
    }

    .bk-resize-layout-aside {
      border-bottom: none;
    }

    .filter-container {
      display: flex;
      flex-wrap: wrap;
      max-height: 95px;
      padding: 0 10px 4px 10px;
      overflow: scroll;
      background: #ffffff;
    }

    .filter-select-wrap {
      display: flex;
      align-items: center;
      min-width: 250px;
      max-width: 600px;
      margin-top: 8px;
      margin-right: 8px;
      border: 1px solid #dbdde1;

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
          padding: 10px;
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
        }

        .bk-loading .bk-loading1 {
          margin-left: -20px;
        }
      }

      .bk-select-angle {
        font-size: 22px;
        color: #979ba5;
      }
    }
  }
</style>
