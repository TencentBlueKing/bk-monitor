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
import { ref, defineExpose, computed } from "vue";
import settingSVG from "@/images/icons/setting-fill.svg";
import Draggable from "vuedraggable";
import QueryPanelMetricAdd from "./QueryPanelMetricAdd.vue";
import useLocale from "@/hooks/use-locale";
const { $t } = useLocale();
const formData = ref([
  { id: 1, name: "aaa" },
  { id: 2, name: "bbb" },
]);
const fields = ref([]);
const preferRawData = ref(false);
const errorMsg = ref("");
const svgImg = ref(settingSVG);
const isCanPutInTips = computed(() => {
  //   if (
  //     verifyRelation(
  //       props.metricType,
  //       formData.value.length,
  //       totalDimensions.value.length,
  //       true
  //     )
  //   ) {
  //     return $t("dashboards.当前配置已满");
  //   }
  //   if (computedMetricType.value === "none") {
  //     return $t("dashboards.无需配置");
  //   }
  //   if (computedMetricType.value === "single" && formData.value.length > 0) {
  //     return $t("dashboards.当前配置已满");
  //   }
  return "";
});
const verifyRelation = (rule, currentLength, targetLength, isAdd = false) => {
  if (!isObject(rule)) return null;

  // 假设 rule 是一个 DimensionRule 类型的对象
  const asRule = rule;

  if (asRule.relation && asRule.relation.length > 0) {
    let result = true;

    /** 关联条件中有一个命中即可 */
    if (!isAdd) {
      result = asRule.relation.some(({ condition, count }) => {
        const currResult = evaluateCondition(count, currentLength, false);
        const conditionResult = evaluateCondition(condition, targetLength, false);
        return conditionResult && currResult;
      });
    } else {
      result = asRule.relation.every(({ condition, count }) => {
        /** 这里注意evaluateCondition isAdd添加模式下 可添加返回结果是false  */
        const currResult = evaluateCondition(count, currentLength, isAdd);
        const conditionResult = evaluateCondition(condition, targetLength, false);
        if (!conditionResult) return true;
        // 添加验证情况下，如果依赖条件不符合则直接返回true 由后续取反返回结果即可
        return conditionResult && !currResult;
      });
    }

    return isAdd ? !result : result;
  }

  // 检查 rule 是否有 'count' 属性
  if (Object.prototype.hasOwnProperty.call(rule, "count")) {
    return evaluateCondition(asRule.count, currentLength, isAdd);
  }

  return null;
};
function addFormField(data) {
  if (!data?.name) return;
  const item = new QueryColumn(data);
  const name = item?.name;
  const exitActiveItem = namesMap.value?.names?.get(name);
  const aggregationOptions = getFileTypeAggregation(data.type);
  const tempArr = aggregationOptions?.filter((option) => !exitActiveItem?.has(option.id));

  if (!tempArr?.length) {
    Message({
      theme: "error",
      message: `${item.aggregate ? `[${item.aggregate}]` : ""}${item.name}，${t(
        "dashboards.已经存该字段，不可重复添加！"
      )}`,
    });
    return;
  }

  let temp;
  if (props.preferRawData) {
    temp = tempArr[tempArr.length - 1];
  } else {
    temp = tempArr[0];
  }

  item.aggregate = temp?.id ?? null;

  if (
    namesMap.value.names.has(item.name) &&
    namesMap.value.names.get(item.name).has(item.aggregate)
  ) {
    Message({
      theme: "error",
      message: `${item.aggregate ? `[${item.aggregate}]` : ""}${item.name}，${$t(
        "dashboards.已经存该字段，不可重复添加！"
      )}`,
    });
    return;
  }

  add(item);
}

function handleDragStart() {
  this.dragCount++;
}
function add(item) {
  formData.value.push(item);
  emit("change", item);
}
const namesMap = computed(() => {
  const names = new Map();
  const displayNames = [];

  formData.value.forEach(({ name, display_name, aggregate }) => {
    if (names.has(name)) {
      names.get(name).add(aggregate);
    } else {
      names.set(name, new Set([aggregate]));
    }
    displayNames.push(display_name);
  });

  return {
    names,
    displayNames,
  };
});
const addTag = () => {};
</script>
<template>
  <div class="settings">
    <!-- <div class="tagList">
      <div class="tagItem" v-for="item in formData" :key="item.id">
        <div>
          <img :src="svgImg" />
        </div>

        {{ item.name }}
      </div>
    </div> -->
    <Draggable
      :list="formData"
      handle=".dragging-handle"
      :group="{ name: 'fields', pull: 'clone', put: !isCanPutInTips }"
      tag="div"
      item-key="name"
      :class="[
        'panel-edit--query-fields flex-row align-items-center flex-wrap',
        {
          'panel-edit--query-has-error': errorMsg,
          'cursor-not-allow': isCanPutInTips,
        },
      ]"
      :beforeAdd="addFormField"
      @start="handleDragStart"
    >
      <template #item="{ element, index }">
        <div
          :key="element.name + element.aggregate + element.display_name"
          class="bv-query-field bv-query-field-metric flex-row align-items-center font-small"
        >
          <!-- <QueryFieldSetting
          v-model="formData[index]"
          :namesMap="namesMap"
          :index="index"
          :dragCount="dragCount"
          :dataset="dataset"
          @change="filed => $emit('change', filed)"
          @addOrder="$emit('addOrder', element)"
          @addWhere="$emit('addWhere', element)"
        /> -->
          <span class="pl-min dragging-handle field-max-width280">
            <!-- <OverflowTitle
            class="flex-1"
            type="tips"
            :key="Date.now()"
          >
            {{ getMetricName(element) }}
          </OverflowTitle> -->
          </span>

          <i
            @click="() => remove(index, element)"
            class="bv-query-field--remove cursor-pointer bkvision-icon icon-guanbi_mianxing"
          />
        </div>
      </template>
      <template #footer>
        <QueryPanelMetricAdd
          @add="add"
          :disabledTips="isCanPutInTips"
          :fields="fields"
          :namesMap="namesMap"
          :preferRawData="preferRawData"
        />
        <!-- <ClearFieldsButton
        v-show="formData.length"
        @clear="clearFields"
      /> -->
      </template>
    </Draggable>
    <!-- <i
      class="bv-query-field--remove cursor-pointer bkvision-icon icon-guanbi_mianxing"
    ></i>
    <div class="addTag" @click="addTag">+</div> -->
  </div>
</template>

<style lang="scss" scoped>
.settings {
  display: flex;

  .tagList {
    display: flex;
    height: 26px;
    line-height: 26px;

    .tagItem {
      display: inline-block;
      padding: 0 8px 0 4px;
      margin-left: 4px;
      color: white;
      background-color: #29bc9e;
      border-radius: 2px;
    }
  }

  .addTag {
    // display: inline-block;
    width: 26px;
    height: 26px;
    margin-left: 4px;
    font-size: 22px;
    line-height: 24px;
    color: #3a84ff;
    text-align: center;
    background: #e1ecff;
    border-radius: 2px;
  }
}
</style>
