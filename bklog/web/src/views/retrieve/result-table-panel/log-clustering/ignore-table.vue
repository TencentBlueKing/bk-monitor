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
  <bk-table
    ref="logClusterTable"
    :class="['log-cluster-table', tableData.length === 0 ? 'ignore-no-data' : '']"
    :data="tableData"
    :outer-border="false"
    data-test-id="cluster_div_ignoreTable"
    @row-click="tableRowClick"
  >
    <bk-table-column
      width="30"
      type="expand"
    >
      <template #default="props">
        <expand-view
          v-bind="$attrs"
          :data="props.row.originSample"
          :list-data="props.row.sample"
          :total-fields="totalFields"
          :visible-fields="visibleFields"
          @menu-click="handleMenuClick"
        />
      </template>
    </bk-table-column>
    <bk-table-column
      :label="$t('序号')"
      :render-header="$renderHeader"
      :width="getTableWidth.index"
      type="index"
    >
    </bk-table-column>
    <bk-table-column
      :label="$t('数量')"
      :render-header="$renderHeader"
      :width="getTableWidth.count"
      prop="count"
      sortable
    >
    </bk-table-column>
    <bk-table-column
      :label="$t('占比')"
      :render-header="$renderHeader"
      :sort-by="'count'"
      :width="getTableWidth.source"
      prop="source"
      sortable
    >
      <template #default="props">
        {{ computedRate(props.row.count) }}
      </template>
    </bk-table-column>
    <bk-table-column
      :label="$t('取样内容')"
      :render-header="$renderHeader"
      class-name="symbol-column"
      prop="content"
    >
      <!-- eslint-disable-next-line -->
      <template slot-scope="{ row, column, $index }">
        <div :class="['symbol-content', { 'is-limit': getLimitState($index) }]">
          <span>{{ row.content }}</span>
          <template v-if="!isLimitExpandView">
            <p
              v-if="!cacheExpandStr.includes($index)"
              class="show-whole-btn"
              @click.stop="handleShowWhole($index)"
            >
              {{ $t('展开全部') }}
            </p>
            <p
              v-else
              class="hide-whole-btn"
              @click.stop="handleHideWhole($index)"
            >
              {{ $t('收起') }}
            </p>
          </template>
        </div>
      </template>
    </bk-table-column>
    <template #empty>
      <div>
        <empty-status empty-type="empty" />
      </div>
    </template>
  </bk-table>
</template>

<script>
  import { copyMessage } from '@/common/util';
  import EmptyStatus from '@/components/empty-status';
  import ExpandView from '../original-log/expand-view.vue';
  import { mapGetters } from 'vuex';

  export default {
    components: {
      ExpandView,
      EmptyStatus,
    },
    inheritAttrs: false,
    props: {
      active: {
        type: String,
        required: true,
      },
      clusteringField: {
        type: String,
        default: '',
      },
      originTableList: {
        type: Array,
        required: true,
      },
      tableList: {
        type: Array,
        required: true,
      },
      visibleFields: {
        type: Array,
        required: true,
      },
      totalFields: {
        type: Array,
        required: true,
      },
    },
    data() {
      return {
        tableData: [],
        cacheExpandStr: [],
        ignoreNumberReg: /(\d{1,})|([1-9]\d+)/g,
        ignoreSymbolReg: /(\d{1,})|([-`.!@#$%^&*(){}<>[\]_+=":;,\\/\d]+)/g,
        enTableWidth: {
          index: '80',
          count: '105',
          source: '115',
        },
        cnTableWidth: {
          index: '60',
          count: '91',
          source: '91',
        },
      };
    },
    computed: {
      getTableWidth() {
        return this.$store.getters.isEnLanguage ? this.enTableWidth : this.cnTableWidth;
      },
      ...mapGetters({
        isLimitExpandView: 'isLimitExpandView',
      }),
    },
    watch: {
      active() {
        this.setTableData();
      },
      tableList: {
        immediate: true,
        handler() {
          this.setTableData();
        },
      },
    },
    methods: {
      setTableData() {
        if (!this.clusteringField) return;

        this.tableData = (this.tableList || []).reduce((pre, next, index) => {
          const regExp = this.active === 'ignoreNumbers' ? this.ignoreNumberReg : this.ignoreSymbolReg;
          const sampleField = next[this.clusteringField];
          const valStr = sampleField
            .toString()
            .replace(/<mark>/g, '')
            .replace(/<\/mark>/g, '')
            .replace(regExp, '*')
            .replace(/\*(\s|\*)+/g, '*');
          const ascription = pre.find(item => item.content === valStr);
          if (!ascription) {
            pre.push({
              count: 1,
              content: valStr,
              sample: next,
              originSample: this.originTableList[index],
            });
          } else {
            ascription.count = ascription.count + 1;
          }
          return pre;
        }, []);
      },
      computedRate(count) {
        return `${((count / this.tableList.length) * 100).toFixed(2)}%`;
      },
      tableRowClick(row) {
        this.$refs.logClusterTable.toggleRowExpansion(row);
      },
      handleShowWhole(index) {
        this.cacheExpandStr.push(index);
      },
      handleHideWhole(index) {
        this.cacheExpandStr = this.cacheExpandStr.map(item => item !== index);
      },
      handleMenuClick(option) {
        switch (option.operation) {
          case 'is':
          case 'is not':
            const { fieldName, operation, value } = option;
            this.$emit('add-filter-condition', fieldName, operation, value === '--' ? '' : value.toString());
            break;
          case 'copy':
            copyMessage(option.value);
            break;
          case 'display':
            this.$emit('fields-updated', option.displayFieldNames);
            break;
          default:
            break;
        }
      },
      getLimitState(index) {
        if (this.isLimitExpandView) return false;
        return !this.cacheExpandStr.includes(index);
      },
    },
  };
</script>

<style lang="scss">
  /* stylelint-disable no-descending-specificity */
  .log-cluster-table {
    font-family: var(--table-fount-family);
    font-size: var(--table-fount-size);
    color: var(--table-fount-color);

    .bk-table-body td.bk-table-expanded-cell {
      padding: 0;
    }

    &:before {
      display: none;
    }

    td {
      padding-top: 14px;
      vertical-align: top;
    }

    td.symbol-column {
      padding: 10px 0px;
    }

    .bk-table-body-wrapper {
      min-height: calc(100vh - 550px);

      .bk-table-empty-block {
        min-height: calc(100vh - 550px);
      }
    }

    .symbol-content {
      position: relative;
      display: inline-block;
      padding-right: 15px;
      overflow: hidden;
      font-family: var(--table-fount-family);
      font-size: var(--table-fount-size);
      line-height: 20px;
      color: var(--table-fount-color);

      &.is-limit {
        max-height: 96px;
      }
    }

    .hover-row {
      .show-whole-btn {
        background-color: #f5f7fa;
      }
    }

    .show-whole-btn {
      position: absolute;
      top: 80px;
      width: 100%;
      height: 24px;
      font-size: 12px;
      color: #3a84ff;
      cursor: pointer;
      background: #fff;
      transition: background-color 0.25s ease;
    }

    .hide-whole-btn {
      margin-top: 2px;
      line-height: 14px;
      color: #3a84ff;
      cursor: pointer;
    }

    .bk-table-column-expand {
      padding-top: 0;

      .bk-icon {
        top: 20px;
      }
    }

    :deep(.bk-table-body-wrapper) {
      min-height: calc(100vh - 541px);

      .bk-table-empty-block {
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: calc(100vh - 540px);
      }
    }

    .empty-text {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: space-between;

      .empty-leave {
        margin-top: 8px;
        color: #3a84ff;
        cursor: pointer;
      }
    }
  }

  .ignore-no-data {
    tr {
      > th {
        /* stylelint-disable-next-line declaration-no-important */
        border-bottom: none !important;
      }
    }
  }
</style>
