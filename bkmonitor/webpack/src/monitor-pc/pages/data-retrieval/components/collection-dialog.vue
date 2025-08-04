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
    :value="isShow"
    header-position="left"
    width="480"
    :title="$t('收藏')"
    @after-leave="handleCloseDialog"
  >
    <div
      v-bkloading="{ isLoading: loading }"
      class="collection-dialog"
    >
      <div>
        <bk-input
          v-model="search"
          clearable
          :placeholder="$t('搜索')"
          :right-icon="'bk-icon icon-search'"
          @change="handleSearchChange"
        />
      </div>
      <!-- 仪表盘分组 -->
      <div
        v-for="group in searchDashBoardList"
        :key="group.id"
        class="dashboard-group"
      >
        <!-- 分组名称 -->
        <div
          class="dashboard-group-title"
          @click="handleClickGroup(group.id)"
        >
          <i
            class="icon-monitor file-icon"
            :class="groupData.checkId === group.id ? 'icon-mc-file-open' : 'icon-mc-file-close'"
          />
          {{ group.title }}
        </div>
        <!-- 仪表盘名称 -->
        <transition
          @before-enter="beforeEnter"
          @enter="enter"
          @after-enter="afterEnter"
          @before-leave="beforeLeave"
          @leave="leave"
          @after-leave="afterLeave"
        >
          <div v-if="groupData.checkId === group.id">
            <!-- 新增仪表盘 -->
            <div
              v-if="dashboard.isShow"
              class="add-row-input dashboard-input"
            >
              <bk-input
                :ref="`dashboardInput${group.id}`"
                v-model="dashboard.name"
                :placeholder="$tc('输入仪表盘名称')"
              />
              <div
                class="input-icon"
                @click="handleAddDashboard(group.id)"
              >
                <i class="bk-icon icon-check-1" />
              </div>
              <div
                class="input-icon"
                @click="handleCloseDashboard"
              >
                <i class="icon-monitor icon-mc-close" />
              </div>
            </div>
            <div
              v-else
              class="dashboard-group-child add-new"
              @click="handleShowDashboardAdd(group.id)"
            >
              <i class="icon-monitor icon-mc-add" />
              {{ $t('新建仪表盘') }}
            </div>
            <!-- 仪表盘名字 -->
            <div
              v-for="item in group.dashboards"
              :key="item.id"
              class="dashboard-group-child"
              :class="{ 'dashboard-active': checkedDashboard.id === item.id }"
              @click="handleAddCollection(item)"
            >
              <span class="group-child-name">{{ item.title }}</span>
              <i
                v-if="checkedDashboard.id === item.id"
                class="bk-icon icon-check-1"
              />
            </div>
          </div>
        </transition>
      </div>
      <!-- 新增仪表盘分组 -->
      <div
        v-if="groupData.isShow"
        class="add-row-input group-input"
      >
        <bk-input
          ref="groupInput"
          v-model="groupData.name"
          :placeholder="$tc('输入目录名称')"
          :left-icon="'icon-monitor icon-mc-file-close'"
        />
        <div
          class="input-icon"
          @click="handleAddDashboardGroup"
        >
          <i class="bk-icon icon-check-1" />
        </div>
        <div
          class="input-icon"
          @click="handleCloseDashboardGroup"
        >
          <i class="icon-monitor icon-mc-close" />
        </div>
      </div>
      <div
        v-else
        class="dashboard-group-title add-new"
        @click="handleShowGroupAdd"
      >
        <i class="icon-monitor icon-mc-add" />
        {{ $t('新建目录') }}
      </div>
    </div>
    <template #footer>
      <bk-button
        :loading="loading"
        theme="primary"
        :disabled="!Object.keys(checkedDashboard).length"
        @click="handleCollectionToDashboard(true)"
        >{{ $t('收藏并跳转') }}</bk-button
      >
      <bk-button
        :loading="loading"
        theme="primary"
        :disabled="!Object.keys(checkedDashboard).length"
        @click="handleCollectionToDashboard(false)"
        >{{ $t('直接收藏') }}</bk-button
      >
      <bk-button @click="handleCloseDialog">
        {{ $t('取消') }}
      </bk-button>
    </template>
  </bk-dialog>
</template>
<script lang="ts">
import { Component, Mixins, Prop, Ref, Watch } from 'vue-property-decorator';

import { createDashboardOrFolder, getDirectoryTree, saveToDashboard } from 'monitor-api/modules/grafana';
import { filterDictConvertedToWhere } from 'monitor-ui/chart-plugins/utils';

import { Debounce } from '../../../components/ip-selector/common/util';
import { DASHBOARD_ID_KEY } from '../../../constant/constant';
import collapseMixin from '../../../mixins/collapseMixin';

import type MonitorVue from '../../../types/index';
import type { ICheckedDashboard } from '../index';

@Component({
  name: 'collection-dialog',
})
export default class CollectionDialog extends Mixins(collapseMixin)<MonitorVue> {
  @Ref() readonly groupInput!: HTMLFormElement;
  // 勾选的图表数据
  @Prop({ default: () => [] })
  collectionList: any[];

  @Prop({ default: false })
  isShow: boolean;

  loading = false;
  groupData = {
    checkId: -1,
    name: '',
    isShow: false,
  };
  dashboard = {
    name: '',
    isShow: false,
  };
  checkedDashboard: ICheckedDashboard = {}; // 选定的仪表盘数据
  dashBoardList = []; // 仪表盘列表

  /* 搜索 */
  search = '';
  searchDashBoardList = [];

  @Watch('isShow')
  async onIsShowChanged() {
    this.checkedDashboard = {};
    await this.getDashboardTree();
    this.groupData.checkId = this.dashBoardList[0].id;
  }

  //  获取仪表盘列表
  async getDashboardTree() {
    this.loading = true;
    const list = await getDirectoryTree().catch(() => []);
    this.dashBoardList = list;
    if (this.search) {
      this.handleSearchChange(this.search);
    } else {
      this.searchDashBoardList = list;
    }
    this.loading = false;
  }

  //  选择仪表盘分组
  handleClickGroup(id: number) {
    this.groupData.checkId = this.groupData.checkId === id ? -1 : id;
  }

  //  选中要收藏的仪表盘
  handleAddCollection(dashboard) {
    if (this.checkedDashboard.id && this.checkedDashboard.id === dashboard.id) {
      this.checkedDashboard = {};
      return;
    }
    this.checkedDashboard = dashboard;
  }

  //  显示新增仪表盘分组input行
  handleShowGroupAdd() {
    this.groupData.isShow = true;
    this.$nextTick(() => {
      this.groupInput.focus();
    });
  }

  //  关闭新增仪表盘分组input行
  handleCloseDashboardGroup() {
    this.groupData.name = '';
    this.groupData.isShow = false;
  }

  //  新增仪表盘分组
  async handleAddDashboardGroup() {
    const { name } = this.groupData;
    if (!name) return;
    const params = {
      title: name,
      type: 'folder',
    };
    await createDashboardOrFolder(params).catch(() => {});
    await this.getDashboardTree();
    this.handleCloseDashboardGroup();
  }

  //  新增仪表盘
  async handleAddDashboard(id: number) {
    const { name } = this.dashboard;
    if (!name) return;
    const params = {
      title: name,
      type: 'dashboard',
      folderId: id,
    };
    const { uid } = await createDashboardOrFolder(params).catch(() => {});
    await this.getDashboardTree();

    const groupItem = this.searchDashBoardList.find(item => item.id === id);
    if (groupItem) {
      const result = [];
      // 通过新增的仪表盘的uid，在列表接口数据中找到新增的仪表盘，并把它过滤出来放在首位
      groupItem.dashboards.forEach(item => {
        if (item.uid === uid) {
          result.unshift(item);
          this.checkedDashboard = item;
        } else {
          result.push(item);
        }
      });
      groupItem.dashboards = result;
    }
    this.handleCloseDashboard();
  }

  //  显示新增仪表盘input行
  handleShowDashboardAdd(id: number) {
    this.dashboard.isShow = true;
    this.$nextTick(() => {
      const dashboardRef: HTMLFormElement = this.$refs[`dashboardInput${id}`][0];
      dashboardRef.focus();
    });
  }

  //  收藏到仪表盘
  handleCollectionToDashboard(needJump = false) {
    this.loading = true;
    const panels = this.collectionList.map(
      item =>
        item?.rawQueryPanel?.toDashboardPanels() || {
          name: item.title,
          fill: item.fill,
          min_y_zero: item.min_y_zero,
          queries: item.targets.map(set => {
            const { data } = set;
            data.query_configs = data.query_configs.map(queryConfig => filterDictConvertedToWhere(queryConfig));
            return {
              ...data,
              alias: set.alias || '',
              expression: set.expression || 'A',
            };
          }),
        }
    );
    saveToDashboard({
      panels,
      dashboard_uids: [this.checkedDashboard.uid],
    })
      .then(() => {
        this.$bkMessage({ theme: 'success', message: this.$t('收藏成功') });
        this.$emit('on-collection-success');
        this.$emit('update:isShow', false);
        this.$emit('show', false);
        // 跳转grafana
        if (needJump) {
          this.updateDashboardId(this.checkedDashboard.uid);
          const url = `${location.origin}${location.pathname}?bizId=${this.$store.getters.bizId}#/grafana/d/${this.checkedDashboard.uid}`;
          window.open(url, '_blank');
        }
      })
      .finally(() => {
        this.loading = false;
      });
  }
  // 更新仪表盘默认显示
  updateDashboardId(uid: string) {
    let idObj = null;
    const { bizId } = this.$store.getters;
    const dashboardCache = localStorage.getItem(DASHBOARD_ID_KEY);
    if (dashboardCache && dashboardCache.indexOf('{') > -1) {
      const data = JSON.parse(dashboardCache);
      data[bizId] = uid;
      idObj = JSON.stringify(data);
    } else {
      idObj = JSON.stringify({ [bizId]: uid });
    }
    localStorage.setItem(DASHBOARD_ID_KEY, idObj);
  }

  //  关闭新增仪表盘input行
  handleCloseDashboard() {
    this.dashboard.name = '';
    this.dashboard.isShow = false;
  }

  //  关闭收藏dialog
  handleCloseDialog() {
    this.handleCloseDashboardGroup();
    this.handleCloseDashboard();
    this.$emit('update:isShow', false);
    this.$emit('show', false);
  }
  @Debounce(300)
  handleSearchChange(value: string) {
    if (value) {
      this.searchDashBoardList = this.dashBoardList
        .filter(item => !!item.dashboards.filter(child => child.title.indexOf(value) > -1).length)
        .map(item => ({
          ...item,
          dashboards: item.dashboards.filter(child => child.title.indexOf(value) > -1),
        }));
    } else {
      this.searchDashBoardList = this.dashBoardList;
    }
  }
}
</script>
<style lang="scss" scoped>
.collection-dialog {
  // border-top: 1px solid #f0f1f5;
  height: 500px;
  padding-bottom: 28px;
  overflow-y: auto;

  :deep(.bk-dialog-wrapper .bk-dialog-header) {
    padding: 3px 24px 14px;
  }

  :deep(.bk-dialog-wrapper) {
    .bk-dialog-body {
      max-height: calc(100vh - 400px);
      overflow-y: auto;
    }
  }

  .dashboard-group {
    display: flex;
    flex-direction: column;
    min-height: 42px;
    color: #313238;
    border-bottom: 1px solid #f0f1f5;

    &-title {
      display: flex;
      align-items: center;
      height: 42px;
      cursor: pointer;

      .file-icon {
        margin: 0 12px 0 2px;
        font-size: 18px;
        color: #a3c5fd;
      }
    }

    &-child {
      display: flex;
      align-items: center;
      height: 32px;
      padding: 0 10px;
      margin: 0 0 2px 32px;
      color: #63656e;
      background: #f5f6fa;
      border-radius: 2px;

      .group-child-name {
        flex: 1;
      }

      .icon-check-1 {
        font-size: 24px;
        color: #3a84ff;
      }

      &:nth-last-child(1) {
        margin-bottom: 11px;
      }

      &:hover {
        cursor: pointer;
        background: #e1ecff;
      }
    }

    .dashboard-active {
      background: #e1ecff;
    }
  }

  .add-new {
    display: flex;
    align-items: center;
    padding-left: 4px;
    color: #3a84ff;
    border-bottom: 1px solid #f0f1f5;

    .icon-mc-add {
      font-size: 24px;
    }
  }

  .add-row-input {
    display: flex;
    align-items: center;

    .input-icon {
      display: flex;
      align-items: center;
      justify-content: center;
      min-width: 32px;
      height: 32px;
      margin-left: 2px;
      font-size: 24px;
      background: #fff;
      border: 1px solid #c4c6cc;
      border-radius: 2px;

      &:hover {
        color: #3a84ff;
        cursor: pointer;
        background: rgba(58, 132, 255, 0.06);
        border-color: #3a84ff;
      }
    }
  }

  .group-input {
    height: 42px;
    border-bottom: 1px solid #f0f1f5;

    :deep(.bk-form-control) .control-icon {
      color: #979ba5;
    }
  }

  .dashboard-input {
    margin-bottom: 2px;
    margin-left: 32px;
    background: #f5f6fa;
  }
}
</style>
