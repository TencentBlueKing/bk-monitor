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
import Vue, { computed, ref } from "vue";
import useLocale from "@/hooks/use-locale";
import useStore from "@/hooks/use-store";
import { useRoute } from "vue-router/composables";
import $http from "@/api";
import { RetrieveEvent } from '@/views/retrieve-helper';
import useRetrieveEvent from '@/hooks/use-retrieve-event';

const store = useStore();
const route = useRoute();
const { t } = useLocale();
const emit = defineEmits(["handle-popover-hide"]);
const showSlider = ref(false);
const sliderLoading = ref(false);
const confirmLoading = ref(false);
const formData = ref([]);
const fields = computed(() => store.state.indexFieldInfo.fields);
const globalsData = computed(() => store.getters["globals/globalsData"]);
const handleOpenSidebar = async () => {
  showSlider.value = true;
  emit("handle-popover-hide");
  addObject();
};

const { addEvent } =  useRetrieveEvent();
addEvent(RetrieveEvent.ALIAS_CONFIG_OPEN, () => {
   if (val) {
      handleOpenSidebar();
    }
});
// 提交
const submit = async () => {
  try {
    await checkQueryAlias();
    const alias_settings = formData.value
      .filter((item) => !item.is_objectKey)
      .reduce((acc, item) => {
        if (item.field_type !== "object") {
          acc.push({
            field_name: item.field_name,
            query_alias: item.query_alias,
            path_type: item.field_type,
          });
        } else if (item.children) {
          const childrenFields = item.children.map((child) => ({
            field_name: child.field_name,
            query_alias: child.query_alias,
            path_type: child.field_type,
          }));
          acc.push(...childrenFields);
        }
        return acc;
      }, [])
      .filter((item) => item.query_alias);
    const res = await $http.request("retrieve/updateFieldsAlias", {
      params: {
        index_set_id: route.params.indexId,
      },
      data: {
        alias_settings,
      },
    });

    if (res.code === 0) {
      showSlider.value = false;
      store.dispatch("requestIndexSetFieldInfo");
    }
  } catch (error) {
    console.error("Submit failed:", error);
  }
};
const handleCancel = () => {
  formData.value = [];
  showSlider.value = false;
};
const closeSlider = () => {
  formData.value = [];
};

// 展开对象按钮的回调
const expandObject = (row, show) => {
  row.expand = show;
  const index = formData.value.findIndex((item) => item.field_name === row.field_name);

  if (show) {
    if (index !== -1) {
      formData.value.splice(index + 1, 0, ...row.children);
    }
  } else {
    if (index !== -1) {
      const childrenCount = row.children ? row.children.length : 0;
      formData.value.splice(index + 1, childrenCount);
    }
  }
};
const aliasShow = (row) => {
  if (row.is_built_in) {
    return true;
  }
  return !row.alias_name;
};
const addObject = () => {
  const deepFields = structuredClone(
    fields.value
      .filter((fields) => fields.field_type !== "object")
      .map((item) => {
        return {
          ...item,
          aliasErr: "",
        };
      })
  );
  const keyFieldList = deepFields.filter((field) => field.field_name.includes("."));

  const objectFieldMap = new Map();
  fields.value.forEach((field) => {
  if (field.field_name.includes(".") || field.field_type == "object") {
      const fieldNamePrefix = field.field_name.split(".")[0].replace(/^_+|_+$/g, "");
      if (!objectFieldMap.has(fieldNamePrefix)) {
        objectFieldMap.set(fieldNamePrefix, {
          field_name: fieldNamePrefix,
          field_type: "object",
          is_built_in: true,
          children: undefined,
        });
      }
    }
  });
  keyFieldList.forEach((item) => {
    item.is_objectKey = true;
    const keyFieldPrefix = item.field_name.split(".")[0].replace(/^_+|_+$/g, "");
    const objectField = objectFieldMap.get(keyFieldPrefix);

    if (objectField) {
      if (!objectField.children) {
        objectField.children = [];
      }
      objectField.children.push(item);
    }
  });

  const normalFields = deepFields.filter(
    (field) => field.field_type !== "__virtual__" && !field.field_name.includes(".")
  );

  // 将对象字段分为有子项和无子项两类
  const objectFields = Array.from(objectFieldMap.values());
  const objectFieldsWithChildren = objectFields.filter(
    (field) => field.children?.length > 0
  );
  const objectFieldsWithoutChildren = objectFields.filter(
    (field) => !field.children || field.children.length === 0
  );

  formData.value = [
    ...objectFieldsWithChildren,
    ...normalFields,
    ...objectFieldsWithoutChildren,
  ];
};
// 校验别名
const checkQueryAlias = () => {
  return new Promise((resolve, reject) => {
    try {
      let result = true;
      formData.value.forEach((row) => {
        if (!checkQueryAliasItem(row)) {
          result = false;
        }
      });

      if (result) {
        resolve();
      } else {
        console.warn("QueryAlias校验错误");
        reject(result);
      }
    } catch (err) {
      console.warn("QueryAlias校验错误");
      reject(err);
    }
  });
};
const checkQueryAliasItem = (row) => {
  const { field_name: fieldName, query_alias: queryAlias } = row;
  if (queryAlias) {
    // 设置了别名
    if (!/^(?!^\d)[\w]+$/gi.test(queryAlias)) {
      row.aliasErr = $t("别名只支持【英文、数字、下划线】，并且不能以数字开头");

      return false;
    } else if (queryAlias === fieldName) {
      row.aliasErr = $t("别名与字段名重复");
      return false;
    }
    if (
      globalsData.value.field_built_in.find(
        (item) => item.id === queryAlias.toLocaleLowerCase()
      )
    ) {
      row.aliasErr = $t("别名不能与内置字段名相同");
      return false;
    }
  }
  row.aliasErr = "";
  return true;
};
defineExpose({
  handleOpenSidebar,
});
</script>
<template>
  <div class="field-alias-v3">
    <div class="bklog-v3 field-alias-title" @click="handleOpenSidebar">
      <span class="bklog-icon bklog-wholesale-editor"></span>{{ t("批量编辑别名") }}
    </div>
    <bk-sideslider
      :is-show.sync="showSlider"
      :quick-close="true"
      :title="$t('批量编辑变量别名')"
      :transfer="true"
      :width="640"
      @animation-end="closeSlider"
    >
      <template #header>
        <div>
          {{ t("批量编辑变量别名") }}
        </div>
      </template>
      <template #content>
        <div class="sideslider-content" v-bkloading="{ isLoading: sliderLoading }">
          <bk-table
            class="field-table field-alias-table"
            :data="formData"
            :empty-text="$t('暂无内容')"
            row-key="field_index"
            size="small"
            col-border
            custom-header-color="#F0F1F5"
            ref="fieldsTable"
          >
            <template>
              <bk-table-column :label="$t('字段名')" :resizable="true">
                <template #default="props">
                  <div
                    class="sideslider-field-name field-name-overflow-tips"
                    v-bk-overflow-tips
                  >
                    <span
                      v-if="props.row.children?.length && !props.row.expand"
                      @click="expandObject(props.row, true)"
                      class="ext-btn rotate bklog-icon bklog-arrow-down-filled"
                    >
                    </span>
                    <span
                      v-if="props.row.children?.length && props.row.expand"
                      @click="expandObject(props.row, false)"
                      class="ext-btn bklog-icon bklog-arrow-down-filled"
                    >
                    </span>

                    <!-- 如果为内置字段且有alias_name则优先展示alias_name -->
                    <div v-if="aliasShow(props.row)" class="field-name">
                      <span
                        v-if="props.row.is_objectKey"
                        class="bklog-icon bklog-subnode"
                      ></span>
                      {{ props.row.field_name }}
                    </div>
                    <div
                      v-else-if="props.row.is_built_in && props.row.alias_name"
                      class="field-name"
                    >
                      {{ props.row.alias_name }}
                    </div>
                  </div>
                </template>
              </bk-table-column>
              <bk-table-column :label="$t('别名')" :resizable="true">
                <template #default="props">
                  <div class="alias-container">
                    <div
                      v-if="props.row.field_type === 'object'"
                      class="ml8"
                      v-bk-tooltips.top="$t('object字段不支持编辑别名')"
                    >
                      --
                    </div>
                    <bk-input
                      v-else
                      class="alias-input"
                      v-model="props.row.query_alias"
                      :placeholder="$t('请输入')"
                      @blur="checkQueryAliasItem(props.row)"
                    >
                    </bk-input>
                    <template v-if="props.row.aliasErr">
                      <i
                        style="right: 8px"
                        class="bk-icon icon-exclamation-circle-shape tooltips-icon"
                        v-bk-tooltips.top="props.row.aliasErr"
                      ></i>
                    </template>
                  </div>
                </template>
              </bk-table-column>

              <div class="empty-text" slot="empty">
                {{ $t("暂无数据") }}
              </div>
            </template>
          </bk-table>
          <div class="submit-container">
            <bk-button
              class="king-button mr10"
              :loading="confirmLoading"
              theme="primary"
              @click.stop.prevent="submit"
            >
              {{ $t("保存") }}
            </bk-button>
            <bk-button @click="handleCancel">{{ $t("取消") }}</bk-button>
          </div>
        </div>
      </template>
    </bk-sideslider>
  </div>
</template>
<style lang="scss">
.field-alias-v3 {
  .field-alias-title {
    display: flex;
    align-items: center;
    font-size: 12px;
    color: #4d4f56;

    .bklog-wholesale-editor {
      margin-right: 4px;
      font-size: 12px;
    }
  }
}

.sideslider-content {
  min-height: 394px;
  max-height: calc(-119px + 100vh);
  padding: 24px 24px 0;
  overflow-y: auto;

  .field-alias-table {
    .bk-table-body-wrapper .cell {
      padding: 0;

      .sideslider-field-name {
        padding: 0 8px;
      }

      .field-name-overflow-tips {
        .ext-btn {
          position: absolute;
          left: 0;
          font-size: 18px;
          cursor: pointer;
        }

        .bklog-subnode {
          font-size: 16px;
        }

        .rotate {
          transform: rotate(-90deg);
        }

        .field-name {
          margin: 15px 10px 15px 15px;
        }
      }

      .alias-container {
        position: relative;

        .ml8 {
          margin-left: 8px;
        }

        .tooltips-icon {
          position: absolute;
          top: 14px;
          z-index: 10;
          font-size: 16px;
          color: #ea3636;
          cursor: pointer;
        }
      }

      .alias-input {
        input {
          height: 43px;
          border: none;
        }
      }
    }
  }

  .submit-container {
    position: fixed;
    bottom: 0;
    padding: 16px 0px 16px;

    button {
      width: 88px;
    }
  }
}
</style>
