<script setup lang="ts">
  import { ref, computed } from 'vue';
  import useStore from '@/hooks/use-store';
  import { ConditionOperator } from '@/store/condition-operator';
  import useLocale from '@/hooks/use-locale';
  import CommonFilterSetting from './common-filter-setting.vue';
  import { withoutValueConditionList } from './const.common';

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

  const commonFilterAddition = computed({
    get() {
      if (store.getters.retrieveParams.common_filter_addition?.length) {
        return store.getters.retrieveParams.common_filter_addition;
      }

      return filterFieldsList.value.map(item => ({
        field: item?.field_name || '',
        operator: '=',
        value: [],
        list: [],
      }));
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

  const activeIndex = ref(-1);

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
      commonFilterAddition.value[index].list.splice(0, commonFilterAddition.value[index].list.length);

      if (value !== undefined && value !== null && !['keyword', 'text'].includes(field.field_type)) {
        return;
      }

      const size = ['keyword'].includes(field.field_type) && value?.length > 0 ? 10 : 100;
      isRequesting.value = true;

      requestTimer && clearTimeout(requestTimer);
      requestTimer = setTimeout(() => {
        const targetAddition = value
          ? [{ field: field.field_name, operator: '=~', value: getConditionValue() }].map(val => {
              const instance = new ConditionOperator(val);
              return instance.getRequestParam();
            })
          : [];
        store
          .dispatch('requestIndexSetValueList', { fields: [field], targetAddition, force: true, size })
          .then(res => {
            const arr = res.data?.aggs_items?.[field.field_name] || [];
            commonFilterAddition.value[index].list = arr.filter(item => item);
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
    rquestFieldEgges(item, index, commonFilterAddition.value[index].operator, value);
  };

  // 新建提交逻辑
  const updateCommonFilterAddition = () => {
    const target = commonFilterAddition.value.map(item => {
      if (!isShowConditonValueSetting(item.operator)) {
        item.value = [];
      }

      return item;
    });

    const param = {
      filterAddition: target,
    };

    store.dispatch('userFieldConfigChange', param);
  };

  const handleChange = () => {
    updateCommonFilterAddition();
    store.dispatch('requestIndexSetQuery');
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
        class="filter-select-wrap"
      >
        <div class="title">
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
            <span class="operator-label">{{ $t(commonFilterAddition[index].operator) }}</span>
          </template>
          <bk-option
            v-for="(child, childIndex) in item?.field_operator"
            :id="child.label"
            :key="childIndex"
            :name="child.label"
          />
        </bk-select>
        <template v-if="isShowConditonValueSetting(commonFilterAddition[index].operator)">
          <bk-select
            class="value-select"
            v-bkloading="{ isLoading: index === activeIndex ? isRequesting : false, size: 'mini' }"
            v-model="commonFilterAddition[index].value"
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
      （暂未设置常驻筛选，请点击左侧设置按钮）
    </div>
  </div>
</template>
<style lang="scss">
  .filter-container-wrap {
    display: flex;
    max-height: 95px;
    padding: 0 10px 0px 10px;
    overflow: auto;
    background: #ffffff;

    .filter-setting-btn {
      width: 83px;
      height: 40px;
      font-size: 13px;
      line-height: 40px;
      color: #3880f8;
      cursor: pointer;
    }

    .empty-tips {
      font-size: 12px;
      line-height: 40px;
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
    margin: 4px 0;
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
