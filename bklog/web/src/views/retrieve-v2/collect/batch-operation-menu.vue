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
  <div class="batch-operation-menu-container">
    <bk-popover
      ref="batchOperatePopoverRef"
      trigger="click"
      :arrow="false"
      theme="light"
      placement="bottom-start"
      boundary="viewport"
      extCls="batch-operation-menu"
      :interactive="true"
    >
      <bk-button :disabled="selectFavoriteList.length === 0">
        {{ $t("批量操作") }} <i class="bk-icon icon-angle-down" />
      </bk-button>
      <div slot="content">
        <div>
          <div class="batch-operation-menu-content">
            <bk-popover
              ref="operationMenuRef"
              placement="right-start"
              :arrow="false"
              theme="light"
              boundary="viewport"
              extCls="batch-operation-menu"
              @show="()=>handleShowOperationMenuRef(false)"
              @hide="()=>handleShowOperationMenuRef(true)"
            >
              <div class="operation-item">
                {{ $t("移动至分组") }}
                <i class="bk-icon icon-angle-right" />
              </div>
              <div slot="content">
                <div ref="batchMoveToGroupMenuRef" class="batch-move-to-group-menu-content">
                  <div class="group-list">
                    <div
                      v-for="group in favoriteGroupList"
                      :key="group.id"
                      class="group-item"
                      @click="() => handleBatchMoveToGroup(group.id)"
                    >
                      {{ group.name }}
                    </div>
                  </div>
                  <div class="add-group-item">
                    <template v-if="moveToGroupAddGroup">
                      <div class="add-group-input">
                        <bk-form
                          ref="checkInputAddFormRef"
                          style="width: 100%"
                          :label-width="0"
                          :model="addGroupData"
                          :rules="rules"
                        >
                          <bk-form-item property="name">
                            <bk-input
                              ref="moveToGroupInputRef"
                              v-model="addGroupData.name"
                            />
                          </bk-form-item>
                        </bk-form>
                        <i
                          class="bk-icon icon-check-line"
                          @click.stop="handleAddGroupConfirm"
                        />
                        <i
                          class="bk-icon icon-close-line-2"
                          @click="() => (moveToGroupAddGroup = false)"
                        />
                      </div>
                    </template>
                    <template v-else>
                      <div
                        class="add-group-btn"
                        @click="() => (moveToGroupAddGroup = true)"
                      >
                        <i class="bklog-icon icon-jia" />
                        <span>{{ $t("新建分组") }}</span>
                      </div>
                    </template>
                  </div>
                </div>
              </div>
            </bk-popover>
            <div class="operation-item" @click="handleShowBatchDeleteDialog">
              {{ $t("删除") }}
            </div>
          </div>

          <!-- 移动分组菜单 -->
        </div>
      </div>
    </bk-popover>

    <!-- 批量删除对话框 -->
    <bk-dialog
      :width="480"
      ext-cls="batch-delete-dialog"
      v-model="batchDeleteDialogVisible"
    >
      <template #header>
        <div class="dialog-content">
          <div class="title">{{ $t("确定删除选中的收藏项?") }}</div>
          <div class="tips">{{ $t("删除后，无法恢复，请谨慎操作!") }}</div>
          <div class="favorite-list">
            <div class="list-title">
              <i18n path="已选择以下{0}个收藏对象">
                <span class="count">{{ selectFavoriteList.length }}</span>
              </i18n>
            </div>
            <div class="list">
              <div
                v-for="item in selectFavoriteList"
                :key="item.id"
                class="item"
                v-bk-overflow-tips
              >
                {{ item.name }}
              </div>
            </div>
          </div>
        </div>
      </template>

      <template #footer>
        <div class="footer-wrap">
          <bk-button class="del-btn" theme="danger" @click="handleBatchDeleteFavorite">
            {{ $t("删除") }}
          </bk-button>
          <bk-button @click="() => (batchDeleteDialogVisible = false)">
            {{ $t("取消") }}
          </bk-button>
        </div>
      </template>
    </bk-dialog>
  </div>
</template>

<script setup>
import { ref, watch, computed, nextTick } from "vue";
import { bkMessage } from "bk-magic-vue";
import useLocale from "@/hooks/use-locale";
import useStore from "@/hooks/use-store";
import $http from "@/api";
const { $t } = useLocale();
const props = defineProps({
  selectFavoriteList: {
    type: Array,
    default: () => [],
  },
  favoriteType: {
    type: String,
    default: "event",
  },
  favoriteGroupList: {
    type: Array,
    default: () => [],
  },
});
const store = useStore();
const spaceUid = computed(() => store.state.spaceUid);
const emit = defineEmits(["operateChange"]);
const operationMenuRef = ref(null);
const batchMoveToGroupMenuRef = ref(null);
const moveToGroupInputRef = ref(null);
const checkInputAddFormRef = ref(null);
const batchOperatePopoverRef = ref(null);
const batchDeleteDialogVisible = ref(false);
const moveToGroupAddGroup = ref(false);

const addGroupData = ref({
  name: "",
});

const rules = {
  name: [
    { validator: checkName, message: $t("组名不规范, 包含了特殊符号."), trigger: "blur" },
    { validator: checkExistName, message: $t("注意: 名字冲突"), trigger: "blur" },
    { required: true, message: $t("必填项"), trigger: "blur" },
    { max: 30, message: $t("注意：最大值为30个字符"), trigger: "blur" },
  ],
};

function checkName() {
  if (addGroupData.value.name.trim() === "") return true;
  return /^[\u4e00-\u9fa5_a-zA-Z0-9`~!@#$%^&*()_\-+=<>?:"\s{}|,./;'\\[\]·~！@#￥%……&*（）——\-+={}|《》？：“”【】、；‘'，。、]+$/im.test(
    addGroupData.value.name.trim()
  );
}

function checkExistName() {
  return !props.favoriteGroupList.some((item) => item.name === addGroupData.value.name);
}

// 显示批量删除对话框
function handleShowBatchDeleteDialog() {
  batchDeleteDialogVisible.value = true;
  batchOperatePopoverRef.value?.hideHandler();;
}

// 批量删除收藏
async function handleBatchDeleteFavorite() {
  try {
    const res = await $http.request("favorite/batchFavoriteDelete", {
      data: {
        id_list: props.selectFavoriteList.map((item) => item.id),
      },
    });
    if (res.result) {
      bkMessage({ theme: "success", message: $t("批量删除成功") });
      batchDeleteDialogVisible.value = false;
      emit("operateChange");
    }
  } catch (error) {
    console.warn(error);
  }
}

// 批量移动分组
async function handleBatchMoveToGroup(id) {
  const params = props.selectFavoriteList.map((row) => {
    return {
      id: row.id,
      name: row.name,
      keyword: row.keyword,
      group_id: id,
      search_fields: row.search_fields,
      visible_type: row.visible_type,
      display_fields: row.display_fields,
      is_enable_display_fields: row.is_enable_display_fields,
      ip_chooser: row.params.ip_chooser,
      addition: row.params.addition,
      search_mode: row.search_mode,
    };
  });
  return $http
    .request("favorite/batchFavoriteUpdate", {
      data: {
        params,
      },
    })
    .then(() => {
      emit("operateChange", id);
      batchOperatePopoverRef.value?.hideHandler();;
    })
    .catch((error) => {
      console.error("Batch update failed", error);
    });
 
}

// 添加新分组确认
async function handleAddGroupConfirm() {
  try {
    await checkInputAddFormRef.value.validate();
    const data = { name: addGroupData.value.name, space_uid: spaceUid.value };
    const res = await $http
      .request(`favorite/createGroup`, {
        data,
      })
    moveToGroupAddGroup.value = false
    checkInputAddFormRef.value?.clearError();
    operationMenuRef.value?.hideHandler();
    handleBatchMoveToGroup(res.data.id)
  } catch (error) {
    console.error(error);
  }
}
function handleShowOperationMenuRef (val){
  batchOperatePopoverRef?.value.instance.set({ hideOnClick: val });
  moveToGroupAddGroup.value = false
}

// 表单输入焦点处理
watch(moveToGroupAddGroup, (val) => {
  if (val) {
    nextTick(() => {
      moveToGroupInputRef.value?.focus();
    });
  } else {
    addGroupData.value.name = "";
  }
});
</script>

<style lang="scss" scoped>
.batch-operation-menu-content {
  .operation-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-width: 106px;
    height: 32px;
    padding: 0 12px;
    font-size: 12px;
    color: #4d4f56;
    cursor: pointer;

    .icon-angle-right {
      font-size: 20px;
    }

    &:hover {
      background: #f5f7fa;
    }
  }
}
.tippy-popper.batch-move-to-group-menu {
  .tippy-tooltip {
    padding: 0;
    border: 1px solid #dcdee5;
    box-shadow: 0 2px 6px 0 #0000001a;
  }
}
.batch-move-to-group-menu-content {
  width: 240px;
  background-color: #fff;

  .group-list {
    max-height: 180px;
    padding: 4px 0;
    overflow-y: auto;

    .group-item {
      height: 32px;
      padding: 0 13px;
      font-size: 12px;
      line-height: 32px;
      color: #4d4f56;
      cursor: pointer;

      &:hover {
        background: #f5f7fa;
      }
    }
  }

  .add-group-item {
    height: 40px;
    padding: 0 12px;
    text-align: center;
    background: #fafbfd;
    border-top: 1px solid #dcdee5;
    border-radius: 0 0 2px 2px;

    .add-group-btn {
      font-size: 12px;
      line-height: 40px;
      color: #4d4f56;
      cursor: pointer;

      .icon-monitor {
        margin-right: 5px;
        font-size: 14px;
        color: #979ba5;
      }
    }

    .add-group-input {
      display: flex;
      align-items: center;
      margin-top: 4px;

      .bk-icon {
        cursor: pointer;
      }

      .icon-check-line {
        margin: 0 10px;
        font-size: 16px;
        color: #299e56;
      }

      .icon-close-line-2 {
        font-size: 16px;
        color: #e71818;
      }
    }
  }
}
</style>
<style lang="scss">
.batch-operation-menu {
  .tippy-tooltip {
    padding: 4px 0;
    border: 1px solid #dcdee5;
    box-shadow: 0 2px 6px 0 #0000001a;
  }
}
.batch-move-to-group-menu {
  .tippy-tooltip {
    padding: 0;
    border: 1px solid #dcdee5;
    box-shadow: 0 2px 6px 0 #0000001a;
  }
}
.bk-dialog-wrapper.batch-delete-dialog {
  .dialog-content {
    padding: 0 32px;
    text-align: left;
    .title {
      margin: 18px 0 24px;
      font-size: 20px;
      color: #313238;
      text-align: center;
    }

    .tips {
      padding: 0 16px;
      margin-bottom: 16px;
      line-height: 46px;
      background: #f5f7fa;
      border-radius: 2px;
      color: #63656e;
      font-size: 14px;
    }

    .favorite-list {
      border: 1px solid #eaebf0;
      border-radius: 2px;

      .list-title {
        padding: 0 16px;
        font-size: 14px;
        line-height: 32px;
        color: #313238;
        background: #f0f1f5;

        .count {
          font-weight: 700;
        }
      }

      .list {
        max-height: 160px;
        overflow-y: auto;

        .item {
          height: 32px;
          padding: 0 16px;
          overflow: hidden;
          font-size: 12px;
          line-height: 32px;
          color: #4d4f56;
          text-overflow: ellipsis;
          white-space: nowrap;

          &:nth-child(n) {
            background: #fff;
          }

          &:nth-child(2n) {
            background: #fafbfd;
          }
        }
      }
    }
  }

  .bk-dialog-footer {
    padding: 16px 32px 24px;
    background-color: #fff;
    border: none;

    .footer-wrap {
      text-align: center;
    }

    .bk-button {
      min-width: 88px;
    }

    .del-btn {
      margin-right: 8px;
    }
  }
}
</style>
