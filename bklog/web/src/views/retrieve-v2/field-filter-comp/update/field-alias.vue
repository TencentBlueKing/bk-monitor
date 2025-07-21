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
const store = useStore();
const route = useRoute();
const { t } = useLocale();
const emit = defineEmits(["handle-popover-hide"]);
const showSlider = ref(false);
const sliderLoading = ref(false);
const confirmLoading = ref(false);
const formData = ref([]);
const fields = computed(() => store.state.indexFieldInfo.fields);
const handleOpenSidebar = async () => {
  showSlider.value = true;
  emit("handle-popover-hide");
  formData.value = fields.value.map((item) => {
    return {
      field_name: item.field_name,
      query_alias: item.query_alias,
      path_type: item.path_type,
    };
  });
};
const submit = async () => {
  const res = await $http.request("retrieve/updateFieldsAlias", {
    params: {
      index_set_id: route.params.indexId,
    },
    data: {
      alias_settings: formData.value,
    }
  });
  if (res.code === 0) {
    showSlider.value = false;
    location.reload();
  }
};
const handleCancel = () => {
  showSlider.value = false;
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
    >
      <template #header>
        <div>
          {{ t("批量编辑变量别名") }}
        </div>
      </template>
      <template #content>
        <div class="sideslider-content">
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
                  <div class="sideslider-field-name">{{ props.row.field_name }}</div>
                </template>
              </bk-table-column>
              <bk-table-column :label="$t('别名')" :resizable="true">
                <template #default="props">
                  <bk-input
                    class="alias-input"
                    v-model="props.row.query_alias"
                    :placeholder="$t('请输入')"
                  >
                  </bk-input>
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
