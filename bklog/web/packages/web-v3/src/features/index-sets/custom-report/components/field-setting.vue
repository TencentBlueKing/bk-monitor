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
        v-model="targetFields"
        style="width: 500px"
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
          v-model="sortFields"
          animation="150"
          handle=".icon-grag-fill"
        >
          <transition-group>
            <t-tag variant="light" data-v2-display="tag"
              v-for="(item, index) in sortFields"
              :key="item"
              :class="'tag-items'"
              closable
              @close="({e}) => handleCloseSortFiled(item, index)"
            >
              <i class="bk-icon icon-grag-fill"></i>
              {{ item }}
            </t-tag>
          </transition-group>
        </vue-draggable>
        <bk-select
          :ext-cls="`add-sort-btn ${!sortFields.length && 'not-sort'}`"
          :popover-min-width="240"
          searchable
          style="width: 500px"
          @selected="handleAddSortFields"
        >
          <template #trigger>
            <t-button
              class="king-button"
              
            ><template #icon><span :class="`bk-icon icon-${'plus'}`"></span></template></t-button>
          </template>
          <bk-option
            v-for="option in targetFieldSelectList"
            :id="option.id"
            :key="option.id"
            :disabled="getSortDisabledState(option.id)"
            :name="option.name"
          >
          </bk-option>
        </bk-select>
      </div>
    </bk-form-item>
  </div>
</template>
<script setup lang="ts">import { ServicesInstance } from '@/platform/services';

  import { computed, ref, watch, defineProps, defineEmits } from 'vue';
  import VueDraggable from 'vuedraggable';
  

  const props = defineProps({
    value: {
      type: Object,
      default: () => ({}),
      required: true,
    },
  });

  const emit = defineEmits(['input']);

  const targetFields = computed({
    get: () => props.value.targetFields || [],
    set: value => emit('input', { ...props.value, targetFields: value }),
  });
  const sortFields = computed({
    get: () => props.value.sortFields || [],
    set: value => emit('input', { ...props.value, sortFields: value }),
  });

  // 获取字段设置数据列表
  const targetFieldSelectList = ref([]);

  const initTargetFieldSelectList = async () => {
    const res = await ServicesInstance.retrieve.getLogTableHead({
      params: {
        index_set_id: props?.value?.indexSetId,
      },
      query: {
        is_realtime: 'True',
      },
    });
    targetFieldSelectList.value = res?.data?.fields.map((item: { field_name: any; }) => {
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
    },
  );

  const getSortDisabledState = (id: unknown) => {
    return sortFields.value.includes(id);
  };

  const handleAddSortFields = (val: unknown) => {
    sortFields.value = [...sortFields.value, val];
  };

  const handleCloseSortFiled = (item: unknown, index: unknown) => {
    sortFields.value = sortFields.value.filter((_: unknown, sortIndex: unknown) => sortIndex !== index);
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
