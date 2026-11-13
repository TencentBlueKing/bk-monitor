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
  <TDialog
    :visible="modelValue"
    width="100%"
    :top="0"
    attach="body"
    :dialog-class-name="`favorite-management-dialog${store.showAlert ? ' is-show-notice' : ''}`"
    :header="false"
    :close-btn="false"
    :footer="false"
    :show-overlay="false"
    :close-on-esc-keydown="false"
    @opened="() => initData(true)"
    @close="handleShowChange"
  >
    <div class="favorite-group-dialog-header">
      {{ $t('收藏管理') }}
      <i class="bk-icon icon-close close-icon" @click="handleShowChange(false)" />
    </div>
    <div class="favorite-group-dialog-content">
      <div class="favorite-group-filter">
        <div class="group-type-container">
          <div :class="['group-item', { active: curSelectGroup === 'all' }]" @click="handleSelectGroupChange('all')">
            <i class="bklog-icon bklog-all" />
            <span class="group-name">{{ $t('全部收藏') }}</span>
            <span class="favorite-count">{{ allGroupList.length }}</span>
          </div>
          <div
            :class="['group-item', { active: curSelectGroup === 'noGroup' }]"
            @click="handleSelectGroupChange('noGroup')"
          >
            <i class="bklog-icon bklog-file-close" />
            <span class="group-name">{{ $t('未分组') }}</span>
            <span class="favorite-count">{{ noGroupList.length }}</span>
          </div>
          <div
            :class="['group-item', { active: curSelectGroup === 'private' }]"
            @click="handleSelectGroupChange('private')"
          >
            <i class="bklog-icon bklog-file-personal" />
            <span class="group-name">{{ $t('个人收藏') }}</span>
            <span class="favorite-count">{{ privateFavorite.length }}</span>
          </div>
        </div>
        <div class="search-input-container">
          <TPopup
            :visible="addGroupVisible"
            trigger="click"
            overlay-class-name="new-add-group-popover"
            placement="bottom-left"
            attach="body"
            :overlay-inner-style="{ padding: '16px' }"
            @visible-change="handleAddGroupVisibleChange"
          >
            <template #content>
              <div class="favorite-add-group-content">
                <TForm
                  ref="checkInputFormRef"
                  style="width: 100%"
                  label-align="top"
                  :data="addGroupData"
                  :rules="rules"
                >
                  <TFormItem :label="$t('分组名称')" name="name" required>
                    <t-input v-model="addGroupData.name" :placeholder="$t('请输入组名')" />
                  </TFormItem>
                </TForm>
                <div class="operate-button">
                  <t-button size="small" theme="primary" @click="handleAddGroupConfirm">
                    {{ $t('确定') }}
                  </t-button>
                  <t-button theme="default" size="small" @click="() => handleAddGroupPopoverHidden()">
                    {{ $t('取消') }}
                  </t-button>
                </div>
              </div>
            </template>
            <div class="add-group-btn">
              <i v-if="!isAPM" class="bk-icon icon-plus-line" />
              <i v-else class="icon-monitor icon-plus-line" />
            </div>
          </TPopup>

          <TInput
            v-model="groupSearchValue"
            class="search-input"
            :suffix-icon="searchIcon"
            clearable
            @change="handleGroupSearch"
          />
        </div>
        <div class="group-list">
          <div
            v-for="group in searchResultGroupList"
            :key="String(group.id)"
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
            ref="batchOperationMenuRef"
            :favorite-group-list="localFavoriteList"
            :favorite-type="favoriteType"
            :select-favorite-list="selectFavoriteList"
            @operateChange="handleBatchUpdateGroup"
          />
          <TInput
            v-model="favoriteSearchValue"
            class="favorite-search-input"
            :suffix-icon="searchIcon"
            clearable
            @change="handleFavoriteSearch"
          />
        </div>
        <div class="table-content">
          <TTable
            row-key="id"
            :data="displayFavorites"
            :columns="tableColumns"
            :max-height="525"
            :row-class-name="getRowClassName"
            :selected-row-keys="selectFavoriteList.map((row) => row.id)"
            :filter-value="columnFilters"
            :sort="tableSort"
            :filter-row="() => null"
            :locale="{ confirmText: $t('确定'), resetText: $t('重置') }"
            @row-click="({ row }) => (curClickRow = searchResultFavorites.find((item) => item.id === row.id) ?? null)"
            @row-mouseenter="({ index }) => (curHoverRowIndex = index)"
            @row-mouseleave="curHoverRowIndex = -1"
            @select-change="
              (keys) => handleTableSelectionChange(searchResultFavorites.filter((row) => keys.includes(row.id)))
            "
            @filter-change="(value) => (columnFilters = value)"
            @sort-change="(value) => (tableSort = value)"
          >
            <template #name="{ row }">
              <div v-if="!row.editName" class="edit-cell" @click="handleEditName(row)">
                <span class="text name">{{ row.name }}</span
                ><i class="bklog-icon bklog-edit" />
              </div>
              <TInput
                v-else
                ref="editFavoriteNameInputRef"
                :value="nameDrafts[row.id]"
                @change="value => handleNameDraftChange(row.id, value)"
                @blur="(value) => handleEditFavoriteName(String(value), row)"
                @enter="(value) => handleEditFavoriteName(String(value), row)"
              />
            </template>
            <template #group_name="{ row }">
              <div v-if="!row.editGroup" class="edit-cell" @click.stop="handleEditGroup(row)">
                <span class="text">{{ row.group_name }}</span
                ><i class="bklog-icon bklog-edit" />
              </div>
              <TSelect
                v-else
                class="edit-favorite-group"
                :value="String(row.group_id)"
                :popup-visible="editingGroupId === row.id"
                :clearable="false"
                :popup-props="{ overlayClassName: 'favorite-edit-group-popup' }"
                @popup-visible-change="(value) => handleToggle(value, row)"
                @change="(value) => handleEditFavoriteGroup(String(value), row)"
              >
                <TOption
                  v-for="item in localFavoriteList"
                  :key="String(item.id)"
                  :value="String(item.id)"
                  :label="item.name"
                />
              </TSelect>
            </template>
            <template #updated_by="{ row }"><bk-user-display-name :user-id="row.updated_by" /></template>
            <template #operation="{ row }"
              ><span class="del-btn" @click="handleDelete(row)">{{ $t('删除') }}</span></template
            >
          </TTable>
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
  </TDialog>
</template>

<script setup lang="ts">

import { useApplicationStore } from '@/app/state/domains/application-store';
import {
  Dialog as TDialog,
  Popup as TPopup,
  Form as TForm,
  FormItem as TFormItem,
  Input as TInput,
  Select as TSelect,
  Option as TOption,
  Table as TTable,
  DialogPlugin,
} from 'tdesign-vue-next';
import type {
  FormInstanceFunctions,
  FormRules,
  PrimaryTableCol,
  FilterValue,
  TableSort,
  PopupVisibleChangeContext,
} from 'tdesign-vue-next';
import type { FavoriteRecord, FavoriteGroup, FavoriteGroupId, FavoriteResponse } from './favorite.types';
import { ServicesInstance } from '@/platform/services';

import { computed, ref, nextTick, watch, h, onBeforeUnmount } from 'vue';
import { useDialogVisible } from '@/shared/global/overlay/index';


import useLocale from '@/shared/composables/use-locale';
import BatchOperationMenu from './batch-operation-menu.vue';
import FavoriteDetail from './favorite-detail.vue';
import useUtils from '@/shared/composables/use-utils';

defineOptions({ compatConfig: { COMPONENT_V_MODEL: false } });

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(['close']);
const store = useApplicationStore();
const { $t } = useLocale();
const spaceUid = computed(() => store.spaceUid);
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
  const names: Record<string, string> = {};
  const groups: Record<string, FavoriteGroupId> = {};

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
const curSelectGroup = ref<FavoriteGroupId>('all');
const groupSearchValue = ref('');
const favoriteSearchValue = ref('');
const nameDrafts = ref<Record<number, string>>({});
const curClickRow = ref<FavoriteRecord | null>(null);
const curHoverRowIndex = ref(-1);
const selectFavoriteList = ref<FavoriteRecord[]>([]);
const addGroupData = ref({ name: '' });
const localFavoriteList = ref<FavoriteGroup[]>([]);
const allGroupList = ref<FavoriteRecord[]>([]);
const noGroupList = ref<FavoriteRecord[]>([]);
const otherGroupList = ref<FavoriteGroup[]>([]);

const privateFavorite = ref<FavoriteRecord[]>([]);
const searchResultFavorites = ref<FavoriteRecord[]>([]);
const favoriteType = ref('event');

const addGroupVisible = ref(false);
const editingGroupId = ref<number | null>(null);
const columnFilters = ref<FilterValue>({});
const tableSort = ref<TableSort>();
const searchIcon = () => h('i', { class: 'bk-icon icon-search' });
const tableColumns = computed<PrimaryTableCol[]>(() => [
  { colKey: 'row-select', type: 'multiple', width: 45 },
  { colKey: 'name', title: $t('收藏名称'), cell: 'name', ellipsis: true, ellipsisTitle: true },
  {
    colKey: 'group_name',
    ellipsis: true,
    ellipsisTitle: true,
    title: $t('所属组'),
    cell: 'group_name',
    filter: {
      type: 'multiple',
      showConfirmAndReset: true,
      resetValue: [],
      list: tableFilters.value.groups.map((item) => ({ label: item.text, value: item.value })),
    },
  },
  {
    colKey: 'updated_by',
    ellipsis: true,
    ellipsisTitle: true,
    title: $t('变更人'),
    cell: 'updated_by',
    filter: {
      type: 'multiple',
      showConfirmAndReset: true,
      resetValue: [],
      list: tableFilters.value.names.map((item) => ({ label: item.text, value: item.value })),
    },
  },
  { colKey: 'updated_at', title: $t('变更时间'), sorter: true, ellipsis: true, ellipsisTitle: true },
  { colKey: 'operation', title: $t('操作'), cell: 'operation', width: 80 },
]);
const displayFavorites = computed(() => {
  const rows = searchResultFavorites.value.filter((row) =>
    Object.entries(columnFilters.value).every(
      ([key, values]) =>
        !Array.isArray(values) ||
        !values.length ||
        values.some((value) => sourceFilterMethod(value, row, { property: key })),
    ),
  );
  const sort = tableSort.value;
  if (!sort || Array.isArray(sort) || sort.sortBy !== 'updated_at') return rows;
  return [...rows].sort((a, b) => a.updated_at.localeCompare(b.updated_at) * (sort.descending ? -1 : 1));
});
const batchOperationMenuRef = ref<InstanceType<typeof BatchOperationMenu> | null>(null);
const checkInputFormRef = ref<FormInstanceFunctions | null>(null);

const editFavoriteNameInputRef = ref<{ focus: () => void } | { focus: () => void }[] | null>(null);

const { setVisible: setFavoriteManageVisible, onValueChange: onFavoriteManageValueChange } = useDialogVisible(false, {
  id: 'retrieve-favorite-manage-dialog',
  type: 'dialog',
  group: 'retrieve-dialog',
});

const isAPM = window.__IS_MONITOR_APM__;
const rules: FormRules = {
  name: [
    {
      validator: () => /^[\u4e00-\u9fa5\w\s\-+]+$/.test(addGroupData.value.name),
      message: $t('组名不规范'),
      trigger: 'blur',
    },
    {
      validator: () => !localFavoriteList.value.some((item) => item.name === addGroupData.value.name),
      message: $t('名称冲突'),
      trigger: 'blur',
    },
    { required: true, message: $t('必填项'), trigger: 'blur' },
    { max: 30, message: $t('最大30字符'), trigger: 'blur' },
  ],
};

watch(
  allGroupList,
  (newValue) => {
    const groupMap = new Map(
      otherGroupList.value.map((group) => {
        return [group.id, { ...group, favorites: [] as FavoriteRecord[] }];
      }),
    );
    const initialOtherGroups = Array.from(groupMap.values());
    const [noGroupItems, privateItems, otherGroupItems] = newValue.reduce(
      (acc, item) => {
        if (item.group_name === '未分组') {
          acc[0].push(item);
        } else if (item.group_name === '个人收藏') {
          acc[1].push(item);
        } else {
          const group = groupMap.get(item.group_id);
          if (group) {
            group.favorites.push(item);
          }
        }
        return acc;
      },
      [[], [], initialOtherGroups] as [FavoriteRecord[], FavoriteRecord[], FavoriteGroup[]],
    );

    noGroupList.value = noGroupItems;
    privateFavorite.value = privateItems;
    otherGroupList.value = otherGroupItems;
  },
  { deep: true },
);
const initData = async (val = true) => {
  onFavoriteManageValueChange(val);
  if (val) {
    curSelectGroup.value = 'all';
    favoriteSearchValue.value = '';
    nameDrafts.value = {};
    selectFavoriteList.value = [];
    curClickRow.value = null;
    await getGroupList();
    await getFavoriteList();
  }
};

const handleShowChange = (_value?: unknown) => {
  emit('close', false);
};
/** 获取组列表 */
const getGroupList = async () => {
  try {
    const query = {
      space_uid: spaceUid.value,
      source_type: store.isSceneMode ? 'scene' : 'index_set',
    };
    if (window.__IS_MONITOR_APM__) {
      Object.assign(query, {
        scope: JSON.stringify({
          app_name: window.MONITOR_APM_APP_NAME,
          service_name: window.MONITOR_APM_SERVICE_NAME,
        }),
      });
    }
    const res = await ServicesInstance.favorite.getGroupList<FavoriteResponse<FavoriteGroup[]>>({ query });
    otherGroupList.value = res.data
      .filter((item) => item.name !== '未分组' && item.name !== '个人收藏')
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

const { formatResponseListTimeZoneString } = useUtils();

/** 获取收藏请求 */
const getFavoriteList = async (showAll = true) => {
  try {
    // this.tableLoading = true;
    const query = {
      space_uid: spaceUid.value,
      order_type: 'NAME_ASC',
      source_type: store.isSceneMode ? 'scene' : 'index_set',
    };
    if (window.__IS_MONITOR_APM__) {
      Object.assign(query, {
        scope: JSON.stringify({
          app_name: window.MONITOR_APM_APP_NAME,
          service_name: window.MONITOR_APM_SERVICE_NAME,
        }),
      });
    }
    const res = await ServicesInstance.favorite.getFavoriteList<FavoriteResponse<FavoriteRecord[]>>({ query });
    const data = formatResponseListTimeZoneString(res.data, () => {
      return {
        editName: false,
        editGroup: false,
      };
    });

    allGroupList.value = data;
    if (showAll) {
      searchResultFavorites.value = allGroupList.value;
    }
  } catch {
    // this.emptyType = "500";
  } finally {
    // this.tableLoading = false;
    // this.handleSearchFilter();
  }
};

/** 切换分组，获取收藏列表 */
const handleSelectGroupChange = (id: FavoriteGroupId) => {
  curSelectGroup.value = id;
  selectFavoriteList.value = [];
  updateSearchResultFavorites();
};
/** 根据当前分组和搜索词生成表格数据 */
const updateSearchResultFavorites = () => {
  let curSelectGroupFavorites: FavoriteRecord[] = [];

  switch (curSelectGroup.value) {
    case 'all':
      curSelectGroupFavorites = allGroupList.value;
      break;
    case 'noGroup':
      curSelectGroupFavorites = allGroupList.value.filter((favorite) => favorite.group_name === '未分组');
      break;
    case 'private':
      curSelectGroupFavorites = allGroupList.value.filter((favorite) => favorite.group_name === '个人收藏');
      break;
    default:
      curSelectGroupFavorites = allGroupList.value.filter((favorite) => favorite.group_id === curSelectGroup.value);
  }

  searchResultFavorites.value = curSelectGroupFavorites
    .filter((favorite) => favorite.name.includes(favoriteSearchValue.value))
    .map((favorite) => ({
      ...favorite,
      editName: false,
      editGroup: false,
      groupName: localFavoriteList.value.find((item) => item.id === favorite.group_id)?.name,
    }));
};
/** 组搜索 */
const handleGroupSearch = () => {};
/** 收藏列表搜索 */
const handleFavoriteSearch = () => {
  updateSearchResultFavorites();
};
/** 删除单个收藏 */
const handleDelete = (row: FavoriteRecord) => {
  const dialog = DialogPlugin.confirm({
    body: $t('当前收藏名为 {n}，确认是否删除？', { n: row.name }),
    theme: 'warning',
    onCancel: () => dialog.destroy(),
    onClose: () => dialog.destroy(),
    onConfirm: async () => {
      const res = await ServicesInstance.favorite.deleteFavorite({
        params: { favorite_id: row.id },
      });
      if (res.result) {
        allGroupList.value = allGroupList.value.filter((item) => item.id !== row.id);
        selectFavoriteList.value = selectFavoriteList.value.filter((item) => item.id !== row.id);
        if (curClickRow.value?.id === row.id) {
          curClickRow.value = null;
        }
        updateSearchResultFavorites();
        dialog.destroy();
      }
    },
  });
};
/** 添加行类名 */
const getRowClassName = ({ row, rowIndex }: { row: FavoriteRecord; rowIndex: number }) => {
  const styles = [];
  if (row.id === curClickRow.value?.id) styles.push('row-click');
  if (rowIndex === curHoverRowIndex.value) styles.push('row-hover');
  return styles.join(' ');
};

const handleTableSelectionChange = (selection: FavoriteRecord[]) => {
  selectFavoriteList.value = selection;
};
/** 添加分组 */
const handleAddGroupConfirm = async () => {
  try {
    if ((await checkInputFormRef.value?.validate()) !== true) return;
    const data = {
      name: addGroupData.value.name,
      space_uid: spaceUid.value,
      source_type: store.isSceneMode ? 'scene' : 'index_set',
    };
    if (window.__IS_MONITOR_APM__) {
      Object.assign(data, {
        scope: {
          app_name: window.MONITOR_APM_APP_NAME,
          service_name: window.MONITOR_APM_SERVICE_NAME,
        },
      });
    }
    await ServicesInstance.favorite.createGroup({
      data,
    });

    handleAddGroupPopoverHidden();
    initData();
  } catch (error) {
    console.error(error);
  }
};
/** 隐藏添加分组popover */
const handleAddGroupPopoverHidden = (close = true) => {
  addGroupData.value.name = '';
  checkInputFormRef.value?.clearValidate();
  if (close) {
    addGroupVisible.value = false;
  }
};
const handleEditGroup = (row: FavoriteRecord) => {
  row.editGroup = true;
  for (const favorite of searchResultFavorites.value) {
    if (favorite.id !== row.id) {
      favorite.editGroup = false;
    }
  }
  editingGroupId.value = row.id;
};
const handleEditName = (row: FavoriteRecord) => {
  nameDrafts.value[row.id] = row.name;
  row.editName = true;
  row.editGroup = false;
  nextTick(() => {
    const input = editFavoriteNameInputRef.value;
    (Array.isArray(input) ? input[0] : input)?.focus();
  });
};
const handleToggle = (val: boolean, row: FavoriteRecord) => {
  if (!val) {
    editingGroupId.value = null;
    row.editGroup = false;
  }
};
const handleNameDraftChange = (id: number, value: string | number) => {
  nameDrafts.value[id] = String(value ?? '');
};
const handleEditFavoriteName = (val: string, row: FavoriteRecord) => {
  if (val !== row.name) {
    const updatedRow = {
      ...row,
      name: val,
    };
    handleUpdateFavorite(updatedRow).then(() => {
      row.editName = false;
      row.name = val;
      curClickRow.value = row;
      handleOperateChange(row);
    });
  } else {
    row.editName = false;
  }
};
const handleEditFavoriteGroup = (val: string, row: FavoriteRecord) => {
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
      row.group_name = localFavoriteList.value.find((item) => item.id === JSON.parse(val))?.name;
      curClickRow.value = row;
      handleOperateChange(row);
    });
  }
};
const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape' || event.key === 'Esc') {
    handleShowChange(false);
  }
};
const handleUpdateFavorite = async (row: FavoriteRecord) => {
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
  if (window.__IS_MONITOR_APM__) {
    Object.assign(params, {
      scope: {
        app_name: window.MONITOR_APM_APP_NAME,
        service_name: window.MONITOR_APM_SERVICE_NAME,
      },
    });
  }

  return ServicesInstance.favorite
    .batchFavoriteUpdate({
      data: {
        params,
      },
    })
    .then(() => {
      return Promise.resolve(true);
    })
    .catch((error) => {
      console.error('Batch update failed', error);
      return Promise.reject(error);
    });
};
const handleDetailUpdate = (params: FavoriteRecord) => {
  curClickRow.value = params;
  handleOperateChange(params);
};
const handleDetailClose = () => {
  curClickRow.value = null;
};
// 修改分组
const handleOperateChange = (data: FavoriteRecord) => {
  const updateDataInList = (list: FavoriteRecord[], data: FavoriteRecord) => {
    return list.map((item) => (item.id === data.id ? data : item));
  };
  allGroupList.value = updateDataInList(allGroupList.value, data);
  searchResultFavorites.value = updateDataInList(searchResultFavorites.value, data);
};
// 批量编辑分组
const handleBatchUpdateGroup = async (groupId?: FavoriteGroupId) => {
  const selectIds = selectFavoriteList.value.map((item) => item.id);
  selectFavoriteList.value = [];
  curClickRow.value = null;
  await getGroupList();
  await getFavoriteList(false);
  if (!groupId) {
    const updateDataInList = (list: FavoriteRecord[]) => {
      return list.filter((item) => {
        return !selectIds.includes(item.id);
      });
    };
    allGroupList.value = updateDataInList(allGroupList.value);
  } else {
    const updateDataInList = (list: FavoriteRecord[]) => {
      return list.map((item) => {
        if (selectIds.includes(item.id)) {
          return {
            ...item,
            group_id: JSON.parse(String(groupId)),
            group_name: localFavoriteList.value.find((item) => item.id === JSON.parse(String(groupId)))?.name,
          };
        }
        return item;
      });
    };
    allGroupList.value = updateDataInList(allGroupList.value);
  }
  updateSearchResultFavorites();
};
const sourceFilterMethod = (value: unknown, row: FavoriteRecord, column: { property: string }) => {
  return row[column.property as keyof FavoriteRecord] === value;
};
function handleAddGroupVisibleChange(visible: boolean, _context: PopupVisibleChangeContext) {
  addGroupVisible.value = visible;
  if (!visible) handleAddGroupPopoverHidden(false);
}
watch(
  () => props.modelValue,
  (visible, wasVisible) => {
    setFavoriteManageVisible(visible);
    if (visible) {
      window.addEventListener('keydown', handleKeydown);
    } else {
      if (wasVisible) {
        handleAddGroupPopoverHidden();
        batchOperationMenuRef.value?.closePopovers();
        columnFilters.value = {};
        tableSort.value = undefined;
        editingGroupId.value = null;
      }
      nextTick(() => {
        window.removeEventListener('keydown', handleKeydown);
      });
    }
  },
  { immediate: true },
);

onBeforeUnmount(() => window.removeEventListener('keydown', handleKeydown));
</script>

<style lang="scss" scoped>
:global(.t-dialog__ctx:has(.favorite-management-dialog)) {
  top: 52px;
  height: calc(100% - 52px);
}
:global(.t-dialog__ctx:has(.favorite-management-dialog.is-show-notice)) {
  top: 92px;
  height: calc(100% - 92px);
}
:global(.t-dialog__ctx:has(.favorite-management-dialog) .t-dialog__mask),
:global(.t-dialog__ctx:has(.favorite-management-dialog) .t-dialog__wrap) {
  position: absolute;
  inset: 0;
  height: 100%;
}
:global(.t-dialog__ctx:has(.favorite-management-dialog) .t-dialog__wrap) {
  overflow: hidden;
}
:global(.t-dialog__ctx:has(.favorite-management-dialog) .t-dialog__position) {
  height: 100%;
  padding: 0;
}
:global(.t-dialog.favorite-management-dialog) {
  height: 100%;
  padding: 0;
  border: none;
  border-radius: 0;
  overflow: hidden;
}
:global(.favorite-management-dialog .t-dialog__body) {
  height: 100%;
  padding: 0;
  overflow: hidden;
  background: #f5f6fa;
}
:global(.favorite-management-dialog .t-table__content) {
  border: 1px solid var(--bklog-border-muted, #dcdee5);
}
:global(.favorite-management-dialog .t-table th) {
  background: var(--bklog-surface-disabled, #fafbfd);
  color: var(--bklog-text-primary, #313238);
  font-weight: normal;
}
:global(.favorite-management-dialog .t-table th),
:global(.favorite-management-dialog .t-table td) {
  height: 43px;
  padding: 10px 12px;
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
  margin-top: 1px;
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

      :deep(.t-table__row) {
        &.row-hover {
          cursor: pointer;
          background: var(--bklog-surface-hover, #f5f7fa);

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
          background-color: var(--bklog-surface, #fff);
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

.favorite-add-group-content {
  width: 240px;

  .tippy-tooltip.light-theme {
    padding: 16px;
  }

  .operate-button {
    display: flex;
    align-items: center;
    margin-top: 16px;
    color: #979ba5;

    .t-button {
      min-width: 52px;

      &:first-child {
        margin-right: 8px;
      }
    }
  }
}
</style>
