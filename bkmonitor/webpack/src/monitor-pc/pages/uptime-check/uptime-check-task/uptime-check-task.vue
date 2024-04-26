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
  <div
    v-monitor-loading="{ isLoading: allLoading }"
    class="uptime-task"
  >
    <uptime-check-empty
      v-if="(!allData.length && !group.data.length) || !hasNode"
      :is-node="!hasNode"
      @create="handleCreateTask"
      @import="options.isShow = true"
      @create-node="handleCreateNode"
    />
    <template v-else>
      <div class="uptime-task-header">
        <bk-button
          v-authority="{ active: !authority.MANAGE_AUTH }"
          theme="primary"
          class="search-item mc-btn-add"
          @click="authority.MANAGE_AUTH ? handleCreateTask() : handleShowAuthorityDetail()"
        >
          {{ $t('新建') }}
        </bk-button>
        <bk-button
          v-authority="{ active: !authority.MANAGE_AUTH }"
          class="search-item mc-btn-add"
          @click="authority.MANAGE_AUTH ? handleCreateTaskGroup() : handleShowAuthorityDetail()"
        >
          {{ $t('新建任务组') }}
        </bk-button>
        <bk-button
          v-authority="{ active: !authority.MANAGE_AUTH }"
          class="search-item"
          @click="authority.MANAGE_AUTH ? importFile() : handleShowAuthorityDetail()"
        >
          {{ $t('导入拨测任务') }}
        </bk-button>
        <bk-input
          class="search-input"
          :placeholder="$t('任务名称')"
          right-icon="bk-icon icon-search"
          :value="header.keyword"
          clearable
          @change="handleSearch"
        />
        <div class="search-switch">
          <span
            class="icon-monitor icon-card search-switch-icon"
            :class="{ 'icon-active': header.switch === 0 }"
            @click="handleSwitchChange(0)"
          />
          <span
            class="icon-monitor icon-biaoge search-switch-icon"
            :class="{ 'icon-active': header.switch === 1 }"
            @click="handleSwitchChange(1)"
          />
        </div>
      </div>
      <div class="uptime-task-container">
        <keep-alive>
          <uptime-check-cards
            v-if="!header.switch"
            ref="checkCards"
            :group="group"
            @update-all="handleAllDataFetch"
            @detail-show="handleDetailShow"
            @group-update="getTaskData"
            @set-loading="handleSetAllLoading"
            @change-group-id="handleGroupIdChange"
            @edit="handleEditTask"
            @change-task-detail="handleTaskDetail"
          />
          <uptime-check-list
            v-else
            :change-status="handleChangeGroupStatus"
            @update-all="handleAllDataFetch"
            @edit="handleEditTask"
            @detail-show="handleDetailShow"
          />
        </keep-alive>
      </div>
    </template>
    <uptime-check-import
      :options="options"
      @complete="handleComplete"
    />
  </div>
</template>
<script>
import { debounce } from 'throttle-debounce';
import { createNamespacedHelpers } from 'vuex';

import UptimeCheckCards from './uptime-check-card/uptime-check-cards.vue';
import UptimeCheckEmpty from './uptime-check-empty/uptime-check-empty';
import UptimeCheckImport from './uptime-check-import/uptime-check-import';
import UptimeCheckList from './uptime-check-list/uptime-check-list.vue';

const { mapGetters, mapActions } = createNamespacedHelpers('uptime-check-task');
export default {
  name: 'UptimeCheckTask',
  components: {
    UptimeCheckEmpty,
    UptimeCheckCards,
    UptimeCheckList,
    UptimeCheckImport,
  },
  inject: ['authority', 'handleShowAuthorityDetail'],
  props: {
    fromRouteName: {
      type: String,
      required: true,
    },
    nodeName: {
      type: String,
      default: '',
    },
  },
  data() {
    return {
      hasNode: false,
      header: {
        switch: 0,
        keyword: '',
      },
      group: {
        data: [],
        expand: false,
        loading: false,
      },
      table: {
        data: [],
        row: null,
      },
      detail: {
        groupId: -1,
        groupLimit: false,
      },
      options: {
        isShow: false,
      },
      allLoading: false,
      handleSearch: null,
      taskDetail: null,
    };
  },
  computed: {
    ...mapGetters(['allData', 'keyword', 'searchData']),
  },
  activated() {
    this.handleRouteEnter();
    this.handleSearch = debounce(300, this.handleDebounceSearch);
  },
  deactivated() {
    this.detail = {
      groupId: -1,
      groupLimit: false,
    };
  },
  methods: {
    ...mapActions(['getUptimeCheckTask', 'setKeyword']),
    handleRouteEnter(name) {
      const { params } = this.$route;
      if (!['uptime-check-task-detail', 'uptime-check-task-add', 'uptime-check-task-edit'].includes(name)) {
        this.header.keyword = '';
        // this.header.switch = 0  从编辑详情新建页面跳转过来无需重置布局类型
        this.hasNode = false;
      }
      this.header.keyword = this.nodeName ? `${this.$t('节点:')}${this.nodeName}` : this.keyword || '';
      if ((name === 'strategy-config-add' || name === 'strategy-config-edit') && params.taskId) {
        this.handleEditMetric(params.taskId);
      }
      !this.allLoading && this.getTaskData();
    },
    async getTaskData(needLoading = true) {
      this.allLoading = needLoading;
      const data = await this.getUptimeCheckTask().catch(() => ({ has_node: true, group_data: [] }));
      if (this.$refs.checkCards) {
        this.$refs.checkCards.taskDetail = {
          show: false,
          tasks: [],
          name: '',
          id: '',
        };
      }
      this.hasNode = data.has_node;
      this.group.data = data.group_data;
      this.setKeyword(this.header.keyword);
      this.handleEditMetric(this.$route.params.taskId);
      this.allLoading = false;
    },
    handleEditMetric(id) {
      if (id !== undefined) {
        const task = this.searchData.find(item => item.id === id);
        task && this.handleEditTask(task);
      }
    },
    handleEditTask(task) {
      this.$router.push({
        name: 'uptime-check-task-edit',
        params: {
          id: task.id,
          bizId: task.bk_biz_id,
        },
      });
    },
    handleAllDataFetch() {
      return this.getTaskData();
    },
    handleSetAllLoading(v) {
      this.allLoading = v;
    },
    handleDetailShow(item) {
      const { groupLimit, groupId } = this.detail;
      this.$router.push({
        name: groupLimit && groupId ? 'uptime-check-group-detail' : 'uptime-check-task-detail',
        params: {
          taskId: item.id,
          groupId: groupLimit && groupId ? groupId : 0,
        },
      });
    },
    handleTaskDetail(v) {
      this.taskDetail = v;
    },
    handleDebounceSearch(v) {
      const keyword = typeof v === 'string' ? v.trim() : '';
      this.header.keyword = keyword;
      let params = keyword;
      if (this.taskDetail?.show) {
        const { show, tasks } = this.taskDetail;
        params = {
          keyword,
          groupDetail: show,
          tasks,
        };
      }
      this.setKeyword(params);
      this.$emit('node-name-change');
    },
    updateList() {
      this.getTaskData();
    },
    importFile() {
      this.options.isShow = true;
    },
    handleComplete() {
      this.getTaskData();
    },
    handleCreateNode() {
      this.$router.push({
        name: 'uptime-check-node-add',
      });
    },
    handleChangeGroupStatus() {
      return this.getTaskData(false);
    },
    handleGroupIdChange(id) {
      this.detail.groupId = id;
      this.detail.groupLimit = this.header.switch === 0 && id !== -1;
    },
    handleSwitchChange(v) {
      this.header.switch = v;
      this.detail.groupLimit = this.header.switch === 0 && this.detail.groupId !== -1;
    },
    handleCreateTask() {
      const params = {
        title: this.$t('新建拨测任务'),
      };
      if (!this.header.switch && this.$refs.checkCards && this.$refs.checkCards._data.taskDetail.name) {
        params.groupName = this.$refs.checkCards._data.taskDetail.name;
      }
      this.$router.push({
        name: 'uptime-check-task-add',
        params,
      });
    },
    handleCreateTaskGroup() {
      this.$bus.$emit('handle-create-task-group');
    },
  },
};
</script>
<style lang="scss" scoped>
.uptime-task {
  min-height: calc(100vh - 80px);

  &-header {
    display: flex;
    align-items: center;

    .search-item {
      margin-right: 10px;
    }

    .search-input {
      flex: 0 0 320px;
      margin-left: auto;
      margin-right: 10px;
    }

    .search-switch {
      display: flex;
      color: #979ba5;
      border-radius: 2px;

      &-icon {
        font-size: 16px;
        width: 32px;
        height: 32px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        border: 1px solid #c4c6cc;
      }

      :first-child {
        border-right: 0;
        border-top-left-radius: 2px;
        border-bottom-left-radius: 2px;
      }

      :last-child {
        border-top-right-radius: 2px;
        border-bottom-right-radius: 2px;
      }

      .icon-active {
        background: #63656e;
        color: #fff;
        border: 0;
      }
    }
  }

  &-container {
    margin-top: 26px;
    overflow: hidden;
  }
}
</style>
