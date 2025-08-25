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
<template>
  <div class="favorite-manage___favorite-detail-component">
    <div class="header-title">{{ $t("收藏详情") }}
      <span class="bklog-icon bklog-close" @click="handleCloseDialog" />
    </div>
    <div class="detail-items-wrap">
      <!-- 收藏名称 -->
      <div class="form-item">
        <div class="form-item-label">{{ $t("收藏名称") }}：</div>
        <div class="form-item-content">
          <template v-if="!nameLoading">
            <template v-if="!showNameInput">
              <span class="edit-name-wrap">
                <div class="edit-name">{{ value.name }}</div>
                <span class="bklog-icon bklog-edit" @click="handleEditName" />
              </span>
            </template>
            <template v-else>
              <bk-input
                class="edit-input-wrap"
                v-model="nameInput"
                @blur="handleUpdateName"
                @enter="handleUpdateName"
              />
            </template>
          </template>
          <div v-else class="skeleton-element input-loading" />
        </div>
      </div>

      <!-- 所属组 -->
      <div class="form-item">
        <div class="form-item-label">{{ $t("所属组") }}：</div>
        <div class="form-item-content">
          <template v-if="!groupLoading">
            <template v-if="!showGroupInput">
              <span class="edit-name-wrap">
                <div class="edit-name">{{ value.group_name }}</div>
                <span class="bklog-icon bklog-edit" @click="handleEditGroup" />
              </span>
            </template>
            <template v-else>
              <bk-select
                class="edit-input-wrap"
                v-model="groupInput"
                :clearable="false"
                @change="handleUpdateGroup"
              >
                <bk-option
                  v-for="item in groups"
                  :key="String(item.id)"
                  :id="String(item.id)"
                  :name="item.name"
                />
              </bk-select>
            </template>
          </template>
          <div v-else class="skeleton-element input-loading" />
        </div>
      </div>

      <!-- 数据ID -->
      <!-- <div v-if="favoriteType === 'event'" class="form-item">
        <div class="form-item-label">{{ $t("数据ID") }}：</div>
        <div class="form-item-content">
          <div class="item-name">{{ value.config.queryConfig.result_table_id }}</div>
        </div>
      </div> -->

      <!-- 查询语句 -->
      <div class="form-item">
        <div class="form-item-label">{{ $t("查询语句") }}：</div>
        <div class="form-item-content">
          <div class="query-content-wrap">
            <div class="query-string-wrap">{{ queryContent }}</div>
            <!-- <JsonFormatWrapper :data={queryContent} deep='5' /> -->
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from "vue";
import $http from "@/api";
import useLocale from "@/hooks/use-locale";
const { $t } = useLocale();

const props = defineProps({
  value: {
    type: Object,
    default: () => ({}),
  },
  groups: {
    type: Array,
    default: () => [],
  },
  favoriteType: {
    type: String,
    default: "event",
  },
});

const emit = defineEmits(["success","close"]);

const showNameInput = ref(false);
const nameInput = ref("");
const nameLoading = ref(false);
const showGroupInput = ref(false);
const groupInput = ref(null);
const groupLoading = ref(false);

const handleEditName = () => {
  showNameInput.value = true;
  showGroupInput.value = false;
  nameInput.value = props.value.name;
};

const handleEditGroup = () => {
  showGroupInput.value = true;
  showNameInput.value = false;
  groupInput.value = props.value.group_id;
};

const handleUpdateName = async () => {
  showNameInput.value = false;
  if (nameInput.value && nameInput.value !== props.value.name) {
    nameLoading.value = true;
    const params = {
      ...props.value,
      name: nameInput.value,
    };
    const success = await handleUpdateFavorite(params);
    nameLoading.value = false;
    success && emit("success", params);
  }
};

const handleUpdateGroup = async () => {
  showGroupInput.value = false;
  if (groupInput.value && groupInput.value !== props.value.group_id) {
    groupLoading.value = true;
    const group_name = props.groups.find(
      (item) => String(item.id) === String(groupInput.value)
    )?.name;
    const params = {
      ...props.value,
      group_id: groupInput.value === "null" ? null : groupInput.value,
    };
    const success = await handleUpdateFavorite(params);
    groupLoading.value = false;
    success &&
      emit("success", {
        ...params,
        group_name: group_name || props.value.group_name,
      });
  }
};

const handleUpdateFavorite = async (row) => {
  const params = [
    {
      id: row.id,
      name: row.name,
      keyword: row.keyword,
      group_id: row.group_id,
      search_fields: row.search_fields,
      visible_type: row.visible_type,
      display_fields: row.display_fields,
      is_enable_display_fields: row.is_enable_display_fields,
      ip_chooser: row.params.ip_chooser,
      addition: row.params.addition,
      search_mode: row.search_mode,
    },
  ];

  return $http
    .request("favorite/batchFavoriteUpdate", {
      data: {
        params,
      },
    })
    .then(() => {
      return Promise.resolve(true);
    })
    .catch((error) => {
      console.error("Batch update failed", error);
      return Promise.reject(error);
    });
};
function handleCloseDialog (){
  emit("close")
}
function mergeWhereList(source, target) {
  let result = [];
  const sourceMap = new Map();
  for (const item of source) {
    sourceMap.set(item.key, item);
  }
  const localTarget = [];
  for (const item of target) {
    const sourceItem = sourceMap.get(item.key);
    if (
      !(
        sourceItem &&
        sourceItem.key === item.key &&
        sourceItem.method === item.method &&
        JSON.stringify(sourceItem.value) === JSON.stringify(item.value) &&
        sourceItem?.options?.is_wildcard === item?.options?.is_wildcard
      )
    ) {
      localTarget.push(item);
    }
  }
  result = [...source, ...localTarget];
  return result;
}

const queryContent = computed(() => {
  return props.value.keyword;
});

watch(
  () => props.value,
  () => {
    showNameInput.value = false;
    showGroupInput.value = false;
    nameLoading.value = false;
    groupLoading.value = false;
  }
);
</script>

<style lang="scss" scoped>
.favorite-manage___favorite-detail-component {
  padding: 14px 16px;

  .header-title {
    display: flex;
    justify-content: space-between;
    margin-bottom: 12px;
    font-size: 16px;
    line-height: 24px;
    color: #313238;

    .bklog-close{
      cursor: pointer;
    }
  }

  .detail-items-wrap {
    .form-item {
      display: flex;
      align-items: flex-start;
      font-size: 12px;

      .form-item-label {
        width: 60px;
        margin: 6px 0;
        line-height: 20px;
        color: #4d4f56;
        text-align: right;
      }

      .form-item-content {
        display: flex;
        align-items: center;
        line-height: 20px;

        .input-loading {
          width: 248px;
          height: 20px;
          margin-top: 6px;
        }

        .edit-name-wrap {
          display: flex;
          align-items: flex-start;
          margin-top: 6px;

          .edit-name {
            line-height: 20px;
          }

          .bklog-edit {
            display: inline-block;
            width: 20px;
            height: 20px;
            margin-left: 4px;
            font-size: 16px;
            line-height: 20px;
            cursor: pointer;
          }
        }

        .item-name {
          margin-top: 6px;
        }

        .edit-input-wrap {
          width: 248px;
          background: #fff;
        }

        .query-content-wrap {
          position: relative;
          width: 440px;
          padding: 8px 12px;
          font-size: 12px;
          line-height: 18px;
          background: #f0f1f5;
          border-radius: 2px;

          .json-wrap {
            width: auto;
            max-height: 500px;
            overflow-y: auto;

            .vjs-tree {
              font-size: 12px;

              .vjs-value-string {
                tab-size: 3;
                white-space: pre-wrap;
              }

              .vjs-value__string {
                color: #1f6d89;
              }

              .vjs-key {
                color: #9d694c;
              }
            }
          }

          .promql-val {
            width: 100%;
            word-wrap: break-word;
          }
        }
      }
    }
  }
}
</style>
