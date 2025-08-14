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
    @value-change="(val)=>initData(val)"
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
            <i class="bklog-icon bklog-all" />
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
            ref="addGroupPopoverRef"
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
                  ref="checkInputFormRef"
                  style="width: 100%"
                  form-type="vertical"
                  :model="addGroupData"
                  :rules="rules"
                >
                  <bk-form-item :label="$t('分组名称')" property="name" required>
                    <bk-input
                      v-model="addGroupData.name"
                      :placeholder="$t('请输入组名')"
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
          <BatchOperationMenu
            :favorite-group-list="localFavoriteList"
            :favorite-type="favoriteType"
            :select-favorite-list="selectFavoriteList"
            @operateChange="handleBatchUpdateGroup"
          />
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
            ref="favoriteTableRef"
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
                    ref="editFavoriteNameInputRef"
                    :value="row.name"
                    @blur="(val) => handleEditFavoriteName(val, row)"
                    @enter="(val) => handleEditFavoriteName(val, row)"
                  ></bk-input>
                </div>
              </template>
            </bk-table-column>
            <bk-table-column
              :label="$t('所属组')"
              prop="group_name"
              :filters="tableFilters.groups"
              filter-multiple
              :filter-method="sourceFilterMethod"
            >
              <template #default="{ row }">
                <div
                  v-if="!row.editGroup"
                  class="edit-cell"
                  @click.stop="handleEditGroup(row)"
                >
                  <span class="text">{{ row.group_name }}</span>
                  <i class="bklog-icon bklog-edit" />
                </div>
                <bk-select
                  v-else
                  class="edit-favorite-group"
                  ref="editFavoriteNameSelectRef"
                  :model-value="row.group_id"
                  :clearable="false"
                  @toggle="(val) => handleToggle(val, row)"
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
            </bk-table-column>
            <bk-table-column
              :label="$t('变更人')"
              prop="updated_by"
              :filters="tableFilters.names"
              filter-multiple
              :filter-method="sourceFilterMethod"
            >
            </bk-table-column>
            <bk-table-column :label="$t('变更时间')" prop="updated_at" sortable>
              <template #default="{ row }">
                {{ dayjs(row.updated_at).format("YYYY-MM-DD HH:mm:ss") }}
              </template>
            </bk-table-column>
            <bk-table-column :label="$t('操作')" prop="operation" width="80">
              <template #default="{ row }">
                <span class="del-btn" @click="handleDelete(row)">
                  {{ $t("删除") }}
                </span>
              </template>
            </bk-table-column>
          </bk-table>
        </div>
      </div>
      <div v-if="curClickRow" class="favorite-detail-container">
        <FavoriteDetail
          :favorite-type="favoriteType"
          :groups="groups"
          :value="curClickRow"
          @success="handleDetailUpdate"
          @close="handleDetailClose"
        />
      </div>
    </div>
  </bk-dialog>
</template>

<script setup>
import {
  defineProps,
  defineEmits,
  computed,
  ref,
  nextTick,
  watch,
} from "vue";
import { bkInfoBox } from "bk-magic-vue";
import $http from "@/api";
import useStore from "@/hooks/use-store";
import useLocale from "@/hooks/use-locale";
import BatchOperationMenu from "./batch-operation-menu";
import FavoriteDetail from "./favorite-detail";
import dayjs from "dayjs";
const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["close"]);
const store = useStore();
const { $t } = useLocale();
const spaceUid = computed(() => store.state.spaceUid);
const groups = computed(() => {
  return localFavoriteList.value.map((item) => ({
    id: item.id,
    name: item.name,
  }));
});
const searchResultGroupList = computed(() => {
  return otherGroupList.value.filter((group) => {
    return group.name.includes(groupSearchValue.value);
  });
});
const tableFilters = computed(() => {
  const names = {};
  const groups = {};

  for (const item of allGroupList.value) {
    if (!names[item.updated_by]) {
      names[item.updated_by] = item.updated_by;
    }
    if (item.group_id && !groups[item.group_id]) {
      groups[item.group_id] = item.group_id;
    }
  }

  return {
    names: Object.values(names).map((text) => ({ text, value: text })),
    groups: Object.values(groups).map((value) => {
      const group = localFavoriteList.value.find((g) => g.id === value);
      return {
        text: group?.name,
        value: group?.name,
      };
    }),
  };
});
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
const searchResultFavorites = ref([]);
const favoriteType = ref("event");

const addGroupPopoverRef = ref(null);
const checkInputFormRef = ref(null);
const favoriteTableRef = ref(null);
const editFavoriteNameInputRef = ref(null);
const editFavoriteNameSelectRef = ref(null);

const rules = {
  name: [
    { validator: () => /^[\u4e00-\u9fa5\w\s\-\+]+$/.test(addGroupData.value.name), message: $t("组名不规范"), trigger: "blur" },
    { validator:  () => !localFavoriteList.value.some((item) => item.name === addGroupData.value.name), message: $t("名称冲突"), trigger: "blur" },
    { required: true, message: $t("必填项"), trigger: "blur" },
    { max: 30, message: $t("最大30字符"), trigger: "blur" },
  ],
};


watch(() => [props.modelValue], () => {
  if (props.modelValue) {
    window.addEventListener("keydown", handleKeydown);
  } else {
    nextTick(() => {
      window.removeEventListener("keydown", handleKeydown);
    })
  }
})

watch(
  allGroupList,
  (newValue, oldValue) => {
    const groupMap = new Map(
      otherGroupList.value.map((group) => {
        return [group.id, { ...group, favorites: [] }];
      })
    );
    const initialOtherGroups = Array.from(groupMap.values());
    const [noGroupItems, privateItems, otherGroupItems] = newValue.reduce(
      (acc, item) => {
        if (item.group_name === "未分组") {
          acc[0].push(item);
        } else if (item.group_name === "个人收藏") {
          acc[1].push(item);
        } else {
          const group = groupMap.get(item.group_id);
          if (group) {
            group.favorites.push(item);
          }
        }
        return acc;
      },
      [[], [], initialOtherGroups]
    );

    noGroupList.value = noGroupItems;
    privateFavorite.value = privateItems;
    otherGroupList.value = otherGroupItems;
  },
  { deep: true }
);
const initData = async ( val=true ) => {
  if (val) {
    await getGroupList();
    await getFavoriteList();
  }
};

const handleShowChange = () => {
  emit("close", false);
};
/** 获取组列表 */
const getGroupList = async () => {
  try {
    const res = await $http.request("favorite/getGroupList", {
      query: {
        space_uid: spaceUid.value,
      },
    });
    otherGroupList.value = res.data
      .filter((item) => item.name !== "未分组" && item.name !== "个人收藏")
      .map((item) => {
        return {
          ...item,
          favorites: [],
        };
      });
    localFavoriteList.value = res.data;

    handleGroupSearch();
  } catch (error) {
    console.warn(error);
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
    allGroupList.value = data;

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
const handleGroupSearch = () => {};
/** 收藏列表搜索 */
const handleFavoriteSearch = () => {
  searchResultFavorites.value = searchResultFavorites.value.filter((favorite) =>
    favorite.name.includes(favoriteSearchValue.value)
  );
};
/** 删除单个收藏 */
const handleDelete = (row) => {
  bkInfoBox({
    subTitle: $t("当前收藏名为 {n}，确认是否删除？", { n: row.name }),
    type: "warning",
    confirmFn: async () => {
      const res = await $http.request("favorite/deleteFavorite", {
        params: { favorite_id: row.id },
      });
      if (res.result) {
        allGroupList.value = allGroupList.value.filter((item) => item.id !== row.id);
      }
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
    const data = { name: addGroupData.value.name, space_uid: spaceUid.value };
    await $http
      .request(`favorite/createGroup`, {
        data,
      })

    handleAddGroupPopoverHidden();
    initData();
  } catch (error) {
    console.error(error);
  }
};
/** 隐藏添加分组popover */
const handleAddGroupPopoverHidden = (close = true) => {
  addGroupData.value.name = "";
  checkInputFormRef.value?.clearError();
  if (close) {
    addGroupPopoverRef.value?.hideHandler();
  }
};
const handleEditGroup = (row) => {
  row.editGroup = true;
  for (const favorite of searchResultFavorites.value) {
    if (favorite.id !== row.id) {
      favorite.editGroup = false;
    }
  }
  nextTick(() => {
    editFavoriteNameSelectRef?.value.show();
  });
};
const handleEditName = (row) => {
  row.editName = true;
  row.editGroup = false;
  nextTick(() => {
    editFavoriteNameInputRef?.value.focus();
  });
};
const handleToggle = (val,row) => {
  if(!val){
    row.editGroup = false;
  }
}
const handleEditFavoriteName = (val, row) => {
  if (val !== row.name) {
    const updatedRow = {
      ...row,
      name: val,
    };
    handleUpdateFavorite(updatedRow).then(() => {
      row.editName = false;
      row.name = val;
      curClickRow.value = row;
    });
  } else {
    row.editName = false;
  }
};
const handleEditFavoriteGroup = (val, row) => {
  if (val === String(row.group_id)) {
    row.editGroup = false;
  } else {
    const updatedRow = {
      ...row,
      group_id: JSON.parse(val),
    };
    handleUpdateFavorite(updatedRow).then(() => {
      row.editGroup = false;
      row.group_id = JSON.parse(val);
      row.group_name = localFavoriteList.value.find(
        (item) => item.id === JSON.parse(val)
      )?.name;
      curClickRow.value = row;
    });
  }
};
const handleKeydown = (event) => {
  if (event.key === "Escape" || event.key === "Esc") {
    handleShowChange(false);
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
const handleDetailUpdate = (params) => {
  curClickRow.value = params;
  handleOperateChange(params);
};
const handleDetailClose = () => {
  curClickRow.value = null;
}
// 修改分组
const handleOperateChange = (data) => {
  const updateDataInList = (list, data) => {
    return list.map((item) => (item.id === data.id ? data : item));
  };
  allGroupList.value = updateDataInList(allGroupList.value, data);
  searchResultFavorites.value = updateDataInList(searchResultFavorites.value, data);
};
// 批量编辑分组
const handleBatchUpdateGroup = async(groupId) => {
  await initData();
  curSelectGroup.value = 'all'
  const selectIds = selectFavoriteList.value.map((item) => item.id);
  if (!groupId) {
    const updateDataInList = (list) => {
      return list.filter((item) => {
        return !selectIds.includes(item.id);
      });
    };
    allGroupList.value = updateDataInList(allGroupList.value);
    searchResultFavorites.value = updateDataInList(searchResultFavorites.value);
  } else {
    const updateDataInList = (list) => {
      return list.map((item) => {
        if (selectIds.includes(item.id)) {
          return {
            ...item,
            group_id: JSON.parse(groupId),
            group_name: localFavoriteList.value.find(
              (item) => item.id === JSON.parse(groupId)
            )?.name,
          };
        } else {
          return item;
        }
      });
    };
    allGroupList.value = updateDataInList(allGroupList.value);
    searchResultFavorites.value = updateDataInList(searchResultFavorites.value);
  }
};
const sourceFilterMethod = (value, row, column) => {
  const property = column.property;
  return row[property] === value;
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
  margin-top: 1px;
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
.new-add-group-popover {
  width: 272px;

  .tippy-tooltip.light-theme {
    padding: 16px;
  }

  .operate-button {
    display: flex;
    align-items: center;
    margin-top: 16px;
    color: #979ba5;

    .bk-button {
      min-width: 52px;

      &:first-child {
        margin-right: 8px;
      }
    }
  }
}
</style>
