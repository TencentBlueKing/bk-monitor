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
  <section
    class="clean-template-container"
    data-test-id="cleanTemplate_section_cleanTemplateBox"
  >
    <section class="top-operation">
      <bk-button
        class="fl"
        data-test-id="cleanTemplateBox_button_addNewCleanTemplate"
        theme="primary"
        @click="handleCreate"
      >
        {{ $t('新建') }}
      </bk-button>
      <div class="clean-search fr">
        <bk-input
          v-model="params.keyword"
          :clearable="true"
          :right-icon="'bk-icon icon-search'"
          data-test-id="cleanTemplateBox_input_cleanTemplateSearch"
          @change="handleSearchChange"
          @enter="search"
        >
        </bk-input>
      </div>
    </section>
    <section class="clean-template-list">
      <bk-table
        ref="cleanTable"
        class="clean-table"
        v-bkloading="{ isLoading: isTableLoading }"
        :data="templateList"
        :limit-list="pagination.limitList"
        :pagination="pagination"
        :render-header="$renderHeader"
        :size="size"
        data-test-id="cleanTemplateBox_table_cleanTemplateTable"
        @filter-change="handleFilterChange"
        @page-change="handlePageChange"
        @page-limit-change="handleLimitChange"
      >
        <bk-table-column :label="$t('模板名称')">
          <template #default="props">
            {{ props.row.name }}
          </template>
        </bk-table-column>
        <bk-table-column
          :filter-multiple="false"
          :filters="formatFilters"
          :label="$t('格式化方法')"
          :render-header="$renderHeader"
          class-name="filter-column"
          column-key="clean_type"
          prop="clean_type"
        >
          <template #default="props">
            {{ getFormatName(props.row) }}
          </template>
        </bk-table-column>
        <bk-table-column
          width="200"
          :label="$t('操作')"
          :render-header="$renderHeader"
        >
          <template #default="props">
            <div class="collect-table-operate">
              <!-- 编辑 -->
              <bk-button
                class="mr10 king-button"
                theme="primary"
                text
                @click.stop="operateHandler(props.row, 'edit')"
              >
                {{ $t('编辑') }}
              </bk-button>
              <!-- 删除 -->
              <bk-button
                class="mr10 king-button"
                theme="primary"
                text
                @click.stop="operateHandler(props.row, 'delete')"
              >
                {{ $t('删除') }}
              </bk-button>
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
    </section>
  </section>
</template>

<script>
import { clearTableFilter } from '@/common/util';
import EmptyStatus from '@/components/empty-status';
import { mapGetters } from 'vuex';

export default {
  name: 'CleanTemplate',
  components: {
    EmptyStatus,
  },
  data() {
    return {
      isTableLoading: true,
      size: 'small',
      pagination: {
        current: 1,
        count: 0,
        limit: 10,
        limitList: [10, 20, 50, 100],
      },
      templateList: [],
      params: {
        keyword: '',
        clean_type: '',
      },
      emptyType: 'empty',
      isFilterSearch: false,
    };
  },
  computed: {
    ...mapGetters({
      spaceUid: 'spaceUid',
      bkBizId: 'bkBizId',
      globalsData: 'globals/globalsData',
    }),
    formatFilters() {
      const { etl_config: etlConfig } = this.globalsData;
      const target = [];
      etlConfig?.forEach(data => {
        target.push({
          text: data.name,
          value: data.id,
        });
      });
      // target.push({ text: '原始数据', value: 'bk_log_text' });
      return target;
    },
  },
  created() {
    this.search();
  },
  methods: {
    search() {
      this.pagination.current = 1;
      this.requestData();
    },
    handleCreate() {
      this.$router.push({
        name: 'clean-template-create',
        query: {
          spaceUid: this.$store.state.spaceUid,
        },
      });
    },
    handleFilterChange(data) {
      Object.keys(data).forEach(item => {
        this.params[item] = data[item].join('');
      });
      this.isFilterSearch = Object.values(data).reduce((pre, cur) => ((pre += cur.length), pre), 0);
      this.search();
    },
    /**
     * 分页变换
     * @param  {Number} page 当前页码
     * @return {[type]}      [description]
     */
    handlePageChange(page) {
      if (this.pagination.current !== page) {
        this.pagination.current = page;
        this.requestData();
      }
    },
    /**
     * 分页限制
     * @param  {Number} page 当前页码
     * @return {[type]}      [description]
     */
    handleLimitChange(page) {
      if (this.pagination.limit !== page) {
        this.pagination.current = 1;
        this.pagination.limit = page;
        this.requestData();
      }
    },
    requestData() {
      this.isTableLoading = true;
      this.emptyType = this.params.keyword || this.isFilterSearch ? 'search-empty' : 'empty';
      this.$http
        .request('clean/cleanTemplate', {
          query: {
            ...this.params,
            bk_biz_id: this.bkBizId,
            page: this.pagination.current,
            pagesize: this.pagination.limit,
          },
        })
        .then(res => {
          const { data } = res;
          this.pagination.count = data.total;
          this.templateList = data.list;
        })
        .catch(err => {
          console.warn(err);
        })
        .finally(() => {
          this.isTableLoading = false;
        });
    },
    operateHandler(row, operateType) {
      if (operateType === 'edit') {
        this.$router.push({
          name: 'clean-template-edit',
          params: {
            templateId: row.clean_template_id,
          },
          query: {
            spaceUid: this.$store.state.spaceUid,
            editName: row.name,
          },
        });
        return;
      }
      if (operateType === 'delete') {
        this.$bkInfo({
          type: 'warning',
          subTitle: this.$t('当前模板名称为{n}，确认要删除？', { n: row.name }),
          confirmFn: () => {
            this.requestDeleteTemp(row);
          },
        });
        return;
      }
    },
    requestDeleteTemp(row) {
      this.$http
        .request('clean/deleteTemplate', {
          params: {
            clean_template_id: row.clean_template_id,
          },
          data: {
            bk_biz_id: this.bkBizId,
          },
        })
        .then(res => {
          if (res.result) {
            const page =
              this.templateList.length <= 1
                ? this.pagination.current > 1
                  ? this.pagination.current - 1
                  : 1
                : this.pagination.current;
            this.messageSuccess(this.$t('删除成功'));
            if (page !== this.pagination.current) {
              this.handlePageChange(page);
            } else {
              this.requestData();
            }
          }
        })
        .catch(() => {});
    },
    getFormatName(row) {
      const cleantype = row.clean_type;
      const matchItem = this.globalsData.etl_config.find(conf => {
        return conf.id === cleantype;
      });
      return matchItem ? matchItem.name : '';
    },
    handleSearchChange(val) {
      if (val === '' && !this.isTableLoading) {
        this.search();
      }
    },
    handleOperation(type) {
      if (type === 'clear-filter') {
        this.params.keyword = '';
        clearTableFilter(this.$refs.cleanTable);
        this.search();
        return;
      }

      if (type === 'refresh') {
        this.emptyType = 'empty';
        this.search();
        return;
      }
    },
  },
};
</script>

<style lang="scss">
  @import '@/scss/mixins/clearfix';
  @import '@/scss/conf';
  @import '@/scss/devops-common.scss';

  .clean-template-container {
    padding: 20px 24px;

    .top-operation {
      margin-bottom: 20px;

      @include clearfix;

      .bk-button {
        width: 120px;
      }
    }

    .clean-search {
      width: 360px;
    }

    .clean-table {
      overflow: visible;

      .text-disabled {
        color: #c4c6cc;
      }

      .text-active {
        color: #3a84ff;
        cursor: pointer;
      }

      .filter-column {
        .cell {
          display: flex;
        }
      }
    }
  }
</style>
