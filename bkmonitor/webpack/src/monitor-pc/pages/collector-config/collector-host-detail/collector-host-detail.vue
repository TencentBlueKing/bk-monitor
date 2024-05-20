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
    v-bkloading="{ isLoading: loading }"
    class="host-detail"
    :class="{ 'detail-loading': loading }"
  >
    <template v-if="!loading">
      <div
        v-if="tables.length"
        class="host-detail-desc"
      >
        <i class="icon-monitor icon-tips" /> {{ $t('该内容是对') }} {{ tables.config_info.name }} {{ $t('进行') }}“
        <span class="desc-operate">{{ operatorMap[tables.config_info.last_operation] }}</span> ”{{
          $t('操作的执行详情')
        }}
      </div>
      <collector-host-status
        v-if="tables && tables.contents && tables.contents.length"
        :all-data="tables"
        @can-polling="handlePolling"
        @refresh="handleRefreshData"
      />
      <!-- <config-deploy v-if="tables && tables.contents && tables.contents.length" :all-data="tables" @can-polling="handlePolling"></config-deploy> -->
      <empty-detail
        v-else
        :need-title="false"
      >
        <template #desc>
          {{ $t('本次操作未选择目标，无下发操作记录') }}
        </template>
      </empty-detail>
    </template>
  </div>
</template>
<script>
// import ConfigDeploy from '../config-deploy/config-deploy'
import { collectInstanceStatus } from 'monitor-api/modules/collecting';

import authorityMixinCreate from '../../../mixins/authorityMixin';
import * as collectAuth from '../authority-map';
import EmptyDetail from '../collector-add/config-delivery/empty-target';
import CollectorHostStatus from './collector-host-status';

export default {
  name: 'HostDetail',
  components: {
    CollectorHostStatus,
    // ConfigDeploy,
    EmptyDetail,
  },
  mixins: [authorityMixinCreate(collectAuth)],
  provide() {
    return {
      authority: this.authority,
      handleShowAuthorityDetail: this.handleShowAuthorityDetail,
    };
  },
  data() {
    return {
      loading: true,
      needPolling: true,
      pollingCount: 1,
      tables: [],
      operatorMap: {
        ROLLBACK: this.$t('回滚'),
        UPGRADE: this.$t('升级'),
        CREATE: this.$t('新增'),
        EDIT: this.$t('编辑'),
        ADD_DEL: this.$t('增删目标'),
        START: this.$t('启用'),
        STOP: this.$t('停用'),
        AUTO_DEPLOYING: this.$t('自动执行'),
      },
      statusList: ['PENDING', 'RUNNING', 'DEPLOYING', 'STARTING', 'STOPPING'],
    };
  },
  async created() {
    this.loading = true;
    this.id = this.$route.params.id;
    this.$store.commit('app/SET_NAV_TITLE', this.$t('加载中...'));
    await this.getHosts(this.pollingCount).finally(() => {
      this.loading = false;
      this.$store.commit(
        'app/SET_NAV_TITLE',
        `${this.$t('route-' + '执行详情').replace('route-', '')}` +
          '-' +
          `#${this.$route.params.id} ${this.tables.config_info.name}`
      );
    });
  },
  beforeDestroy() {
    window.clearTimeout(this.timer);
  },
  methods: {
    getHosts(count) {
      return collectInstanceStatus({ id: this.id })
        .then(data => {
          if (count !== this.pollingCount) return;
          this.tables = this.handleData(data);
          this.needPolling = data.contents.some(item => item.child.some(set => this.statusList.includes(set.status)));
          if (!this.needPolling) {
            window.clearTimeout(this.timer);
          } else if (count === 1) {
            this.handlePolling();
          }
        })
        .catch(() => {});
    },
    handlePolling(v = true) {
      if (v) {
        this.timer = setTimeout(() => {
          clearTimeout(this.timer);
          this.pollingCount += 1;
          this.getHosts(this.pollingCount).finally(() => {
            if (!this.needPolling) return;
            this.handlePolling();
          });
        }, 10000);
      } else {
        window.clearTimeout(this.timer);
      }
    },
    handleRefreshData() {
      return collectInstanceStatus({ id: this.id })
        .then(data => {
          this.tables = this.handleData(data);
        })
        .catch(() => {});
    },
    handleData(data) {
      const oldContent = this.tables.contents;
      const content = data.contents;
      const sumData = {
        pending: {},
        success: {},
        failed: {},
      };
      content.forEach((item, index) => {
        item.failedNum = 0;
        item.pendingNum = 0;
        item.successNum = 0;
        item.table = [];
        item.expand = oldContent?.length && oldContent[index] ? oldContent[index].expand : item.child.length > 0;
        item.child.forEach(set => {
          if (set.status === 'SUCCESS') {
            item.successNum += 1;
            sumData.success[set.instance_id] = set.instance_id;
          } else if (this.statusList.includes(set.status)) {
            sumData.pending[set.instance_id] = set.instance_id;
            item.pendingNum += 1;
          } else {
            item.failedNum += 1;
            sumData.failed[set.instance_id] = set.instance_id;
          }
        });
      });
      const headerData = {};
      headerData.failedNum = Object.keys(sumData.failed).length;
      headerData.pendingNum = Object.keys(sumData.pending).length;
      headerData.successNum = Object.keys(sumData.success).length;
      data.headerData = headerData;
      headerData.total = headerData.successNum + headerData.failedNum + headerData.pendingNum;
      return data;
    },
    // async handleSetPolling (v) {
    //     this.ajaxMark = true
    //     if (v) {
    //         clearTimeout(this.timer)
    //         await this.getHostData().then(data => {
    //             if (this.ajaxMark) {
    //                 this.tables = this.handleData(data)
    //                 const needPolling = data.contents.some(item => item.child.some(set => (set.status === 'PENDING' || set.status === 'RUNNING')))
    //                 if (!needPolling) {
    //                     window.clearTimeout(this.timer)
    //                 }
    //             }
    //         }).catch(data => {
    //             console.error(data)
    //         }).finally(_ => {
    //             this.handlePolling()
    //         })
    //     } else {
    //         clearTimeout(this.timer)
    //     }
    // }
  },
};
</script>
<style lang="scss" scoped>
.host-detail {
  min-height: calc(100vh - 120px);
  margin: 20px 24px 0;
  color: #63656e;

  &-desc {
    display: flex;
    align-items: center;
    margin: -2px 0 18px;

    .icon-tips {
      height: 14px;
      margin-right: 7px;
      font-size: 14px;
      color: #979ba5;
    }

    .desc-operate {
      font-weight: bold;
    }
  }
}
</style>
