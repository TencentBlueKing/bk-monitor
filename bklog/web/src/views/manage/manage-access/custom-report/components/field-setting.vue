<template>
  <div class="create-form">
    <div class="form-title">
      <span>{{ $t('字段设置') }}</span>
      <span class="title-tips">
        <i class="bk-icon icon-exclamation-circle"></i>
        <span>{{ $t('未匹配到对应字段，请手动指定字段后提交') }}</span>
      </span>
    </div>
    <!-- 目标字段 -->
    <bk-form-item
      :label="$t('目标字段')"
      :property="'target_fields'"
      :desc="$t('用于标识日志文件来源及唯一性')"
    >
      <bk-select
        style="width: 500px"
        v-model="value.targetFields"
        :collapse-tag="false"
        :is-tag-width-limit="false"
        display-tag
        multiple
        searchable
      >
        <bk-option
          v-for="option in targetFieldSelectList"
          :id="option.id"
          :key="option.id"
          :name="option.name"
        >
        </bk-option>
      </bk-select>
    </bk-form-item>
    <!-- 排序字段 -->
    <bk-form-item
      :label="$t('排序字段')"
      :property="'sort_fields'"
      :desc="$t('用于控制日志排序的字段')"
    >
      <div class="collection-select sort-box">
        <vue-draggable
          v-model="value.sortFields"
          animation="150"
          handle=".icon-grag-fill"
        >
          <transition-group>
            <bk-tag
              v-for="(item, index) in value.sortFields"
              ext-cls="tag-items"
              :key="item"
              closable
              @close="handleCloseSortFiled(item, index)"
            >
              <i class="bk-icon icon-grag-fill"></i>
              {{ item }}
            </bk-tag>
          </transition-group>
        </vue-draggable>
        <bk-select
          :ext-cls="`add-sort-btn ${!value.sortFields?.length && 'not-sort'}`"
          :popover-min-width="240"
          searchable
          style="width: 500px"
          @selected="handleAddSortFields"
        >
          <template #trigger>
            <bk-button
              class="king-button"
              icon="plus"
            ></bk-button>
          </template>
          <bk-option
            v-for="option in targetFieldSelectList"
            :disabled="getSortDisabledState(option.id)"
            :id="option.id"
            :key="option.id"
            :name="option.name"
          >
          </bk-option>
        </bk-select>
      </div>
    </bk-form-item>
  </div>
</template>
<script setup lang="ts">
import { ref, watch, defineProps, defineEmits } from 'vue';
import VueDraggable from 'vuedraggable';
import $http from '../../../../../api';
import { cloneDeep } from 'lodash';

const props = defineProps({
  value: {
    type: Object,
    default: () => ({}),
    required: true,
  },
});

const emits = defineEmits(['update:value']);

// 获取字段设置数据列表
const targetFieldSelectList = ref([]);

const initTargetFieldSelectList = async () => {
  const res = await $http.request('retrieve/getLogTableHead', {
    params: {
      index_set_id: props?.value?.indexSetId,
    },
    query: {
      is_realtime: 'True',
    },
  });
  targetFieldSelectList.value = res?.data?.fields.map(item => {
    return {
      id: item.field_name,
      name: item.field_name,
    };
  });
};

watch(
  () => props.value,
  newVal => {
    if (newVal && newVal?.indexSetId) {
      initTargetFieldSelectList();
    }
  },
  {
    immediate: true,
    deep: true,
  }
);

const getSortDisabledState = id => {
  return props.value.sortFields?.includes(id);
};

const handleAddSortFields = val => {
  props.value?.sortFields.push(val);
};

const handleCloseSortFiled = (item, index) => {
  props.value?.sortFields.splice(index, 1);
};
</script>
<style lang="scss" scoped>
  .sort-box {
    display: inline-flex;
    align-items: center;

    .add-sort-btn {
      display: inline-block;
      margin-left: 6px;
      border: none;
      box-shadow: none;
    }

    .not-sort {
      margin-left: 0;
    }
  }

  .title-tips {
    margin-left: 16px;
    font-size: 12px;
    font-weight: normal;

    .icon-exclamation-circle {
      font-size: 16px;
      color: #ea3636;
    }
  }

  .collection-select {
    .tag-items {
      height: 32px;
      line-height: 32px;

      .icon-grag-fill {
        display: inline-block;
        cursor: move;
        transform: translateY(-1px);
      }
    }
  }
</style>
