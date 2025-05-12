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
  <bk-dialog
    width="100%"
    v-model="modelValue"
    :position="{
      top: 50,
      left: 0,
    }"
    :close-icon="false"
    :draggable="false"
    :scrollable="true"
    :show-footer="false"
    :show-mask="false"
    @value-change="initData"
  >
    <div class="favorite-group-dialog-header">
      {{ $t("收藏管理") }}
      <i class="bk-icon icon-close close-icon" @click="handleShowChange(false)" />
    </div>
    <div class="favorite-group-dialog-content">
      <div class="favorite-group-filter">
        <div class="group-type-container">
          <div
            :class="['group-item', { active: curSelectGroup === 'all' }]"
            @click="handleSelectGroupChange('all')"
          >
            <i class="bklog-icon icon-all" />
            <span class="group-name">{{ $t("全部收藏") }}</span>
            <span class="favorite-count">{{ allGroupList.length }}</span>
          </div>
          <div
            :class="['group-item', { active: curSelectGroup === 'noGroup' }]"
            @click="handleSelectGroupChange('noGroup')"
          >
            <i class="bklog-icon bklog-file-close" />
            <span class="group-name">{{ $t("未分组") }}</span>
            <span class="favorite-count">{{ noGroupList.length }}</span>
          </div>
          <div
            :class="['group-item', { active: curSelectGroup === 'private' }]"
            @click="handleSelectGroupChange('private')"
          >
            <i class="bklog-icon bklog-file-personal" />
            <span class="group-name">{{ $t("个人收藏") }}</span>
            <span class="favorite-count">{{ privateFavorite.length }}</span>
          </div>
        </div>
        <div class="search-input-container">
          <bk-popover
            ref="addGroupPopover"
            ext-cls="new-add-group-popover"
            :tippy-options="{
              trigger: 'click',
              interactive: true,
              theme: 'light',
            }"
            placement="bottom-start"
            @hide="handleAddGroupPopoverHidden(false)"
          >
            <template #content>
              <div>
                <bk-form
                  ref="checkInputForm"
                  style="width: 100%"
                  form-type="vertical"
                  :model="addGroupData"
                  :rules="rules"
                >
                  <bk-form-item :label="$t('分组名称')" property="name" required>
                    <bk-input
                      v-model="addGroupData.name"
                      :placeholder="$t('输入组名,30个字符')"
                    />
                  </bk-form-item>
                </bk-form>
                <div class="operate-button">
                  <bk-button size="small" theme="primary" @click="handleAddGroupConfirm">
                    {{ $t("确定") }}
                  </bk-button>
                  <bk-button size="small" @click="handleAddGroupPopoverHidden">
                    {{ $t("取消") }}
                  </bk-button>
                </div>
              </div>
            </template>
            <div class="add-group-btn">
              <i class="bk-icon icon-plus-line" />
            </div>
          </bk-popover>

          <bk-input
            class="search-input"
            v-model="groupSearchValue"
            :allow-emoji="false"
            :right-icon="'bk-icon icon-search'"
            clearable
            show-clear-only-hover
            @input="handleGroupSearch"
            @right-icon-click="handleGroupSearch"
          />
        </div>
        <div class="group-list">
          <div
            v-for="group in searchResultGroupList"
            :key="group.id"
            :class="['group-item', { active: curSelectGroup === group.id }]"
            @click="handleSelectGroupChange(group.id)"
          >
            <i class="bklog-icon bklog-file-close" />
            <span class="group-name">{{ group.name }}</span>
            <span class="favorite-count">{{ group.favorites?.length }}</span>
          </div>
        </div>
      </div>
      <div class="favorite-table-container">
        <div class="table-header-operation">
          <!-- <BatchOperationMenu
            :favorite-group-list="localFavoriteList"
            :favorite-type="favoriteType"
            :select-favorite-list="selectFavoriteList"
            @operate-change="handleOperateChange"
          /> -->
          <bk-input
            class="favorite-search-input"
            v-model="favoriteSearchValue"
            :allow-emoji="false"
            :right-icon="'bk-icon icon-search'"
            clearable
            show-clear-only-hover
            @input="handleFavoriteSearch"
            @right-icon-click="handleFavoriteSearch"
          />
        </div>
        <div class="table-content">
          <bk-table
            ref="favoriteTable"
            :data="searchResultFavorites"
            :max-height="525"
            :row-class-name="getRowClassName"
            @row-click="(row) => (curClickRow = row)"
            @row-mouse-enter="(index) => (curHoverRowIndex = index)"
            @row-mouse-leave="curHoverRowIndex = -1"
            @selection-change="handleTableSelectionChange"
          >
            <bk-table-column width="45" type="selection" />
            <bk-table-column :label="$t('收藏名称')" prop="name">
              <template #default="{ row }">
                <div>
                  <div
                    v-if="!row.editName"
                    class="edit-cell"
                    @click="handleEditName(row)"
                  >
                    <span class="text name">{{ row.name }}</span>
                    <i class="bklog-icon bklog-edit" />
                  </div>
                  <bk-input
                    v-else
                    ref="editFavoriteNameInput"
                    :value="row.name"
                    @blur="(val) => handleEditFavoriteName(val, row)"
                    @enter="(val) => handleEditFavoriteName(val, row)"
                  ></bk-input>
                </div>
                <!-- {{ favoriteNameScopedSlots(row) }} -->
              </template>
            </bk-table-column>
            <bk-table-column :label="$t('所属组')" prop="groupName">
              <template #default="{ row }">
                <!-- {{ groupScopedSlots(row) }} -->
                <div
                  v-if="!row.editGroup"
                  class="edit-cell"
                  @click="handleEditGroup(row)"
                >
                  <span class="text">{{ row.group_name }}</span>
                  <i class="bklog-icon bklog-edit" />
                </div>
                <bk-select
                  v-else
                  class="edit-favorite-group"
                  :model-value="row.group_id"
                  :clearable="false"
                  @selected="(val) => handleEditFavoriteGroup(val, row)"
                >
                  <bk-option
                    v-for="item in localFavoriteList"
                    :key="item.id"
                    :id="String(item.id)"
                    :name="item.name"
                  />
                </bk-select>
              </template>
              <template #filter>
                <bk-checkbox-group :value="[]" @change="handleGroupFilterChange">
                  <bk-checkbox
                    v-for="filter in tableFilters.groups"
                    :key="filter.value"
                    :value="filter.value"
                  >
                    {{ filter.text }}
                  </bk-checkbox>
                </bk-checkbox-group>
              </template>
            </bk-table-column>
            <template v-if="favoriteType === 'event'"> </template>
            <bk-table-column :label="$t('变更人')" prop="updated_by">
              <template #filter>
                <bk-checkbox-group :value="[]" @change="handleNameFilterChange">
                  <bk-checkbox
                    v-for="filter in tableFilters.names"
                    :key="filter.value"
                    :value="filter.value"
                  >
                    {{ filter.text }}
                  </bk-checkbox>
                </bk-checkbox-group>
              </template>
            </bk-table-column>
            <bk-table-column :label="$t('变更时间')" prop="update_time" sortable>
              <template #default="{ row }">
                {{ dayjs(row.update_time).format("YYYY-MM-DD HH:mm:ss") }}
              </template>
            </bk-table-column>
            <bk-table-column :label="$t('操作')" prop="operation" width="80">
              <template #default="{ row }">
                <span class="del-btn" @click="handleOperateChange(row)">
                  {{ $t("删除") }}
                </span>
              </template>
            </bk-table-column>
          </bk-table>
        </div>
      </div>
      <!-- <div v-if="curClickRow" class="favorite-detail-container">
        <FavoriteDetail
          :favorite-type="favoriteType"
          :groups="groups"
          :value="curClickRow"
          @success="handleDetailUpdate"
        />
      </div> -->
    </div>
  </bk-dialog>
</template>

<script setup>
import { defineProps, defineEmits, computed, ref, onMounted, onBeforeUnmount } from "vue";
import { bkInfoBox } from "bk-magic-vue";
import $http from "@/api";
import useStore from "@/hooks/use-store";
import useLocale from "@/hooks/use-locale";
import dayjs from "dayjs";
const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["close", "submit"]);
const store = useStore();
const { $t } = useLocale();
const groupNameMap = ref({
  unknown: $t("未分组"),
  private: $t("个人收藏"),
});
const spaceUid = computed(() => store.state.spaceUid);
const groupList = ref([]);
const unPrivateList = ref([]);
const privateList = ref([]);
const sourceFilters = ref([]);
const unknownGroupID = ref(0);
const privateGroupID = ref(0);

const curSelectGroup = ref("all");
const groupSearchValue = ref("");
const favoriteSearchValue = ref("");
const curClickRow = ref(null);
const curHoverRowIndex = ref(-1);
const selectFavoriteList = ref([]);
const addGroupData = ref({ name: "" });
const localFavoriteList = ref([]);
const allGroupList = ref([]);
const noGroupList = ref([]);
const otherGroupList = ref([]);

const privateFavorite = ref([]);
const searchResultGroupList = ref([]);
const searchResultFavorites = ref([]);
const favoriteType = ref("event");

const addGroupPopoverRef = ref();
const checkInputFormRef = ref();
const favoriteTableRef = ref();

const groupTypes = computed(() => [
  // { id: 'all', name: '全部收藏', icon: 'icon-all', count: allGroupList.value.length },
  // { id: 'noGroup', name: '未分组', icon: 'icon-mc-file-close', count: noGroupList.value.length },
  // { id: 'private', name: '个人收藏', icon: 'icon-file-personal', count: privateFavorite.value.length }
]);
const rules = {
  name: [
    { validator: checkName, message: $t("组名不规范"), trigger: "blur" },
    { validator: checkExistName, message: $t("名称冲突"), trigger: "blur" },
    { required: true, message: $t("必填项"), trigger: "blur" },
    { max: 30, message: $t("最大30字符"), trigger: "blur" },
  ],
};

const checkName = () => /^[\u4e00-\u9fa5\w\s\-\+]+$/.test(addGroupData.value.name);
const checkExistName = () =>
  !localFavoriteList.value.some((item) => item.name === addGroupData.value.name);

onMounted(() => {
  window.addEventListener("keydown", handleKeydown);
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", handleKeydown);
});
const initData = async () => {
  await getGroupList();
  getFavoriteList();
};

const handleShowChange = () => {
  console.log("Closing dialog...", emit);
  emit("close", false);
};
/** 获取组列表 */
const getGroupList = async (isAddGroup = false) => {
  try {
    const res = await $http.request("favorite/getGroupList", {
      query: {
        space_uid: spaceUid.value,
      },
    });
    console.log(res);
    otherGroupList.value = res.data
      .filter((item) => item.name !== "未分组" && item.name !== "个人收藏")
      .map((item) => {
        return {
          ...item,
          favorites: [],
        };
      });

    handleGroupSearch();
  } catch (error) {
    console.warn(error);
  } finally {
    //   if (isAddGroup) {
    //     // 如果是新增组 则刷新操作表格的组列表
    //     this.operateTableList = this.operateTableList.map((item) => ({
    //       ...item,
    //       group_option: this.unPrivateList,
    //       group_option_private: this.privateList,
    //     }));
    //     this.handleSearchFilter();
    // }
  }
};

/** 获取收藏请求 */
const getFavoriteList = async () => {
  try {
    // this.tableLoading = true;
    const res = await $http.request("favorite/getFavoriteList", {
      query: {
        space_uid: spaceUid.value,
        order_type: "NAME_ASC",
      },
    });
    const data = res.data.map((item) => {
      return {
        ...item,
        editName: false,
        editGroup: false,
      };
    });
    const groupMap = new Map(otherGroupList.value.map((group) => [group.id, group]));
    [allGroupList.value, noGroupList.value, privateFavorite.value] = data.reduce(
      (acc, item) => {
        acc[0].push(item);

        if (item.group_name === "未分组") {
          acc[1].push(item);
        } else if (item.group_name === "个人收藏") {
          acc[2].push(item);
        } else {
          const group = groupMap.get(item.group_id);
          group?.favorites.push(item);
        }

        return acc;
      },
      [[], [], []]
    );
    searchResultFavorites.value = allGroupList.value;
  } catch (error) {
    // this.emptyType = "500";
  } finally {
    // this.tableLoading = false;
    // this.handleSearchFilter();
  }
};

/** 切换分组，获取收藏列表 */
const handleSelectGroupChange = (id) => {
  curSelectGroup.value = id;
  selectFavoriteList.value = [];
  let curSelectGroupFavorites = [];

  switch (id) {
    case "all":
      curSelectGroupFavorites = allGroupList.value;
      break;
    case "noGroup":
      curSelectGroupFavorites = noGroupList.value;
      break;
    case "private":
      curSelectGroupFavorites = privateFavorite.value;
      break;
    default:
      curSelectGroupFavorites =
        otherGroupList.value.find((item) => item.id === id)?.favorites || [];
  }

  searchResultFavorites.value = curSelectGroupFavorites.map((favorite) => ({
    ...favorite,
    editName: false,
    editGroup: false,
    groupName: localFavoriteList.value.find((item) => item.id === favorite.group_id)
      ?.name,
  }));
};
/** 组搜索 */
const handleGroupSearch = () => {
  searchResultGroupList.value = otherGroupList.value.filter((group) => {
    return group.name.includes(groupSearchValue.value);
  });
};
/** 收藏列表搜索 */
const handleFavoriteSearch = () => {
  searchResultFavorites.value = searchResultFavorites.value.filter((favorite) =>
    favorite.name.includes(favoriteSearchValue.value)
  );
};

const handleOperateChange = (row) => {
  bkInfoBox({
    subTitle: $t("当前收藏名为 {n}，确认是否删除？", { n: row.name }),
    type: "warning",
    confirmFn: () => {

      // 发送删除请求
      $http.request("favorite/deleteFavorite", {
        params: { favorite_id: row.id },
      });
    },
  });
};
/** 添加行类名 */
const getRowClassName = ({ row, rowIndex }) => {
  const styles = [];
  if (row.id === curClickRow.value?.id) styles.push("row-click");
  if (rowIndex === curHoverRowIndex.value) styles.push("row-hover");
  return styles.join(" ");
};

const handleTableSelectionChange = (selection) => {
  selectFavoriteList.value = selection;
};
/** 添加分组 */
const handleAddGroupConfirm = async () => {
  try {
    await checkInputFormRef.value.validate();
    await createFavoriteGroup({
      type: favoriteType.value,
      name: addGroupData.value.name,
    });
    handleAddGroupPopoverHidden();
    handleOperateChange("request-query-history");
  } catch (error) {
    console.error(error);
  }
};
/** 隐藏添加分组popover */
const handleAddGroupPopoverHidden = (close = true) => {
  addGroupData.value.name = "";
  checkInputFormRef.value?.clearValidate();
  if (close) {
    addGroupPopoverRef.value?.hide();
  }
};
const handleEditGroup = () => {
  row.editGroup = true;
  for (const favorite of this.searchResultFavorites) {
    if (favorite.id !== row.id) {
      favorite.editGroup = false;
    }
  }
};
const handleEditName = (row) => {
  row.editName = true;
  row.editGroup = false;
  // nextTick(() => {
  //   this.favoriteTableRef?.$refs?.editFavoriteNameInput?.focus();
  // });
};

const handleEditFavoriteName = (val, row) => {
  if (val !== row.name) {
    this.handleUpdateFavorite({
      id: row.id,
      group_id: row.group_id,
      name: val,
      config: row.config,
    }).then(() => {
      row.editName = false;
      row.name = val;
      this.curClickRow = row;
    });
  } else {
    row.editName = false;
  }
};
const handleEditFavoriteGroup = (val, row) => {
  if (val === String(row.group_id)) {
    row.editGroup = false;
  } else {
    this.handleUpdateFavorite({
      id: row.id,
      group_id: JSON.parse(val),
      name: row.name,
      config: row.config,
    }).then(() => {
      row.editName = false;
      row.group_id = JSON.parse(val);
      row.groupName = this.groups.find((item) => item.id === JSON.parse(val))?.name;
      this.curClickRow = row;
    });
  }
};
const handleKeydown = (event) => {
  if (event.key === "Escape" || event.key === "Esc") {
    handleShowChange(false);
  }
};
</script>

<style lang="scss" scoped>
:deep(.bk-dialog) {
  height: calc(100% - 50px);
  .bk-dialog-content {
    height: 100%;
    .bk-dialog-body {
      padding: 0;
      overflow: hidden;
      background-color: #f5f6fa;
      height: 100%;
    }
  }
}

:deep(.bk-dialog-tool) {
  display: none;
}

.favorite-group-dialog-header {
  position: relative;
  width: 100%;
  height: 48px;
  font-size: 16px;
  line-height: 48px;
  color: #313238;
  text-align: center;
  background: #ffffff;
  box-shadow: 0 1px 4px 0 #00000014;

  .close-icon {
    position: absolute;
    top: 8px;
    right: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    overflow: hidden;
    font-size: 32px;
    color: #63656e;
    cursor: pointer;
  }
}

.favorite-group-dialog-content {
  position: relative;
  display: flex;
  width: 100%;
  height: calc(100% - 48px);
  background-color: #ffffff;
  .favorite-group-filter {
    display: flex;
    flex-direction: column;
    width: 220px;
    padding: 12px 0;
    background-color: #f5f7fa;

    .group-type-container {
      padding-bottom: 4px;
      border-bottom: 1px solid #dcdee5;
    }

    .search-input-container {
      display: flex;
      padding: 13px 16px 8px;

      .add-group-btn {
        width: 32px;
        height: 32px;
        font-size: 16px;
        line-height: 32px;
        color: #3a84ff;
        text-align: center;
        cursor: pointer;
        background: #cddffe;
        border-radius: 2px;
      }

      .search-input {
        flex: 1;
        flex-shrink: 0;
        margin-left: 8px;
      }
    }

    .group-list {
      flex: 1;
      overflow-y: auto;
    }

    .group-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      height: 32px;
      padding: 0 20px;
      cursor: pointer;

      .bklog-icon {
        font-size: 16px;
        color: #a3b1cc;
      }

      .group-name {
        margin: 0 auto 0 6px;
        font-size: 13px;
        color: #4d4f56;
      }

      .add-group-btn {
      }
      .favorite-count {
        font-size: 12px;
        font-weight: 700;
        color: #a3b1cc;
      }

      &:hover {
        background: #f5f7fa;
      }

      & + .group-item {
        margin-top: 4px;
      }

      &.active {
        background: #e1ecff;

        .bklog-icon,
        .group-name,
        .favorite-count {
          color: #3a84ff;
        }
      }
    }
  }

  .favorite-table-container {
    flex: 1;
    width: calc(100% - 760px);
    padding: 12px;

    .table-header-operation {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 12px;

      .favorite-search-input {
        width: 468px;
      }
    }

    .table-content {
      height: calc(100% - 68px);

      .bk-table-row {
        &.row-hover {
          cursor: pointer;
          background: #f5f7fa;

          .bklog-edit {
            display: block;
          }
        }

        &.row-click {
          background: #f0f5ff;
        }

        .cell {
          font-size: 13px;
        }

        .edit-favorite-group {
          background-color: #fff;
        }
      }

      .edit-cell {
        display: flex;
        align-items: center;
        cursor: pointer;

        .text {
          overflow: hidden;
          font-size: 13px;
          text-overflow: ellipsis;
          white-space: nowrap;

          &.name {
            color: #3a84ff;
          }
        }

        .bklog-edit {
          display: none;
          font-size: 16px;
          color: #979ba5;
        }
      }

      .del-btn {
        color: #3a84ff;
        cursor: pointer;
      }
    }
  }

  .favorite-detail-container {
    width: 540px;
    background: #f5f7fa;
  }
}
</style>
