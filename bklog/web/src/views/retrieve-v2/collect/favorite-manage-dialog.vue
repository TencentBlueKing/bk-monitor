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
  <!-- 检索-设置 -->
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
    @value-change = initData
  >
    <div class="favorite-group-dialog-header">
      {{ $t("收藏管理") }}
      <i class="bk-icon icon-close close-icon" @click="handleShowChange(false)" />
    </div>
   
  </bk-dialog>
</template>

<script setup>
import { defineProps, defineEmits, computed, ref } from "vue";
import $http from "@/api";
import useStore from "@/hooks/use-store";
import useLocale from '@/hooks/use-locale';
const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
});
groupNameMap = ref({
  unknown: $t('未分组'),
  private: $t('个人收藏'),
})
const emit = defineEmits(["close", "submit"]);
const store = useStore();
const { $t } = useLocale();
const spaceUid = computed(() => store.state.spaceUid);
const initData = async() =>{
  console.log(3444);
  
  await getGroupList();
  getFavoriteList();
}



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

    //   this.groupList = res.data.map((item) => ({
    //     group_id: item.id,
    //     group_name: this.groupNameMap[item.group_type] ?? item.name,
    //     group_type: item.group_type,
    //   }));
    //   this.unPrivateList = this.groupList.slice(1); // 去除个人收藏的列表
    //   this.privateList = this.groupList.slice(0, 1); // 个人收藏列表
    //   this.sourceFilters = res.data.map((item) => ({
    //     text: this.groupNameMap[item.group_type] ?? item.name,
    //     value: item.name,
    //   }));
    //   this.unknownGroupID = this.groupList[this.groupList.length - 1]?.group_id;
    //   this.privateGroupID = this.groupList[0]?.group_id;
  } catch (error) {
    // console.warn(error);
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
    console.log(res);
    
    // const updateSourceFiltersSet = new Set();
    // const localLanguage = jsCookie.get("blueking_language") || "zh-cn";
    // const initList = res.data.map((item) => {
    //   const visible_option =
    //     item.created_by === this.getUserName
    //       ? this.allOptionList
    //       : this.unPrivateOptionList;
    //   const search_fields_select_list = item.search_fields.map((item) => ({
    //     name:
    //       localLanguage === "en"
    //         ? item.replace(/^全文检索(\(\d\))?$/, (item, p1) => {
    //             return `${this.$t("全文检索")}${!!p1 ? p1 : ""}`;
    //           })
    //         : item,
    //     chName: item,
    //   })); // 初始化表单字段

    //   const is_group_disabled = item.visible_type === "private";
    //   if (!updateSourceFiltersSet.has(item.updated_by))
    //     updateSourceFiltersSet.add(item.updated_by);
    //   return {
    //     ...item,
    //     search_fields_select_list,
    //     group_option: this.unPrivateList,
    //     group_option_private: this.privateList,
    //     visible_option,
    //     is_group_disabled,
    //   };
    // });
    // this.updateSourceFilters = [...updateSourceFiltersSet].map((item) => ({
    //   text: item,
    //   value: item,
    // }));
    // this.tableList = res.data;
    // this.operateTableList = initList;
    // this.searchAfterList = initList;
  } catch (error) {
    // this.emptyType = "500";
  } finally {
    // this.tableLoading = false;
    // this.handleSearchFilter();
  }
};
</script>
<style lang="scss" scoped>
:deep(.bk-dialog-body) {
  padding: 0;
  overflow: hidden;
  background-color: #f5f6fa;
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

      .icon-monitor {
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

        .icon-monitor,
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

          .icon-bianji {
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

        .icon-bianji {
          display: none;
          font-size: 24px;
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
