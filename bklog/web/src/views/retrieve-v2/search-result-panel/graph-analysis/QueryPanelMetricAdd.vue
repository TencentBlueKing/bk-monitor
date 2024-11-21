<!--
* Tencent is pleased to support the open source community by making
* 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
*
* Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
*
* 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
*
* License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
*
* ---------------------------------------------------
* Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
* documentation files (the "Software"), to deal in the Software without restriction, including without limitation
* the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
* to permit persons to whom the Software is furnished to do so, subject to the following conditions:
*
* The above copyright notice and this permission notice shall be included in all copies or substantial portions of
* the Software.
*
* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
* THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
* AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
* CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
* IN THE SOFTWARE.
-->
<script setup>
import { ref, computed } from "vue";
import useLocale from "@/hooks/use-locale";
const { $t } = useLocale();
const isShow = ref(false);
const keyword = ref("");
const formData = ref({
  name: "",
  aggregate: null,
});
const disabledTips = ref(false);
const fields = ref([]);
const aggregationOptions = ref([]);
const namesMap = ref({
  names: new Map(),
});
const props = defineProps({
  isAdd: Boolean,
  disabledTips: {
    type: String,
    default: "",
  },
  fields: {
    type: Array,
  },
  namesMap: {
    type: Object,
  },
  preferRawData: Boolean,
});
const filteredFields = computed(() => {
  if (!keyword.value) {
    return fields.value;
  }
  return fields.value.filter(
    ({ name, display_name }) =>
      name?.toLowerCase().includes(keyword.value.toLowerCase()) ||
      display_name?.toLowerCase().includes(keyword.value.toLowerCase())
  );
});

const handleAfterHidden = () => {};

const changeColumn = (row) => {};

const ensure = () => {};

const cancel = () => {};

const isDisabled = (row) => {
  const exitItem = namesMap.value.names.get(row.name);
  return exitItem && aggregationOptions.value.every((item) => exitItem.has(item.id));
};

const isActive = (row) => {
  return formData.value.name === row.name;
};
</script>
<template>
  <bk-popover
    ref="popoverRef"
    :isShow="isShow"
    @after-show="isShow = true"
    @after-hidden="handleAfterHidden"
    trigger="click"
    theme="light"
    extCls="bv-custom-popover"
    placement="bottom-start"
    :disabled="!!disabledTips"
    width="446"
    height="300"
  >
    <template #default>
      <!-- <AddFieldButton :disabledTips="disabledTips" /> -->
    </template>
    <template #content>
      <div class="full-height flex-column bv-query--order-select-box-shadow">
        <div class="flex-1 flex-row">
          <div class="bv-metric-select flex-column full-height flex-1">
            <div class="flex-row align-items-center justify-content-between mb-min">
              <Input
                v-model.trim="keyword"
                behavior="simplicity"
                clearable
                :placeholder="$t('搜索')"
              >
                <template #prefix>
                  <Search class="input-icon" />
                </template>
              </Input>
            </div>
            <div class="flex-1 overflow-auto">
              <div class="full-height overflow-auto">
                <template v-if="props.fields.length">
                  <DataSetFieldItem
                    v-for="row in filteredFields"
                    :key="row.name"
                    @click="!isDisabled(row) && changeColumn(row)"
                    v-bk-tooltips="{
                      content: $t('已经存该字段，不可重复添加！'),
                      disabled: !isDisabled(row) || isActive(row),
                      placement: 'right',
                    }"
                    :class="[
                      'bv-metric-field flex-row align-items-center cursor-pointer',
                      {
                        'bv-metric-field-disabled': isDisabled(row) && !isActive(row),
                        'bv-metric-field-active': isActive(row),
                      },
                    ]"
                    :field="row"
                  />
                </template>
                <template v-else>
                  <div
                    class="full-height align-items-center justify-content-center flex-column text-gray"
                  >
                    {{ keyword ? $t("无匹配数据") : $t("暂无数据") }}
                  </div>
                </template>
              </div>
            </div>
          </div>
          <div class="bv-metric-radio-box">
            <div class="text-title mb-small">{{ $t("聚合算法") }}</div>
            <!-- <Radio.Group v-model="formData.aggregate">
              <div class="flex-1 overflow-auto">
                <div
                  v-for="(item, index) in aggregationOptions"
                  :key="item.id + index"
                  class="pb-small"
                >
                  <Radio :label="item.id" :disabled="exitActiveItem?.has(item.id)">{{
                    item.name
                  }}</Radio>
                </div>
              </div>
            </Radio.Group> -->
          </div>
        </div>
        <div class="bv-metric-footer flex-row justify-content-end align-items-center">
          <Button
            @click="ensure"
            :disabled="!formData.name"
            size="small"
            theme="primary"
            class="mr-normal"
          >
            {{ $t("确定") }}
          </Button>
          <Button @click="cancel" size="small">
            {{ $t("取消") }}
          </Button>
        </div>
      </div>
    </template>
  </bk-popover>
</template>

<style lang="scss" scoped>
.bv-metric {
  &-select {
    z-index: 1000;
  }

  &-footer {
    height: 42px;
    padding: 0 16px;
    background: #fafbfd;
    box-shadow: inset 0 1px 0 0 #0000001f;
  }

  &-field {
    padding: 0 12px;
    line-height: 32px;

    &:hover {
      background: #f5f7fa;
    }

    &-disabled {
      cursor: not-allowed;

      &,
      .text-gray,
      .bkvision-icon {
        color: #c4c6cc;
      }
    }

    &-active {
      color: #3a84ff;
      background: #e1ecff;

      .text-gray {
        color: #699df4;
      }

      &:hover {
        background: #ccd7e5;
      }
    }
  }

  &-radio-box {
    width: 126px;
    padding: 8px 16px;
    background: #f5f7fa;
  }

  &-radio-title {
    padding: 8px 0;
  }
}
</style>
