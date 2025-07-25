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
<!--
 * @Date: 2021-06-14 20:44:18
 * @LastEditTime: 2021-06-15 10:50:24
 * @Description:
-->
<template>
  <div
    v-monitor-loading="{ isLoading: loading }"
    class="alarm-group"
  >
    <!-- 列表页 -->
    <div class="alarm-group-tool">
      <bk-button
        v-authority="{ active: !authority.MANAGE_AUTH }"
        class="tool-btn mc-btn-add"
        theme="primary"
        @click="authority.MANAGE_AUTH ? handleShowAddView('add') : handleShowAuthorityDetail()"
      >
        {{ $t('新建') }}
      </bk-button>
      <bk-input
        class="tool-search"
        :placeholder="$t('ID / 告警组名称')"
        :value="keyword"
        right-icon="bk-icon icon-search"
        @change="handleSearch"
      />
    </div>
    <div>
      <bk-table
        class="alarm-group-table"
        :data="table.data"
        :empty-text="$t('无数据')"
      >
        <bk-table-column
          width="70"
          label="ID"
          prop="id"
        >
          <template slot-scope="scope"> #{{ scope.row.id }} </template>
        </bk-table-column>
        <bk-table-column
          :label="$t('名称')"
          min-width="100"
        >
          <template slot-scope="scope">
            <span
              class="notice-group-name"
              @click="handleShowDetailsView(scope.row)"
            >
              {{ scope.row.name }}
            </span>
          </template>
        </bk-table-column>
        <!-- <bk-table-column :label="$t('所属')" prop="bkBizId" min-width="100">
                </bk-table-column> -->
        <bk-table-column
          width="200"
          :label="$t('应用策略数')"
        >
          <template slot-scope="scope">
            <div class="col-appstrategy">
              <span
                v-authority="{ active: scope.row.relatedStrategy > 0 && !authority.STRATEGY_VIEW_AUTH }"
                class="strategy-num"
                :class="{ 'btn-disabled': scope.row.relatedStrategy === 0 }"
                @click="handleToAppStrategy(scope.row)"
              >
                {{ scope.row.relatedStrategy }}
              </span>
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          :label="$t('说明')"
          min-width="180"
          prop="message"
        >
          <template slot-scope="scope">
            {{ scope.row.message || '--' }}
          </template>
        </bk-table-column>
        <bk-table-column
          width="130"
          :label="$t('操作')"
        >
          <template slot-scope="scope">
            <bk-button
              v-authority="{ active: !authority.MANAGE_AUTH }"
              class="col-btn"
              :disabled="!scope.row.editAllowed"
              :text="true"
              @click="authority.MANAGE_AUTH ? handleShowAddView('edit', scope.row.id) : handleShowAuthorityDetail()"
            >
              {{ $t('编辑') }}
            </bk-button>
            <bk-button
              v-authority="{ active: !authority.MANAGE_AUTH }"
              class="col-btn"
              :disabled="!scope.row.deleteAllowed"
              :text="true"
              @click="authority.MANAGE_AUTH ? handleDeleteRow(scope.row.id) : handleShowAuthorityDetail()"
            >
              {{ $t('删除') }}
            </bk-button>
          </template>
        </bk-table-column>
      </bk-table>
      <div class="alarm-group-pagination">
        <template v-if="tableInstance">
          <bk-pagination
            v-show="tableInstance.total"
            class="config-pagination list-pagination"
            :count="tableInstance.total"
            :current="tableInstance.page"
            :limit="tableInstance.pageSize"
            :limit-list="tableInstance.pageList"
            align="right"
            size="small"
            pagination-able
            show-total-count
            @change="handlePageChange"
            @limit-change="handleLimitChange"
          />
        </template>
      </div>
    </div>
    <!-- 详情页 组件 -->
    <alarm-group-detail
      :id="detail.id"
      :authority="authority"
      :detail="detail"
      :handle-show-authority-detail="handleShowAuthorityDetail"
      @detail-close="handleDetailClose"
      @edit-group="handleEditGroup"
    />
  </div>
</template>

<script>
import { deleteNoticeGroup } from 'monitor-api/modules/notice_group';
import { debounce } from 'throttle-debounce';
import { mapActions } from 'vuex';

import { commonPageSizeMixin } from '../../common/mixins';
import authorityMixinCreate from '../../mixins/authorityMixin';
import alarmGroupDetail from './alarm-group-detail/alarm-group-detail-bak.vue';
import * as alarmGroupAuth from './authority-map';
import TableStore from './store.ts';

export default {
  name: 'AlarmGroup',
  components: {
    alarmGroupDetail,
  },
  mixins: [commonPageSizeMixin, authorityMixinCreate(alarmGroupAuth)],
  provide() {
    return {
      authority: this.authority,
      handleShowAuthorityDetail: this.handleShowAuthorityDetail,
      alarmGroupAuth,
    };
  },
  beforeRouteEnter(to, from, next) {
    next(vm => {
      if (!['alarm-group-add', 'alarm-group-edit'].includes(from.name)) {
        vm?.tableInstance?.setDefaultStore?.();
        vm.keyword = '';
      }
      !vm.loading && vm.getNoticeGroupList();
    });
  },
  data() {
    return {
      test: true,
      keyword: '',
      handleSearch() {},
      table: {
        data: [],
      },
      tableInstance: null,
      detail: {
        show: false,
        id: 0,
        title: '',
      },
      loading: false,
    };
  },
  created() {
    this.detail.show = false;
    this.getNoticeGroupList();
    this.handleSearch = debounce(300, this.handleKeywordChange);
  },
  deactivated() {
    this.detail.show = false;
  },
  methods: {
    ...mapActions('alarm-group', ['noticeGroupList']),
    // 详情编辑告警组
    handleEditGroup(id) {
      this.detail.show = false;
      this.handleDetailClose();
      this.handleShowAddView('edit', id);
    },
    // 新增/编辑跳转入口
    handleShowAddView(mode, id) {
      if (mode === 'edit') {
        this.$router.push({
          name: 'alarm-group-edit',
          params: { id },
        });
      } else {
        this.$router.push({ name: 'alarm-group-add' });
      }
    },
    // 告警组详情展示 侧弹窗
    handleShowDetailsView({ name, id }) {
      this.detail.show = true;
      this.detail.id = id;
      this.detail.title = name;
    },
    // 跳转到策略列表  展示相关联告警组的策略
    handleToAppStrategy({ relatedStrategy, name }) {
      if (!relatedStrategy) return;
      if (!this.authority.STRATEGY_VIEW_AUTH) {
        this.handleShowAuthorityDetail(alarmGroupAuth.STRATEGY_VIEW_AUTH);
        return;
      }
      this.$router.push({
        name: 'strategy-config',
        params: { noticeName: name },
      });
    },
    // 删除事件
    handleDeleteRow(id) {
      this.$bkInfo({
        title: this.$t('确认要删除？'),
        maskClose: true,
        confirmFn: () => {
          this.loading = true;
          deleteNoticeGroup({ id_list: [id] })
            .then(() => {
              this.getNoticeGroupList();
              this.$bkMessage({ theme: 'success', message: this.$t('删除成功') });
            })
            .catch(() => (this.loading = false));
        },
      });
    },
    // 翻页切换事件
    handlePageChange(page) {
      this.tableInstance.page = page;
      this.table.data = this.tableInstance.getTableData();
    },
    // 每页最大显示条数切换事件
    handleLimitChange(limit) {
      this.tableInstance.page = 1;
      this.tableInstance.pageSize = limit;
      this.handleSetCommonPageSize(limit);
      this.table.data = this.tableInstance.getTableData();
    },
    // 搜索条件变化事件
    handleKeywordChange(v) {
      this.keyword = v;
      this.tableInstance.keyword = v;
      this.tableInstance.page = 1;
      this.table.data = this.tableInstance.getTableData();
    },
    // 获取告警组列表
    async getNoticeGroupList() {
      this.loading = true;
      const data = await this.noticeGroupList();
      if (!this.tableInstance) {
        this.tableInstance = new TableStore(data);
      } else {
        this.tableInstance.data = data;
        this.tableInstance.total = data.length;
      }
      this.table.data = this.tableInstance.getTableData();
      this.loading = false;
    },
    // 详情页关闭
    handleDetailClose() {
      this.detail.id = 0;
    },
  },
};
</script>

<style lang="scss" scoped>
.alarm-group {
  min-height: calc(100vh - 80px);
  font-size: 12px;

  .alarm-group-tool {
    display: flex;

    .tool-btn {
      margin-right: auto;
    }

    .tool-search {
      width: 360px;
    }
  }

  .alarm-group-table {
    margin-top: 16px;

    .col {
      &-appstrategy {
        width: 59px;
        text-align: right;
      }
    }

    .notice-group-name {
      color: #3a84ff;
      cursor: pointer;
    }

    .strategy-num {
      color: #3a84ff;
      cursor: pointer;
    }

    .btn-disabled {
      color: #c4c6cc;
      cursor: not-allowed;

      &:hover {
        cursor: not-allowed;
        background: transparent;
      }

      i {
        color: #c4c6cc;
      }
    }

    .col-btn {
      margin-right: 8px;
    }
  }

  .alarm-group-pagination {
    .config-pagination {
      display: flex;
      align-items: center;
      justify-content: flex-start;
      height: 60px;
      padding: 0 20px;
      background: #fff;
      border: 1px solid #dcdee5;
      border-top: 0;

      :deep(.bk-page-count) {
        margin-right: auto;
      }
    }
  }

  :deep(.bk-button-text) {
    padding-left: 0;
  }
}
</style>
