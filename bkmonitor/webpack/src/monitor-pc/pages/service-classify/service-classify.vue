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
    class="service-classify"
  >
    <div class="service-classify-tool">
      <bk-button
        class="tool-btn mc-btn-add"
        theme="primary"
        @click="handleShowAddView"
      >
        {{ $t('新建') }}
      </bk-button>
      <div class="tool-explanation">
        <i class="icon-monitor icon-tips" /><span>
          {{ $t('修改或删除分类请') }}
          <span
            class="tool-span"
            @click="handleToCMDB"
          >
            {{ $t('前往CMDB') }}
          </span></span
        >
      </div>
      <bk-input
        class="tool-search"
        :placeholder="$t('一级分类 / 二级分类')"
        right-icon="bk-icon icon-search"
        @change="handleSearch"
      />
    </div>
    <div class="service-classify-panel">
      <ul class="panel-tab">
        <li
          v-for="(item, index) in panel.data"
          :key="index"
          class="panel-tab-item"
          :class="{ 'tab-active': index === panel.active }"
          @click="index !== panel.active && handleTabItemClick(index)"
        >
          <span class="tab-name">{{ item.name }}</span>
          <span class="tab-mark">{{ item.total }}</span>
        </li>
        <li class="panel-tab-blank" />
      </ul>
    </div>
    <div class="service-classify-table">
      <bk-table
        :empty-text="$t('无数据')"
        :data="table.data"
        @row-mouse-enter="i => (table.hoverIndex = i)"
        @row-mouse-leave="i => (table.hoverIndex = -1)"
      >
        <bk-table-column
          v-if="false"
          :label="$t('所属')"
          prop="bizName"
          min-width="120"
        />
        <bk-table-column
          :label="$t('一级分类')"
          prop="first"
          min-width="100"
        />
        <bk-table-column
          :label="$t('二级分类')"
          min-width="100"
        >
          <template slot-scope="scope">
            <div class="table-row">
              <span
                v-if="scope.$index !== table.editIndex"
                class="col-edit"
                >{{ scope.row.second }}</span
              >
              <!-- <bk-input v-if="scope.$index === table.editIndex" :ref="'label-' + scope.$index"
                                        :maxlength="50"
                                        v-model="table.editName"
                                        @keydown="handleLabelKey(scope, ...arguments)"
                                        v-bk-clickoutside="handleTagClickout"></bk-input>
                                    <i @click.stop.prevent="handleEditLabel(scope, $event)" v-show="scope.$index !== table.editIndex && table.hoverIndex === scope.$index" class="icon-monitor icon-bianji col-btn" style="font-size: 24px "></i> -->
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          :label="$t('指标数')"
          min-width="100"
        >
          <template slot-scope="scope">
            <div class="col-target">
              <span
                class="col-btn"
                :class="{ zero: !scope.row.metricCount }"
                @click="handleToTarget(scope.row)"
                >{{ scope.row.metricCount }}</span
              >
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          :label="$t('采集配置')"
          min-width="100"
        >
          <template slot-scope="scope">
            <div class="col-config">
              <span
                v-authority="{ active: !authority.COLLECTION_VIEW_AUTH }"
                class="col-btn"
                :class="{ zero: !scope.row.configCount }"
                @click="
                  authority.COLLECTION_VIEW_AUTH
                    ? handleToCollectionConfig(scope.row)
                    : handleShowAuthorityDetail(serviceClassifyAuth.COLLECTION_VIEW_AUTH)
                "
              >
                {{ scope.row.configCount }}
              </span>
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          :label="$t('策略配置')"
          min-width="100"
        >
          <template slot-scope="scope">
            <div class="col-config">
              <span
                v-authority="{ active: !authority.RULE_VIEW_AUTH }"
                class="col-btn"
                :class="{ zero: !scope.row.strategyCount }"
                @click="
                  authority.RULE_VIEW_AUTH
                    ? handleToStrategyConfig(scope.row)
                    : handleShowAuthorityDetail(serviceClassifyAuth.RULE_VIEW_AUTH)
                "
              >
                {{ scope.row.strategyCount }}
              </span>
            </div>
          </template>
        </bk-table-column>
        <bk-table-column
          :label="$t('操作')"
          width="150"
        >
          <template slot-scope="scope">
            <span
              v-authority="{ active: !authority.EXPORT_MANAGE_AUTH }"
              class="col-btn"
              @click="
                authority.EXPORT_MANAGE_AUTH
                  ? handleConfigurationExport(scope.row)
                  : handleShowAuthorityDetail(serviceClassifyAuth.EXPORT_MANAGE_AUTH)
              "
            >
              {{ $t('配置导出') }}
            </span>
          </template>
        </bk-table-column>
      </bk-table>
      <div class="alarm-group-pagination">
        <template v-if="tableInstance">
          <bk-pagination
            v-show="tableInstance.total"
            class="config-pagination"
            align="right"
            size="small"
            pagination-able
            :current="tableInstance.page"
            :limit="tableInstance.pageSize"
            :count="tableInstance.total"
            :limit-list="tableInstance.pageList"
            show-total-count
            @change="handlePageChange"
            @limit-change="handleLimitChange"
          />
        </template>
      </div>
    </div>
  </div>
</template>

<script>
import { serviceCategoryList } from 'monitor-api/modules/service_classify';
import { debounce } from 'throttle-debounce';

import { commonPageSizeMixin } from '../../common/mixins';
import authorityMixinCreate from '../../mixins/authorityMixin';
import * as serviceClassifyAuth from './authority-map';
import TableStore from './store';

export default {
  name: 'ServiceClassify',
  mixins: [commonPageSizeMixin, authorityMixinCreate(serviceClassifyAuth)],
  data() {
    return {
      serviceClassifyAuth,
      header: {
        keyword: '',
        handelSearch() {},
      },
      loading: true,
      panel: {
        isLoading: false,
        active: 0,
        data: [
          {
            name: this.$t('服务分类'),
            total: 0,
          },
          // {
          //     name: '主机分类',
          //     total: '29'
          // }
        ],
      },
      table: {
        data: [],
        tableData: [],
        loading: false,
        hoverIndex: -1,
        editIndex: -1,
        editName: '',
      },
      tableInstance: null,
      bizList: [],
    };
  },
  created() {
    this.bizList = this.$store.getters.bizList;
    this.handleGetListData();
    this.handleSearch = debounce(300, this.handleKeywordChange);
  },
  methods: {
    handleGetListData(needLoading = true) {
      this.loading = needLoading;
      serviceCategoryList()
        .then(data => {
          const biz = this.bizList.find(item => item.id === this.$store.getters.bizId);
          this.tableInstance = new TableStore(data, biz.text);
          this.panel.data[0].total = this.tableInstance.total || 0;
          this.table.data = this.tableInstance.getTableData();
        })
        .finally(() => {
          this.loading = false;
        });
    },
    handleTabItemClick(index) {
      this.panel.active = index;
      const { tableInstance } = this;
      tableInstance.page = 1;
      this.table.data = this.getTableData();
    },
    handleKeywordChange(v) {
      this.tableInstance.keyword = v;
      this.tableInstance.keyword = v;
      this.tableInstance.page = 1;
      this.table.data = this.tableInstance.getTableData();
    },
    handleToCMDB() {
      window.open(`${this.$store.getters.cmdbUrl}/#/business/${this.$store.getters.bizId}/service/cagetory`, '_blank');
    },
    handleToTarget() {
      // alert('跳转到指标数')
    },
    handleToCollectionConfig(data) {
      if (!data.configCount) return;
      this.$router.push({
        name: 'collect-config',
        params: {
          serviceCategory: `${data.first}-${data.second}`,
        },
      });
    },
    handleToStrategyConfig(data) {
      if (!data.strategyCount) return;
      this.$router.push({
        name: 'strategy-config',
        params: {
          serviceCategory: `${data.first}-${data.second}`,
        },
      });
    },
    handleConfigurationExport(row) {
      const params = {
        first: row.first,
        second: row.second,
      };
      this.$router.push({
        name: 'export-configuration',
        params,
      });
    },
    handlePageChange(page) {
      this.tableInstance.page = page;
      this.table.data = this.tableInstance.getTableData();
    },
    handleLimitChange(limit) {
      this.tableInstance.page = 1;
      this.tableInstance.pageSize = limit;
      this.handleSetCommonPageSize(limit);
      this.table.data = this.tableInstance.getTableData();
    },
    handleShowAddView() {
      window.open(`${this.$store.getters.cmdbUrl}/#/business/${this.$store.getters.bizId}/service/cagetory`, '_blank');
    },
  },
};
</script>

<style lang="scss" scoped>
.service-classify {
  min-height: calc(100vh - 80px);
  font-size: 12px;
  color: #63656e;

  &-tool {
    display: flex;
    align-items: center;

    .tool-explanation {
      display: flex;
      align-items: center;
      margin-right: auto;
      margin-left: 21px;

      .tool-span {
        color: #3a84ff;
        cursor: pointer;
      }

      i {
        margin-top: 3px;
        margin-right: 7px;
        font-size: 14px;
        color: #979ba5;
      }
    }

    .tool-search {
      width: 360px;
    }
  }

  &-panel {
    height: 52px;
    margin-top: 16px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-bottom: 0;
    border-radius: 2px 2px 0 0;

    .panel-tab {
      display: flex;
      padding: 0;
      margin: 0;
      overflow: auto;
      background: #fafbfd;

      &-item {
        display: flex;
        flex: 0 0 auto;
        align-items: center;
        justify-content: center;
        min-width: 120px;
        height: 42px;
        padding: 0 20px;
        font-size: 14px;
        color: #63656e;
        cursor: pointer;
        border-right: 1px solid #dcdee5;
        border-bottom: 1px solid #dcdee5;

        .tab-name {
          margin-right: 6px;
          font-weight: bold;
        }

        .tab-mark {
          display: flex;
          align-items: center;
          justify-content: center;
          min-width: 24px;
          height: 16px;
          padding: 0px 4px;
          font-size: 12px;
          line-height: 14px;
          color: #fff;
          background: #c4c6cc;
          border-radius: 12px;
        }

        &.tab-active {
          color: #3a84ff;
          background: #fff;
          border-bottom-color: transparent;

          .tab-mark {
            color: #fff;
            background: #3a84ff;
          }
        }

        &:first-child {
          /* stylelint-disable-next-line declaration-no-important */
          border-left-color: transparent !important;
        }

        &:hover {
          color: #3a84ff;
          cursor: pointer;
        }
      }

      &-blank {
        flex: 1;
        height: 42px;
        border-bottom: 1px solid #dcdee5;
      }
    }
  }

  &-table {
    background: #fff;

    .table-row {
      display: flex;
      align-items: center;
      height: 32px;
    }

    .col {
      &-target {
        width: 48px;
        text-align: right;
      }

      &-config {
        width: 58px;
        text-align: right;
      }

      &-btn {
        margin-right: 12px;
        color: #3a84ff;
        cursor: pointer;
      }

      &-edit {
        margin-right: 3px;
      }
    }

    .zero {
      color: #c4c6cc;
      cursor: not-allowed;
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
  }
}
</style>
