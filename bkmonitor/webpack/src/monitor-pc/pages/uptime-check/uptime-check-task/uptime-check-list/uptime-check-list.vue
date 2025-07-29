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
  <div class="task-list">
    <bk-table
      ref="table"
      class="task-list-table"
      :data="tableData"
      :empty-text="$t('没有搜索到相关拨测任务')"
    >
      <bk-table-column
        :label="$t('任务名称')"
        min-width="150"
      >
        <template slot-scope="scope">
          <div class="col-name">
            <span @click="handleClickName(scope.row)">{{ scope.row.name || '--' }}</span>
          </div>
        </template>
      </bk-table-column>
      <bk-table-column
        :label="$t('目标地址')"
        min-width="350"
      >
        <template slot-scope="scope">
          <div class="col-url">
            {{ scope.row.url || '--' }}
          </div>
        </template>
      </bk-table-column>
      <bk-table-column
        :label="$t('协议')"
        min-width="80"
      >
        <template slot-scope="scope">
          <div class="col-url">
            {{ scope.row.protocol }}
          </div>
        </template>
      </bk-table-column>
      <bk-table-column
        :label="$t('响应时长')"
        min-width="120"
      >
        <template slot-scope="scope">
          <span :style="{ color: scope.row.alarm_num === 0 ? '' : '#EA3636' }">
            {{ scope.row.task_duration !== null ? `${scope.row.task_duration}ms` : '--' }}
          </span>
        </template>
      </bk-table-column>
      <bk-table-column
        :label="$t('可用率')"
        min-width="120"
      >
        <template slot-scope="scope">
          <div class="col-available">
            <div class="rate-name">
              {{ scope.row.available !== null ? `${scope.row.available}%` : '--' }}
            </div>
            <bk-progress
              :color="filterAvailable(scope.row.available, scope.row.status)"
              :percent="+(scope.row.available * 0.01).toFixed(2) || 0"
              :show-text="false"
            />
          </div>
        </template>
      </bk-table-column>
      <bk-table-column
        :label="$t('所属分组')"
        min-width="120"
      >
        <template slot-scope="scope">
          <span>{{
            scope.row.groups && scope.row.groups.length ? scope.row.groups.map(item => item.name).join(',') : '--'
          }}</span>
        </template>
      </bk-table-column>
      <bk-table-column
        :label="$t('创建人')"
        min-width="120"
        prop="create_user"
      />
      <bk-table-column
        width="120"
        :label="$t('状态')"
      >
        <template slot-scope="scope">
          <span
            :style="{
              color:
                scope.row.status === 'stoped'
                  ? '#c7c7c7'
                  : ['start_failed', 'stop_failed'].includes(scope.row.status)
                    ? '#EA3636'
                    : '#63656E',
            }"
            >{{ table.statusMap[scope.row.status] }}</span
          >
        </template>
      </bk-table-column>
      <bk-table-column
        width="120"
        :label="$t('启/停')"
      >
        <template slot-scope="scope">
          <bk-switcher
            v-authority="{ active: !authority.MANAGE_AUTH }"
            class="col-switcher"
            :disabled="['starting', 'new_draft', 'stoping'].includes(scope.row.status)"
            :pre-check="() => handleStatusChange(scope.row)"
            :value="scope.row.switch"
            size="small"
          />
        </template>
      </bk-table-column>
      <bk-table-column
        width="150"
        :label="$t('操作')"
      >
        <template slot-scope="scope">
          <div class="col-operate">
            <span
              v-authority="{ active: !authority.MANAGE_AUTH }"
              class="col-operate-btn"
              @click="authority.MANAGE_AUTH ? handleRowEdit(scope) : handleShowAuthorityDetail()"
            >
              {{ $t('编辑') }}
            </span>
            <span
              v-authority="{ active: !authority.MANAGE_AUTH }"
              class="col-operate-btn"
              @click="authority.MANAGE_AUTH ? handleRowDelete(scope.row) : handleShowAuthorityDetail()"
            >
              {{ $t('删除') }}
            </span>
            <span
              v-authority="{ active: !authority.MANAGE_AUTH }"
              :class="['col-operate-more', { 'more-active': popover.active === scope.$index }]"
              @click="
                authority.MANAGE_AUTH
                  ? handleShowMoreList(scope.row, scope.$index, $event)
                  : handleShowAuthorityDetail()
              "
            >
              <i
                class="bk-icon icon-more"
                data-popover="true"
              />
            </span>
          </div>
        </template>
      </bk-table-column>
    </bk-table>
    <bk-pagination
      v-if="tableData?.length"
      class="task-list-pagination list-pagination"
      align="right"
      size="small"
      show-total-count
      v-bind="pagination"
      @change="handlePageChange"
      @limit-change="handleLimitChange"
    />
    <div v-show="false">
      <div
        ref="moreGroup"
        class="more-group"
      >
        <span
          class="more-group-btn"
          @click="handleCloneTask"
        >
          {{ $t('克隆') }}
        </span>
      </div>
    </div>
    <div style="display: none">
      <delete-subtitle
        ref="deleteSubTitle"
        :key="delSubTitle.name"
        :name="delSubTitle.name"
        :title="delSubTitle.title"
      />
    </div>
  </div>
</template>
<script>
import { changeStatusUptimeCheckTask, cloneUptimeCheckTask, destroyUptimeCheckTask } from 'monitor-api/modules/model';
import { createNamespacedHelpers } from 'vuex';

import { uptimeCheckMixin } from '../../../../common/mixins';
import { SET_PAGE, SET_PAGE_SIZE } from '../../../../store/modules/uptime-check-task';
import DeleteSubtitle from '../../../strategy-config/strategy-config-common/delete-subtitle';

const { mapGetters, mapActions, mapMutations } = createNamespacedHelpers('uptime-check-task');
export default {
  name: 'UptimeCheckList',
  components: {
    DeleteSubtitle,
  },
  mixins: [uptimeCheckMixin],
  inject: ['authority', 'handleShowAuthorityDetail'],
  props: {
    changeStatus: Function,
  },
  data() {
    return {
      table: {
        data: [],
        loading: false,
        statusMap: {
          running: this.$t('运行中'),
          stoped: this.$t('已停用'),
          start_failed: this.$t('启用失败'),
          stop_failed: this.$t('停用失败'),
          starting: this.$t('启用中'),
          stoping: this.$t('停用中'),
          new_draft: this.$t('未保存'),
        },
      },
      watchInstance: null,
      popover: {
        instance: null,
        active: -1,
        data: {},
      },
      delSubTitle: {
        title: window.i18n.t('任务名'),
        name: '',
      },
    };
  },
  computed: {
    ...mapGetters(['keyword', 'tableData', 'pagination']),
  },
  created() {
    this.watchInstance = this.$watch('keyword', () => {
      this.setTabelData();
    });
  },
  activated() {
    this.$refs.table.doLayout();
  },
  beforeDestroy() {
    this.watchInstance();
  },
  methods: {
    ...mapActions(['setTabelData']),
    ...mapMutations([SET_PAGE_SIZE, SET_PAGE]),
    handleClickName(item) {
      this.$emit('detail-show', item);
    },
    handlePageChange(page) {
      this.SET_PAGE(page);
      this.setTabelData();
    },
    handleRowEdit(data) {
      this.$emit('edit', data.row);
    },
    handleLimitChange(limit) {
      this.SET_PAGE(1);
      this.SET_PAGE_SIZE(limit);
      this.setTabelData();
    },
    handleStatusChange(row) {
      return new Promise((resolve, reject) => {
        if (!this.authority.MANAGE_AUTH) {
          this.handleShowAuthorityDetail();
          reject();
        }
        this.table.loading = true;
        changeStatusUptimeCheckTask(row.id, { status: row.switch ? 'stoped' : 'running' })
          .then(data => {
            this.changeStatus(row.id, row.status);
            this.$bkMessage({
              theme: 'success',
              message: data.status === 'running' ? this.$t('任务启动成功') : this.$t('任务停止成功'),
            });
            resolve();
          })
          .catch(() => {
            reject();
          })
          .finally(() => (this.table.loading = false));
      });
    },
    async handleRowDelete(row) {
      this.delSubTitle.name = row.name;
      await this.$nextTick();
      const subHeader = this.$refs.deleteSubTitle.$vnode;
      this.$bkInfo({
        type: 'warning',
        title: this.$t('确认要删除？'),
        subHeader,
        maskClose: true,
        confirmFn: () => {
          this.table.loading = true;
          destroyUptimeCheckTask(row.id, {})
            .then(() => {
              this.$bkMessage({
                theme: 'success',
                message: this.$t('删除任务成功！'),
              });
              this.$emit('update-all');
            })
            .finally(() => {
              this.table.loading = false;
            });
        },
      });
    },
    // 显示更多操作
    handleShowMoreList(row, index, e) {
      this.popover.data = row;
      this.popover.active = index;
      if (!this.popover.instance) {
        this.popover.instance = this.$bkPopover(e.target, {
          content: this.$refs.moreGroup,
          arrow: false,
          trigger: 'click',
          placement: 'bottom',
          theme: 'light common-monitor',
          maxWidth: 520,
          duration: [200, 0],
          onHidden: () => {
            this.popover.active = -1;
            this.popover.instance.destroy();
            this.popover.instance = null;
          },
        });
      }
      this.popover.instance?.show(100);
    },
    // 克隆任务
    handleCloneTask() {
      this.table.loading = true;
      cloneUptimeCheckTask(this.popover.data.id, {}, { needRes: true })
        .then(() => {
          this.$emit('update-all');
          this.SET_PAGE(1);
          this.setTabelData();
          this.$bkMessage({
            theme: 'success',
            message: this.$t('克隆任务成功！'),
          });
        })
        .finally(() => {
          this.table.loading = false;
        });
    },
  },
};
</script>
<style lang="scss" scoped>
.task-list {
  font-size: 12px;
  color: #63656e;

  &-table {
    .col-name {
      color: #3a84ff;
      cursor: pointer;
    }

    .col-available {
      .rate-name {
        line-height: 16px;
      }

      :deep(.progress-bar) {
        box-shadow: none;
      }
    }
    // :deep(.bk-table-body) {
    //     width: 100%;
    // }
    .col-switcher {
      &.is-checked {
        background: #3a84ff;
      }
    }

    .col-operate {
      display: flex;
      align-items: center;
      color: #3a84ff;
      cursor: pointer;

      :not(:last-child) {
        margin-right: 10px;
      }

      &-more {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 24px;
        height: 24px;
        border-radius: 50%;

        .icon-more {
          font-size: 14px;
          color: #3a84ff;
        }

        &:hover {
          cursor: pointer;
          background: #ddd;
        }

        &.more-active {
          background: #ddd;
        }
      }
    }

    .col-url {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      direction: rtl;
      unicode-bidi: plaintext;
    }
  }

  &-pagination {
    padding: 15px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-top: 0;
    border-radius: 2px;
  }
}

.more-group {
  display: flex;
  flex-direction: column;
  width: 68px;
  font-size: 12px;
  // padding: 6px 0;
  color: #63656e;
  border: 1px solid #dcdee5;

  &-btn {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    height: 32px;
    padding-left: 10px;
    background: #fff;

    &:hover {
      color: #3a84ff;
      cursor: pointer;
      background: #f0f1f5;
    }
  }
}
</style>
