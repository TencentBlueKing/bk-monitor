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
    v-monitor-loading="{ isLoading: loading }"
    class="node-page-container"
  >
    <div v-show="!showCreateCard">
      <div class="header">
        <div class="create-node">
          <bk-button
            v-authority="{
              active: !authority.MANAGE_AUTH,
            }"
            class="mc-btn-add"
            theme="primary"
            @click="authority.MANAGE_AUTH ? addNode() : handleShowAuthorityDetail(uptimeAuth.MANAGE_AUTH)"
          >
            {{ $t('新建') }}
          </bk-button>
        </div>
        <bk-input
          style="width: 320px"
          :placeholder="$t('节点名称/IP')"
          :value="searchWord"
          right-icon="bk-icon icon-search"
          clearable
          @change="search"
        />
      </div>
      <div class="node-table">
        <bk-table
          :data="table.list"
          :empty-text="$t('无数据')"
          row-class-name="row-class"
        >
          <bk-table-column
            width="153"
            :label="$t('节点名称')"
            prop="name"
          />
          <bk-table-column
            label="IP / Url"
            prop="ip"
          />
          <bk-table-column
            width="153"
            :label="$t('类型')"
            prop="is_common"
          >
            <template slot-scope="scope">
              {{ scope.row.is_common ? $t('自建节点(公共)') : $t('自建节点(私有)') }}
            </template>
          </bk-table-column>
          <bk-table-column
            v-if="false"
            :label="$t('所属')"
            prop="bk_biz_name"
          />
          <bk-table-column
            :label="$t('国家/地区')"
            prop="country"
          >
            <template slot-scope="scope">
              <div>{{ scope.row.country ? scope.row.country : '--' }}</div>
            </template>
          </bk-table-column>
          <bk-table-column
            :label="$t('省份')"
            align="center"
          >
            <template slot-scope="scope">
              <div>{{ scope.row.province ? scope.row.province : '--' }}</div>
            </template>
          </bk-table-column>
          <bk-table-column
            :label="$t('关联任务数')"
            align="right"
          >
            <template slot-scope="scope">
              <div
                :style="{ color: scope.row.task_num > 0 ? '#3A84FF' : '#C4C6CC' }"
                class="task-num"
                @click="scope.row.task_num > 0 && handleToCheckTask(scope.row.name)"
              >
                {{ scope.row.task_num || 0 }}
              </div>
            </template>
          </bk-table-column>
          <bk-table-column
            :label="$t('运营商')"
            align="center"
          >
            <template slot-scope="scope">
              <div>{{ scope.row.carrieroperator ? scope.row.carrieroperator : '--' }}</div>
            </template>
          </bk-table-column>
          <bk-table-column :label="$t('状态')">
            <template slot-scope="scope">
              <span
                :class="['col-status', statusColorMap[scope.row.status].className]"
                @mouseenter.stop="handleStatusPopoverShow(scope.row, scope.$index, $event)"
              >
                {{ statusColorMap[scope.row.status].text }}
              </span>
            </template>
          </bk-table-column>
          <bk-table-column :label="$t('操作')">
            <template slot-scope="scope">
              <div>
                <bk-button
                  v-authority="{ active: !authority.MANAGE_AUTH }"
                  :class="[canEdit(scope.row) ? '' : 'not-allowed']"
                  :disabled="!canEdit(scope.row)"
                  theme="primary"
                  text
                  @click="
                    authority.MANAGE_AUTH ? handleEdit(scope.row) : handleShowAuthorityDetail(uptimeAuth.MANAGE_AUTH)
                  "
                >
                  {{ $t('button-编辑') }}
                </bk-button>
                <bk-button
                  v-authority="{ active: !authority.MANAGE_AUTH }"
                  :class="[canEdit(scope.row) ? '' : 'not-allowed']"
                  :disabled="!canEdit(scope.row)"
                  text
                  @click="
                    authority.MANAGE_AUTH
                      ? handleRemove(scope.row.id, scope.row.name)
                      : handleShowAuthorityDetail(uptimeAuth.MANAGE_AUTH)
                  "
                >
                  {{ $t('删除') }}
                </bk-button>
              </div>
            </template>
          </bk-table-column>
        </bk-table>
        <div
          v-show="table.total"
          class="uptime-check-node-footer"
        >
          <bk-pagination
            class="list-pagination"
            :count="table.total"
            :current.sync="table.page"
            :limit="table.pageSize"
            :limit-list="table.pageList"
            align="right"
            show-total-count
            @change="handlePageChange"
            @limit-change="handleLimitChange"
          />
        </div>
      </div>
    </div>
    <div
      v-show="showCreateCard"
      class="not-nodes"
    >
      <div class="desc">
        {{ $t('暂无拨测节点') }}
      </div>
      <div class="create-node-el">
        <div class="title">
          {{ $t('新建') }}
        </div>
        <div class="create-desc">
          {{ $t('创建一个私有或云拨测节点，用于探测服务的质量与可用性') }}
        </div>
        <span
          v-authority="{
            active: !authority.MANAGE_AUTH,
          }"
          class="create-btn"
          @click="authority.MANAGE_AUTH ? addNode() : handleShowAuthorityDetail(uptimeAuth.MANAGE_AUTH)"
        >
          {{ $t('立即新建') }}
        </span>
      </div>
    </div>
    <div v-show="false">
      <div
        ref="popoverContent"
        class="popover-content"
      >
        <div class="popover-hint">
          <div
            v-if="popover.data.status === '2'"
            class="hint-upgrade"
          >
            <div class="hint-text">
              {{ $t('当前采集器版本过低') }}（ {{ popover.data.version }} ），{{ $t('联系系统管理员升级至最新版本') }}（
              {{ popover.data.right_version }}）
            </div>
          </div>
          <div
            v-else-if="popover.data.status === '-1'"
            class="hint-deploy"
          >
            <div class="hint-text">
              <span class="text-content"> {{ $t('bkmonitorbeat采集器异常或版本过低，请至节点管理处理') }} </span>
            </div>
            <div class="hint-btn">
              <bk-button
                class="btn-cancel"
                :text="true"
                @click.stop="handleStatusPopoverHide"
              >
                {{ $t('取消') }}
              </bk-button>
            </div>
          </div>
        </div>
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
import { destroyUptimeCheckNode, listUptimeCheckNode } from 'monitor-api/modules/model';
import { debounce } from 'throttle-debounce';

import { commonPageSizeMixin } from '../../../common/mixins';
import DeleteSubtitle from '../../strategy-config/strategy-config-common/delete-subtitle';

export default {
  name: 'UptimeCheckNodes',
  components: {
    DeleteSubtitle,
  },
  mixins: [commonPageSizeMixin],
  inject: ['authority', 'handleShowAuthorityDetail', 'uptimeAuth'],
  props: {
    fromRouteName: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
      timer: null,
      intv: 1000, // 轮询间隔
      times: 0, // 轮询次数
      timesLimit: 20, // 轮询次数限制
      businessId: Number(this.$store.getters.bizId),
      searchWord: '',
      nodes: [],
      table: {
        list: [],
        loading: false,
        page: 1,
        pageSize: 10,
        pageList: [10, 20, 50, 100],
        total: 0,
      },
      showCreateCard: false,
      statusColorMap: {
        0: {
          className: 'normal',
          text: this.$t('正常'),
        },
        1: {
          className: 'initing',
          text: this.$t('初始化中...'),
        },
        '-1': {
          className: 'error',
          text: this.$t('异常'),
        },
        2: {
          className: 'warning',
          text: this.$t('升级'),
        },
      },
      search() {},
      popover: {
        active: -1,
        instance: null,
        data: {},
      },
      delSubTitle: {
        title: window.i18n.t('节点名称'),
        name: '',
      },
    };
  },
  activated() {
    this.handleRouteEnter();
  },
  deactivated() {
    this.handleStatusPopoverHide();
  },
  created() {
    this.search = debounce(300, v => this.searchNode(v));
  },
  beforeDestroy() {
    this.timer && clearTimeout(this.timer);
    this.handleStatusPopoverHide();
  },
  methods: {
    handleRouteEnter(name) {
      if (!['uptime-check-node-add', 'uptime-check-node-edit'].includes(name)) {
        this.table.page = 1;
        this.table.pageSize = this.handleGetCommonPageSize();
        this.table.total = 0;
        this.searchWord = '';
      }
      !this.loading && this.getNodes();
    },
    handlePageChange(v) {
      this.table.page = v;
      this.handleTableData();
    },
    handleTableData() {
      const tableData = this.nodes.filter(
        item => item.ip.indexOf(this.searchWord) > -1 || item.name.indexOf(this.searchWord) > -1
      );
      const start = this.table.pageSize * (this.table.page - 1);
      const end = this.table.pageSize * this.table.page;
      const data = tableData.slice(start, end);
      this.table.list = data;
      this.table.total = tableData.length;
    },
    handleLimitChange(size) {
      this.table.pageSize = size;
      this.table.page = 1;
      this.handleSetCommonPageSize(size);
      this.handleTableData();
    },
    async handleRemove(id, name) {
      this.delSubTitle.name = name;
      await this.$nextTick();
      const subHeader = this.$refs.deleteSubTitle.$vnode;
      this.$bkInfo({
        type: 'warning',
        title: this.$t('你确认要删除?'),
        subHeader,
        maskClose: true,
        confirmFn: () => {
          this.loading = true;
          destroyUptimeCheckNode(id)
            .then(() => {
              this.getNodes();
              this.$bkMessage({ theme: 'success', message: this.$t('删除成功') });
            })
            .catch(() => {})
            .finally(() => {
              this.loading = false;
            });
        },
      });
    },
    getNodes(loading = true) {
      this.loading = loading;
      return listUptimeCheckNode()
        .then(data => {
          this.showCreateCard = !data.length;
          if (!this.showCreateCard) {
            this.nodes = data;
            this.handleTableData();
          }
        })
        .finally(() => {
          this.loading = false;
        });
    },
    searchNode(v) {
      this.searchWord = v;
      this.table.page = 1;
      this.handleTableData();
    },
    addNode() {
      this.$router.push({
        name: 'uptime-check-node-add',
      });
    },
    handleEdit(data) {
      this.$router.push({
        name: 'uptime-check-node-edit',
        params: {
          id: data.id,
          bizId: data.bk_biz_id,
          title: this.$t('编辑拨测节点'),
        },
      });
    },
    pollNodeData() {
      if (this.times < this.timesLimit) {
        this.getNodes(false);
        this.timer = setTimeout(this.pollNodeData, this.intv);
        this.times += 1;
      } else if (this.timer) {
        clearTimeout(this.timer);
        this.timer = null;
        this.times = 0;
      }
    },
    canEdit(row) {
      return row.bk_biz_id === this.businessId;
    },
    handleStatusPopoverShow(row, index, e) {
      this.handleStatusPopoverHide();
      if (row.status !== '-1' && row.status !== '2') {
        return;
      }
      const { popover } = this;
      popover.data = row;
      popover.instance = this.$bkPopover(e.target, {
        content: this.$refs.popoverContent,
        arrow: true,
        interactive: true,
        // interactiveBorder: 20,
        placement: 'bottom-start',
        theme: 'light task-node',
        maxWidth: 188,
        distance: 0,
        duration: [325, 300],
        // offset: '-35, 0',
        appendTo: () => e.target,
      });
      // .instances[0]
      popover.instance.show(100);
    },
    handleStatusPopoverHide() {
      const { popover } = this;
      if (popover.instance) {
        popover.instance.hide();
        popover.instance.destroy(true);
        popover.instance = null;
      }
    },
    handleToCheckTask(name) {
      this.$emit('set-task', name);
      // this.SET_KEY_WORD(`${this.$t('节点:')}${name}`)
      // this.$store.commit('uptime-check-task/SET_KEY_WORD', )
    },
  },
};
</script>
<style lang="scss" scoped>
.node-page-container {
  .header {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    margin-bottom: 16px;

    .create-node {
      flex: 0 0 130px;
      padding-right: 10px;

      :deep(.bk-button) {
        padding: 0 17px;
      }
    }

    :deep(.icon-search) {
      cursor: pointer;
    }
  }

  .node-table {
    height: calc(100vh - 168px);
    min-height: 513px;

    :deep(.bk-table) {
      overflow: visible;

      .bk-table-body-wrapper {
        overflow: visible;
      }
    }

    :deep(.row-class) {
      color: #63656e;
    }

    .uptime-check-node-footer {
      padding: 15px;
      background: #fff;
      border: 1px solid #dcdee5;
      border-top: 0;
      border-radius: 2px;

      :deep(.bk-page-count) {
        margin-top: 0;
      }
    }

    .normal {
      color: #2dcb56;
    }

    .error {
      color: #ea3636;
      cursor: pointer;
    }

    .warning {
      color: #ffeb00;
      cursor: pointer;
    }

    .task-num {
      color: #3a84ff;
      cursor: pointer;
    }

    .not-allowed {
      color: #c4c6cc;
      cursor: not-allowed;
    }

    :deep(.bk-button-text) {
      padding-left: 0;
    }

    .col-status {
      display: inline-block;
      height: 42px;
      line-height: 42px;
      // width: 50%;
    }
  }

  .not-nodes {
    margin-top: 75px;
    text-align: center;

    .desc {
      margin-bottom: 32px;
      font-size: 20px;
      color: #313238;
    }

    .create-node-el {
      display: inline-block;
      width: 320px;
      height: 220px;
      background: #fff;
      border: 1px solid #f0f1f5;

      .title {
        margin: 40px auto 8px auto;
        font-size: 16px;
        font-weight: bold;
        color: #63656e;
      }

      .create-desc {
        width: 208px;
        margin: auto;
        font-size: 12px;
        line-height: 20px;
        color: #63656e;
      }

      .create-btn {
        display: inline-block;
        width: 160px;
        height: 36px;
        margin-top: 24px;
        font-size: 12px;
        line-height: 36px;
        color: #699df4;
        cursor: pointer;
        border: 1px solid #699df4;
        border-radius: 18px;
      }
    }
  }
}

.popover-content {
  width: 188px;
  height: 78px;
  padding-top: 16px;
  padding-right: 16px;
  padding-left: 16px;
  line-height: normal;

  .hint-title {
    margin-bottom: 15px;
    font-size: 12px;
    color: #606266;
  }

  .hint-text {
    height: 32px;

    .text-content {
      margin-bottom: 15px;
      font-size: 12px;
    }
  }

  .hint-btn {
    text-align: right;

    .btn-confirm {
      margin-right: 10px;
    }

    .btn-cancel {
      padding-right: 0;
    }
  }
}

:deep(.tippy) {
  &-popper {
    max-width: 188px;
  }

  &-tooltip {
    &.task-node-theme {
      padding: 0;
    }
  }
}
</style>
