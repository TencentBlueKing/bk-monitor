<!--
* Tencent is pleased to support the open source community by making
* 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
*
* Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
    ref="uptimeCheckTask"
    v-bkloading="{ isLoading: group.loading }"
  >
    <group-cards
      ref="groupCards"
      :group="group.data"
      :task-detail.sync="taskDetail"
      @resize="handleWindowResize"
      @drag-drop="handleDragDrop"
      @group-delete="handleGroupDelete"
      @group-edit="handleGroupEdit"
    />
    <task-cards
      v-show="hasSearchData"
      ref="taskCards"
      :task-detail.sync="taskDetail"
      v-on="$listeners"
      @delete-task="handleDeleteTask"
      @clone-task="handleCloneTask"
      @change-status="handleChangeStatus"
    />
    <div
      v-show="!hasSearchData"
      class="empty-search-data"
    >
      <i class="icon-monitor icon-hint" /> {{ $t('没有搜索到相关拨测任务') }}
    </div>
    <div style="display: none">
      <delete-subtitle
        ref="deleteSubTitle"
        :key="delSubTitle.name"
        :title="delSubTitle.title"
        :name="delSubTitle.name"
      />
    </div>
  </div>
</template>
<script>
import { addListener, removeListener } from '@blueking/fork-resize-detector';
import {
  addTaskUptimeCheckGroup,
  changeStatusUptimeCheckTask,
  cloneUptimeCheckTask,
  createUptimeCheckGroup,
  destroyUptimeCheckGroup,
  destroyUptimeCheckTask,
  updateUptimeCheckGroup,
} from 'monitor-api/modules/model';
import { debounce } from 'throttle-debounce';
import { createNamespacedHelpers } from 'vuex';

import DeleteSubtitle from '../../../strategy-config/strategy-config-common/delete-subtitle';
import GroupCards from './group-cards.vue';
import TaskCards from './task-cards.vue';

const { mapGetters, mapActions } = createNamespacedHelpers('uptime-check-task');
export default {
  name: 'UptimeCheckCards',
  components: {
    GroupCards,
    TaskCards,
    DeleteSubtitle,
  },
  props: {
    group: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      lisenResize: null,
      taskDetail: {
        show: false,
        tasks: [],
        name: '',
        id: '',
      },
      hasSearchData: true,
      delSubTitle: {
        title: window.i18n.t('任务名'),
        name: '',
      },
    };
  },
  computed: {
    ...mapGetters({ keyword: 'keyword', taskList: 'groupTaskList' }),
  },
  watch: {
    keyword: {
      handler() {
        setTimeout(() => {
          this.hasSearchData = this.refreshListStatus();
          this.$refs.groupCards.handleGroupChange();
        }, 0);
      },
    },
    taskDetail: {
      handler(v) {
        this.getTaskList({ groupDetail: v.show, tasks: v.tasks });
        this.$emit('change-group-id', v.id);
        this.$emit('change-task-detail', v);
      },
    },
  },
  created() {
    this.lisenResize = debounce(300, v => this.handleWindowResize(v));
  },
  activated() {
    this.handleWindowResize();
  },
  mounted() {
    addListener(this.$refs.uptimeCheckTask, this.lisenResize);
    this.handleWindowResize();
  },
  beforeDestroy() {
    removeListener(this.$refs.uptimeCheckTask, this.lisenResize);
  },
  methods: {
    ...mapActions(['getTaskList']),
    refreshListStatus() {
      if (this.taskDetail.show) {
        return !!this.taskList.length;
      }
      return this.$refs.groupCards?.hasGroupList || !!this.taskList.length;
    },
    handleDragDrop(id, data) {
      this.$emit('set-loading', true);
      addTaskUptimeCheckGroup(data.id, {
        id: data.id,
        task_id: id,
      })
        .then(() => {
          this.handleUpdateAll();
        })
        .catch(() => {
          this.$emit('set-loading', false);
        });
    },
    async handleWindowResize() {
      await this.$nextTick();
      this.$refs.groupCards?.refreshItemWidth();
      this.$refs.taskCards?.refreshItemWidth();
    },
    handleGroupDelete(id) {
      destroyUptimeCheckGroup(id, { bk_biz_id: window.bk_biz_id }, { needRes: true })
        .then(res => {
          this.$bkMessage({
            message: res.result ? this.$t('解散任务组成功') : this.$t('解散任务组失败'),
            theme: res.result ? 'success' : 'error',
          });
          this.handleUpdateAll();
        })
        .catch(() => {
          this.$emit('set-loading', false);
        });
    },
    handleUpdateAll() {
      this.$listeners['update-all']().finally(() => {
        setTimeout(() => {
          this.handleWindowResize();
        }, 50);
      });
    },
    handleGroupEdit(params) {
      this.$emit('set-loading', true);
      const editRes = !params.add
        ? updateUptimeCheckGroup(params.id, params, { needRes: true })
        : createUptimeCheckGroup(params, { needRes: true });
      editRes
        .then(res => {
          const success = params.add ? this.$t('创建成功') : this.$t('编辑成功');
          const error = params.add ? this.$t('创建失败') : this.$t('编辑失败');
          this.$bkMessage({
            message: res.result ? success : error,
            theme: res.result ? 'success' : 'error',
          });
          this.handleUpdateAll();
        })
        .catch(() => {
          this.$emit('set-loading', false);
        });
    },
    async handleDeleteTask(item) {
      this.delSubTitle.name = item.name;
      await this.$nextTick();
      const subHeader = this.$refs.deleteSubTitle.$vnode;
      this.$bkInfo({
        type: 'warning',
        title: this.$t('确认要删除？'),
        subHeader,
        maskClose: true,
        confirmFn: () => {
          this.$emit('set-loading', true);
          destroyUptimeCheckTask(item.id, {}, { needRes: true })
            .then(() => {
              this.$bkMessage({
                theme: 'success',
                message: this.$t('删除任务成功！'),
              });
              this.handleUpdateAll();
            })
            .catch(() => {
              this.$emit('set-loading', false);
            });
        },
      });
    },
    // 克隆拨测任务
    handleCloneTask(item) {
      this.$emit('set-loading', true);
      cloneUptimeCheckTask(item.id, {}, { needRes: true })
        .then(() => {
          this.$bkMessage({
            theme: 'success',
            message: this.$t('克隆任务成功！'),
          });
          this.handleUpdateAll();
        })
        .catch(() => {
          this.$emit('set-loading', false);
        });
    },
    // 启停任务
    handleChangeStatus(item) {
      const status = item.switch ? 'stoped' : 'running';
      this.$emit('set-loading', true);
      changeStatusUptimeCheckTask(item.id, { status })
        .then(data => {
          this.$bkMessage({
            theme: 'success',
            message: this.$t(data.status === 'running' ? '任务启动成功' : '任务停止成功'),
          });
          this.handleUpdateAll();
        })
        .finally(() => this.$emit('set-loading', false));
    },
  },
};
</script>
<style lang="scss" scoped>
.empty-search-data {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 42px;
  font-size: 14px;
  color: #63656e;
  background: #fff;
  border: 1px solid #dcdee5;
  border-radius: 2px;

  i {
    margin-right: 8px;
    font-size: 18px;
    color: #979ba5;
  }
}
</style>
