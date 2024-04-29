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
    width="850"
    :value="isShow"
    :close-icon="false"
    :ok-text="$t('添加')"
    :cancel-text="$t('取消')"
    :auto-close="false"
    @value-change="handleValueChange"
  >
    <ip-selector
      ref="ipSelector"
      min-width="850"
      height="410"
      :tab-disabled="1"
      :active-diabled="[0, 2, 3]"
      :active-unshow="[0, 2, 3]"
      :select-unshow="[0, 1]"
      :default-active="1"
      :get-default-data="getDefaultData"
      :get-fetch-data="getFetchData"
      is-show-tree-loading
      is-show-table-loading
      :is-instance="false"
    >
      <template #static-ip-panel="{ data }">
        <bk-table :data="data">
          <bk-table-column
            prop="ip"
            label="IP"
          />
          <bk-table-column
            prop="cloudName"
            :label="$t('管控区域')"
          />
          <bk-table-column
            prop="agentStatus"
            :label="$t('状态')"
          >
            <template #default="{ row }">
              <div
                :class="{
                  'col-status-success': row.agentStatus === 0,
                  'col-status-error': row.agentStatus === -1,
                  'col-status-not-exist': row.agentStatus === 2,
                }"
              >
                {{ agentStatusFilter(row.agentStatus) }}
              </div>
            </template>
          </bk-table-column>
          <bk-table-column
            prop="isBuilt"
            :label="$t('是否配置任务')"
          >
            <template #default="{ row }">
              {{ row.isBuilt ? $t('是') : $t('无') }}
            </template>
          </bk-table-column>
          <bk-table-column
            :label="$t('操作')"
            align="center"
            width="80"
          >
            <template #default="rowData">
              <bk-button
                text
                @click="handleDeleteStaticIp(rowData)"
              >
                {{ $t('移除') }}
              </bk-button>
            </template>
          </bk-table-column>
        </bk-table>
      </template>
      <template #static-topo="{ treeData, disabledData, filterMethod, keyword, nodeCheck }">
        <static-radio-topo
          v-if="treeData.length"
          ref="tree"
          :tree-data="treeData"
          :checked-data="selectorData.checkedData"
          :disabled-data="disabledData"
          :filter-method="filterMethod"
          :keyword="keyword"
          :is-search-no-data.sync="selectorConfig.isSearchNoData"
          :default-expand-node="selectorConfig.defaultExpandNode"
          :height="350"
          @node-check="nodeCheck"
        />
      </template>
    </ip-selector>
    <template #footer>
      <bk-button
        theme="primary"
        :title="$t('添加')"
        class="mr10"
        :disabled="disabledAddBtn"
        @click="handleAddTargetIp"
      >
        {{ $t('添加') }}
      </bk-button>
      <bk-button
        :title="$t('取消')"
        @click="handleCancel"
      >
        {{ $t('取消') }}
      </bk-button>
    </template>
  </bk-dialog>
</template>
<script>
import { getTopoTree } from 'monitor-api/modules/commons';
import { transformDataKey } from 'monitor-common/utils/utils';

import IpSelector from '../../../components/ip-select/ip-select';
import StaticRadioTopo from '../../../components/ip-select/static-radio-topo';

const EVENT_CHANGE = 'change'; // 自定义v-model
const EVENT_CHECKED_IP = 'checked-ip'; // 添加IP事件

export default {
  name: 'UptimeCheckNodeEditTopo',
  components: {
    IpSelector,
    StaticRadioTopo,
  },
  model: {
    prop: 'isShow',
    event: 'change',
  },
  props: {
    isShow: {
      type: Boolean,
      default: false,
    },
    ipList: {
      type: Array,
      default() {
        return [];
      },
    },
    defaultCheckedIp: {
      type: String,
      default: '',
    },
  },
  data() {
    return {
      selectorConfig: {
        isSearchNoData: false,
        defaultExpandNode: 2,
      },
      selectorData: {
        treeData: [],
        checkedData: [],
        disabledData: [],
        tableData: [],
      },
      disabledAddBtn: false,
    };
  },
  watch: {
    'selectorData.tableData': {
      handler(v) {
        // target ip是否配置任务
        this.disabledAddBtn = !(v && v.length === 1 && !v[0].isBuilt);
      },
      immediate: true,
    },
  },
  methods: {
    agentStatusFilter(status) {
      switch (status) {
        case 0:
          return `Agent ${this.$t('正常')}`;
        case -1:
          return `Agent ${this.$t('异常')}`;
        case 2:
          return `Agent ${this.$t('未安装')}`;
      }
    },
    async getDefaultData() {
      this.selectorData.treeData = await getTopoTree({
        bk_biz_id: this.$store.getters.bizId,
        instance_type: 'host',
        remove_empty_nodes: true,
      }).catch(() => []);

      const { treeData, checkedData, disabledData, tableData } = this.selectorData;
      return {
        treeData,
        checkedData,
        disabledData,
        tableData,
      };
    },
    async getFetchData(type, payload) {
      // todo 替换新接口
      const { data } = payload;
      // const __tableData = await getHostInstanceByIp({
      //     bk_biz_id: this.$store.getters.bizId,
      //     bk_biz_ids: [this.$store.getters.bizId],
      //     ip_list: [{
      //         ip: nodeData.ip,
      //         bk_cloud_id: nodeData.bk_cloud_id,
      //         bk_supplier_id: nodeData.bk_supplier_id
      //     }]
      // })
      this.selectorData.tableData = transformDataKey(new Array(this.findItemInIpList(data)));
      this.selectorData.checkedData = [{ bkCloudId: data.bk_cloud_id, ip: data.ip }];

      const { checkedData, tableData, disabledData } = this.selectorData;
      return {
        checkedData,
        tableData,
        disabledData,
      };
    },
    handleDeleteStaticIp() {
      this.selectorData.tableData = [];
      this.selectorData.checkedData = [];
      this.$refs.ipSelector.setCurActivedTableData(this.selectorData.tableData);
    },
    handleValueChange(v) {
      this.$emit(EVENT_CHANGE, v);
    },
    handleAddTargetIp() {
      this.$emit(EVENT_CHECKED_IP, this.selectorData.checkedData[0]);
      this.$emit(EVENT_CHANGE, false);
    },
    handleCancel() {
      this.$emit(EVENT_CHANGE, false);
    },
    findItemInIpList(data) {
      return this.ipList.find(item => item.ip === data.ip && item.bkCloudId === data.bk_cloud_id) || {};
    },
  },
};
</script>
<style lang="scss" scoped>
.col-status {
  &-success {
    color: #2dcb56;
  }

  &-error {
    color: #ea3636;
  }

  &-not-exist {
    color: #c4c6cc;
  }

  :deep(.bk-dialog) {
    &-tool {
      display: none;
    }

    &-body {
      padding: 0;
    }

    &-footer {
      padding: 9px 24px;
      border-top: 0;
    }
  }

  :deep(.ip-select-left) {
    .left-tab {
      display: none;
    }

    .left-content {
      padding-right: 0;

      .left-content-wrap {
        height: 350px;
        margin-right: 6px;
        // max-width: 220px;
      }
    }
  }

  :deep(.static-topo-radio) {
    padding-top: 0;
  }

  :deep(.right-panel) {
    &-title {
      display: none;
    }

    &-content {
      .bk-table .bk-table-header th {
        background: #fafbfd;
      }
    }
  }
}
</style>
