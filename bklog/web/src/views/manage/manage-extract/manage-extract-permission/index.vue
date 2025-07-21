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
    class="extract-auth-manage"
    v-bkloading="{ isLoading }"
    data-test-id="extractAuthManage_div_extractAuthManageBox"
  >
    <div>
      <bk-button
        style="width: 120px; margin: 20px 0"
        class="king-button"
        v-cursor="{ active: isAllowedManage === false }"
        :disabled="isAllowedManage === null || isLoading"
        :loading="isButtonLoading"
        data-test-id="extractAuthManageBox_button_addNewExtractAuthManage"
        theme="primary"
        @click="handleCreateStrategy"
      >
        {{ $t('新增') }}
      </bk-button>
    </div>
    <bk-table
      class="king-table"
      :data="strategyList"
      row-key="strategy_id"
    >
      <bk-table-column
        :label="$t('名称')"
        :render-header="$renderHeader"
        min-width="100"
      >
        <template #default="{ row }">
          <div class="table-ceil-container">
            <span v-bk-overflow-tips>{{ row.strategy_name }}</span>
          </div>
        </template>
      </bk-table-column>
      <bk-table-column
        :label="$t('授权目标')"
        :render-header="$renderHeader"
        min-width="100"
      >
        <template #default="{ row }">
          <div class="table-ceil-container">
            <span v-bk-overflow-tips>{{ row.modules.map(item => item.bk_inst_name).join('; ') }}</span>
          </div>
        </template>
      </bk-table-column>
      <bk-table-column
        :label="$t('文件目录')"
        :render-header="$renderHeader"
        min-width="100"
      >
        <template #default="{ row }">
          <div class="table-ceil-container">
            <span v-bk-overflow-tips>{{ row.visible_dir.join('; ') }}</span>
          </div>
        </template>
      </bk-table-column>
      <bk-table-column
        :label="$t('文件后缀')"
        :render-header="$renderHeader"
        min-width="100"
      >
        <template #default="{ row }">
          <div class="table-ceil-container">
            <span v-bk-overflow-tips>{{ row.file_type.join('; ') }}</span>
          </div>
        </template>
      </bk-table-column>
      <bk-table-column
        :label="$t('执行人')"
        :render-header="$renderHeader"
        min-width="100"
      >
        <template #default="{ row }">
          <div class="table-ceil-container">
            <span v-bk-overflow-tips>{{ row.operator || '--' }}</span>
          </div>
        </template>
      </bk-table-column>
      <bk-table-column
        :label="$t('创建时间')"
        :render-header="$renderHeader"
        min-width="100"
        prop="created_at"
      >
      </bk-table-column>
      <bk-table-column
        :label="$t('创建人')"
        :render-header="$renderHeader"
        min-width="80"
        prop="created_by"
      >
      </bk-table-column>
      <bk-table-column
        :label="$t('操作')"
        :render-header="$renderHeader"
        min-width="80"
      >
        <template #default="{ row }">
          <div class="task-operation-container">
            <span
              class="task-operation"
              @click="handleEditStrategy(row)"
              >{{ $t('编辑') }}</span
            >
            <span
              class="task-operation"
              @click="handleDeleteStrategy(row)"
              >{{ $t('删除') }}</span
            >
          </div>
        </template>
      </bk-table-column>
      <template #empty>
        <div>
          <empty-status
            :empty-type="emptyType"
            @operation="handleOperation"
          />
        </div>
      </template>
    </bk-table>

    <bk-sideslider
      :before-close="handleCloseSidebar"
      :is-show.sync="showManageDialog"
      :quick-close="true"
      :title="type === 'create' ? $t('新增') : $t('编辑')"
      :width="520"
      transfer
    >
      <template #content>
        <directory-manage
          ref="directoryRef"
          v-bkloading="{ isLoading: isSliderLoading }"
          :allow-create="allowCreate"
          :strategy-data="strategyData"
          :user-api="userApi"
          @confirm="confirmCreateOrEdit"
        />
      </template>
    </bk-sideslider>
  </div>
</template>

<script>
import EmptyStatus from '@/components/empty-status';
import SidebarDiffMixin from '@/mixins/sidebar-diff-mixin';
import { mapGetters } from 'vuex';

import * as authorityMap from '../../../../common/authority-map';
import DirectoryManage from './directory-manage';

export default {
  name: 'ManageExtract',
  components: {
    DirectoryManage,
    EmptyStatus,
  },
  mixins: [SidebarDiffMixin],
  data() {
    return {
      isLoading: true,
      strategyList: [],
      allowCreate: false,
      isAllowedManage: null, // 是否有管理权限
      isButtonLoading: false, // 没有权限时点击新增按钮请求权限链接
      users: [],
      showManageDialog: false,
      isSliderLoading: false,
      type: '', // 新增或编辑策略
      strategyData: {}, // 新增或编辑策略时传递的数据
      userApi: '',
      emptyType: 'empty',
    };
  },
  computed: {
    ...mapGetters(['spaceUid']),
  },
  created() {
    this.checkManageAuth();
  },
  methods: {
    async checkManageAuth() {
      try {
        const res = await this.$store.dispatch('checkAllowed', {
          action_ids: [authorityMap.MANAGE_EXTRACT_AUTH],
          resources: [
            {
              type: 'space',
              id: this.spaceUid,
            },
          ],
        });
        this.isAllowedManage = res.isAllowed;
        if (res.isAllowed) {
          this.initStrategyList();
          this.allowCreate = false;
          this.userApi = window.BK_LOGIN_URL;
        } else {
          this.isLoading = false;
        }
      } catch (err) {
        console.warn(err);
        this.isLoading = false;
        this.isAllowedManage = false;
      }
    },
    async initStrategyList() {
      try {
        this.isLoading = true;
        const res = await this.$http.request('extractManage/getStrategyList', {
          query: { bk_biz_id: this.$store.state.bkBizId },
        });
        this.strategyList = res.data;
      } catch (e) {
        console.warn(e);
        this.emptyType = '500';
      } finally {
        this.isLoading = false;
      }
    },
    async handleCreateStrategy() {
      if (!this.isAllowedManage) {
        try {
          this.isButtonLoading = true;
          const res = await this.$store.dispatch('getApplyData', {
            action_ids: [authorityMap.MANAGE_EXTRACT_AUTH],
            resources: [
              {
                type: 'space',
                id: this.spaceUid,
              },
            ],
          });
          this.$store.commit('updateAuthDialogData', res.data);
        } catch (err) {
          console.warn(err);
        } finally {
          this.isButtonLoading = false;
        }
        return;
      }

      this.type = 'create';
      this.showManageDialog = true;
      this.strategyData = {
        strategy_name: '',
        user_list: [],
        visible_dir: [''],
        file_type: [''],
        operator: this.$store.state.userMeta.operator,
        select_type: 'topo',
        modules: [],
      };
    },
    handleEditStrategy(row) {
      this.type = 'edit';
      this.showManageDialog = true;
      this.strategyData = row;
    },
    handleDeleteStrategy(row) {
      this.$bkInfo({
        title: `${this.$t('确定要删除')}【${row.strategy_name}】？`,
        closeIcon: false,
        confirmFn: this.syncConfirmFn.bind(this, row.strategy_id),
      });
    },
    // 这里使用同步是为了点击确认后立即关闭info
    syncConfirmFn(id) {
      this.confirmDeleteStrategy(id);
    },
    async confirmDeleteStrategy(id) {
      try {
        this.isLoading = true;
        await this.$http.request('extractManage/deleteStrategy', {
          params: {
            strategy_id: id,
          },
        });
        this.messageSuccess(this.$t('删除成功'));
        await this.initStrategyList();
      } catch (e) {
        console.warn(e);
        this.isLoading = false;
      }
    },
    async confirmCreateOrEdit(strategyData) {
      if (strategyData === null) {
        this.showManageDialog = false;
        return;
      }

      this.isSliderLoading = true;
      const data = Object.assign(strategyData, {
        bk_biz_id: this.$store.state.bkBizId,
      });

      if (this.type === 'create') {
        try {
          await this.$http.request('extractManage/createStrategy', {
            data,
          });
          this.showManageDialog = false;
          this.messageSuccess(this.$t('创建成功'));
          await this.initStrategyList();
        } catch (e) {
          console.warn(e);
        } finally {
          this.isSliderLoading = false;
        }
      } else if (this.type === 'edit') {
        try {
          await this.$http.request('extractManage/updateStrategy', {
            params: {
              strategy_id: data.strategy_id,
            },
            data,
          });
          this.messageSuccess(this.$t('修改成功'));
          this.showManageDialog = false;
          await this.initStrategyList();
        } catch (e) {
          console.warn(e);
        } finally {
          this.isSliderLoading = false;
        }
      }
    },
    handleOperation(type) {
      if (type === 'refresh') {
        this.emptyType = 'empty';
        this.initStrategyList();
        return;
      }
    },
    async handleCloseSidebar() {
      return await this.$refs.directoryRef.handleCloseSidebar();
    },
  },
};
</script>

<style lang="scss" scoped>
  .extract-auth-manage {
    padding: 0 24px 20px;

    /*表格内容样式*/
    :deep(.king-table) {
      .task-operation-container {
        display: flex;
        align-items: center;

        .task-operation {
          margin-right: 12px;
          color: #3a84ff;
          cursor: pointer;
        }
      }
    }
  }
</style>
