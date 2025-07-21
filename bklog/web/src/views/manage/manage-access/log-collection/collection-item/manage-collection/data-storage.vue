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
  <div class="data-storage-container">
    <div
      v-if="isShowEditBtn"
      class="edit-btn-container"
    >
      <bk-button
        style="min-width: 88px; color: #3a84ff"
        class="mr10"
        v-cursor="{ active: !editAuth }"
        :theme="'default'"
        @click="handleClickEdit"
      >
        {{ $t('编辑') }}
      </bk-button>
    </div>
    <section class="partial-content">
      <div class="main-title">
        {{ $t('基础信息') }}
      </div>
      <dl class="description-list">
        <dt class="description-term">{{ $t('集群名称') }}</dt>
        <dd class="description-definition">
          <span
            v-bk-tooltips.top="{
              content: `${collectorData.storage_cluster_domain_name}:${collectorData.storage_cluster_port}`,
              disabled: !collectorData.storage_cluster_name,
            }"
            >{{ collectorData.storage_cluster_name || '-' }}</span
          >
        </dd>
        <dt class="description-term">{{ $t('索引集名称') }}</dt>
        <dd class="description-definition">{{ collectorData.table_id_prefix + collectorData.table_id || '--' }}</dd>
        <dt class="description-term">{{ $t('过期时间') }}</dt>
        <dd class="description-definition">{{ collectorData.retention || '--' }}</dd>
        <dt class="description-term">{{ $t('分裂规则') }}</dt>
        <dd class="description-definition">{{ collectorData.index_split_rule || '--' }}</dd>
      </dl>
    </section>
    <section
      style="margin-bottom: 20px"
      class="partial-content"
    >
      <div class="main-title">
        {{ $t('物理索引') }}
      </div>
      <bk-table
        v-bkloading="{ isLoading: tableLoading1 }"
        :data="indexesData"
      >
        <bk-table-column
          :label="$t('索引')"
          min-width="180"
          prop="index"
        ></bk-table-column>
        <bk-table-column
          :label="$t('状态')"
          prop="health"
        >
          <template #default="{ row }">
            <div :class="['status-text', row.health]">
              {{ healthMap[row.health] }}
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          :label="$t('主分片')"
          prop="pri"
        ></bk-table-column>
        <bk-table-column
          :label="$t('副本分片')"
          prop="rep"
        ></bk-table-column>
        <bk-table-column :label="$t('文档计数')">
          <template #default="{ row }">
            {{ row['docs.count'] }}
          </template>
        </bk-table-column>
        <bk-table-column :label="$t('存储大小')">
          <template #default="{ row }">
            {{ getFileSize(row['store.size']) }}
          </template>
        </bk-table-column>
        <template #empty>
          <div>
            <empty-status empty-type="empty" />
          </div>
        </template>
      </bk-table>
    </section>
  </div>
</template>

<script>
import { formatFileSize } from '@/common/util';
import EmptyStatus from '@/components/empty-status';
export default {
  components: {
    EmptyStatus,
  },
  props: {
    collectorData: {
      type: Object,
      required: true,
    },
    isShowEditBtn: {
      type: Boolean,
      default: false,
    },
    editAuth: {
      type: Boolean,
      default: false,
    },
    editAuthData: {
      type: Object,
      default: null,
      validator(value) {
        // 校验 value 是否为 null 或一个有效的对象
        return value === null || (typeof value === 'object' && value !== null);
      },
    },
  },
  data() {
    return {
      tableLoading1: true,
      indexesData: [],
      // 健康状态，文案待定，先不国际化
      healthMap: {
        green: this.$t('健康'),
        yellow: this.$t('部分故障'),
        red: this.$t('严重故障'),
      },
      tableLoading2: true,
      timeField: '',
      fieldsData: [],
    };
  },
  created() {
    this.fetchIndexes();
  },
  methods: {
    getFileSize(size) {
      return formatFileSize(size);
    },
    async fetchIndexes() {
      try {
        const res = await this.$http.request('source/getIndexes', {
          params: {
            collector_config_id: this.collectorData.collector_config_id,
          },
        });
        this.indexesData = res.data;
      } catch (e) {
        console.warn(e);
      } finally {
        this.tableLoading1 = false;
      }
    },
    handleClickEdit() {
      if (!this.editAuth && this.editAuthData) {
        this.$store.commit('updateAuthDialogData', this.editAuthData);
        return;
      }
      const params = {
        collectorId: this.$route.params.collectorId,
      };
      this.$router.push({
        name: 'collectStorage',
        params,
        query: {
          spaceUid: this.$store.state.spaceUid,
          backRoute: 'manage-collection',
          type: 'dataStorage',
        },
      });
    },
  },
};
</script>

<style lang="scss" scoped>
  .data-storage-container {
    .edit-btn-container {
      display: flex;
      align-items: center;
      justify-content: end;
      width: 100%;
    }
  }

  .description-list {
    display: flex;
    flex-flow: wrap;
    font-size: 12px;
    line-height: 16px;

    .description-term {
      width: 120px;
      height: 40px;
      padding-right: 20px;
      color: #979ba5;
      text-align: right;
    }

    .description-definition {
      width: calc(100% - 200px);
      height: 40px;
      color: #63656e;
    }
  }

  .status-text {
    &.green {
      color: #2dcb56;
    }

    &.yellow {
      color: #ff9c01;
    }

    &.red {
      color: #ea3636;
    }
  }

  .icon-date-picker {
    font-size: 16px;
    color: #979ba5;
  }
</style>
