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
  <div class="expand-view-wrapper">
    <div class="view-tab">
      <div class="tab-left">
        <span
          :class="{ activeKv: activeExpandView === 'kv' }"
          @click="activeExpandView = 'kv'"
        >
          KV
        </span>
        <span
          :class="{ activeJson: activeExpandView === 'json' }"
          @click="activeExpandView = 'json'"
        >
          JSON
        </span>
      </div>
      <div class="tab-right">
        <bk-input
          v-show="activeExpandView === 'kv'"
          v-model="searchKeyword"
          ext-cls="search-input"
          clearable
          :placeholder="$t('搜索字段')"
          :right-icon="'bk-icon icon-search'"
          @enter="handleSearch"
          @right-icon-click="handleSearch"
          @clear="handleClearSearch"
          @input="handleInputChange"
          >
        </bk-input>
        <span
          class="bklog-icon bklog-data-copy"
          v-bk-tooltips="{ content: $t('复制') }"
          @click="handleCopy"
        ></span>
      </div>
    </div>
    <div
      class="view-content kv-view-content"
      v-if="activeExpandView === 'kv' && rawRowData"
    >
      <kv-list
        :data="rawRowData"
        :field-list="totalFields"
        :kv-show-fields-list="kvShowFieldsList"
        :list-data="rawRowData"
        :total-fields="totalFields"
        :visible-fields="visibleFields"
        :search-keyword="activeSearchKeyword"
        @value-click="
          (type, content, isLink, field, depth) => $emit('value-click', type, content, isLink, field, depth)
        "
      />
    </div>
    <div
      style="padding: 2px 12px 10px 39px"
      class="view-content json-view-content"
      v-if="activeExpandView === 'json'"
    >
      <JsonFormatWrapper
        :data="jsonShowData"
        :deep="5"
      />
    </div>
  </div>
</template>

<script>
  import { TABLE_LOG_FIELDS_SORT_REGULAR, copyMessage } from '@/common/util';
  import { getFieldNameByField } from '@/hooks/use-field-name';
  import tableRowDeepViewMixin from '@/mixins/table-row-deep-view-mixin';
  import { perfMeasure, perfStart, perfEnd } from '@/utils/performance-monitor';

  import KvList from '../../result-comp/kv-list.vue';

  export default {
    components: {
      KvList,
    },
    mixins: [tableRowDeepViewMixin],
    inheritAttrs: false,
    props: {
      data: {
        type: Object,
        default: () => {},
      },
      listData: {
        type: Object,
        default: () => {},
      },
      kvShowFieldsList: {
        type: Array,
        require: true,
      },
      rowIndex: {
        type: Number,
      },
    },
    data() {
      return {
        activeExpandView: 'kv',
        searchKeyword: '',
        activeSearchKeyword: '',
        rawRowData: null, // 非响应式数据副本
        jsonShowDataCache: null, // JSON 数据缓存
      };
    },
    computed: {
      visibleFields() {
        return this.$store.getters.visibleFields ?? [];
      },
      totalFields() {
        return this.$store.state.indexFieldInfo.fields ?? [];
      },
      // 性能优化：使用 Set 缓存 kvShowFieldsList，提升查找性能
      kvShowFieldsSet() {
        return new Set(this.kvShowFieldsList);
      },
      kvListData() {
        // 性能监控：记录过滤和排序耗时
        return perfMeasure('expand-view:kvListData', () => {
          const kvShowFieldsSet = this.kvShowFieldsSet;
          const totalFields = this.totalFields;
          
          // 性能优化：使用 for 循环替代 filter，减少函数调用开销
          const filteredFields = [];
          for (let i = 0; i < totalFields.length; i++) {
            if (kvShowFieldsSet.has(totalFields[i].field_name)) {
              filteredFields.push(totalFields[i]);
            }
          }
          
          // 性能优化：缓存字段名称，避免重复调用 getFieldNameByField
          const fieldNameCache = new Map();
          const getCachedFieldName = (field) => {
            if (!fieldNameCache.has(field)) {
              fieldNameCache.set(field, getFieldNameByField(field, this.$store));
            }
            return fieldNameCache.get(field);
          };
          
          // 性能优化：预计算排序键，避免在排序时重复计算
          const sortKeys = filteredFields.map(field => ({
            field,
            sortKey: getCachedFieldName(field).replace(TABLE_LOG_FIELDS_SORT_REGULAR, 'z'),
          }));
          
          sortKeys.sort((a, b) => a.sortKey.localeCompare(b.sortKey));
          
          return sortKeys.map(item => item.field);
        }, {
          fieldCount: this.totalFields.length,
          kvShowFieldsCount: this.kvShowFieldsList.length,
        });
      },
      jsonList() {
        if (this.rowIndex === undefined) {
          return this.listData ?? this.data;
        }

        return this.$store.state.indexSetQueryResult?.origin_log_list?.[this.rowIndex] ?? this.listData ?? this.data;
      },
      jsonShowData() {
        // 如果已有缓存，直接返回缓存（避免重复计算）
        if (this.jsonShowDataCache !== null) {
          return this.jsonShowDataCache;
        }

        // 性能监控：记录 jsonShowData 计算耗时
        const result = perfMeasure('expand-view:jsonShowData', () => {
          const kvListData = this.kvListData;
          const jsonList = this.jsonList;
          const computedResult = {};
          
          // 性能优化：缓存字段名称，避免重复调用 getFieldNameByField
          const fieldNameCache = new Map();
          const getCachedFieldName = (field) => {
            if (!fieldNameCache.has(field)) {
              fieldNameCache.set(field, getFieldNameByField(field, this.$store));
            }
            return fieldNameCache.get(field);
          };
          
          // 性能优化：对于简单字段（没有嵌套的），直接访问，避免调用 parseTableRowData
          // 这样可以显著减少函数调用开销
          const totalFields = kvListData.length;
          
          for (let i = 0; i < totalFields; i++) {
            const cur = kvListData[i];
            const fieldName = getCachedFieldName(cur);
            const fieldKey = cur.field_name;
            
            // 性能优化：简单字段直接访问，复杂字段才调用 tableRowDeepView
            if (fieldKey.indexOf('.') === -1 && fieldKey.indexOf('[') === -1) {
              // 简单字段：直接访问
              let value = jsonList[fieldKey];
              
              // 处理空值
              if (value === null || value === undefined || value === '') {
                value = '--';
              } else if (typeof value === 'object') {
                // 对象需要序列化
                value = JSON.stringify(value);
              }
              
              computedResult[fieldName] = value;
            } else {
              // 复杂字段（嵌套字段）：使用 tableRowDeepView
              computedResult[fieldName] = this.tableRowDeepView(jsonList, fieldKey, cur.field_type) ?? '';
            }
          }
          
          return computedResult;
        }, {
          fieldCount: this.kvListData.length,
        });

        // 缓存结果，使用 Object.freeze 创建非响应式副本
        this.jsonShowDataCache = Object.freeze(JSON.parse(JSON.stringify(result)));
        return this.jsonShowDataCache;
      },
    },
    methods: {
      handleCopy() {
        copyMessage(JSON.stringify(this.jsonShowData));
      },
      handleSearch() {
        this.activeSearchKeyword = this.searchKeyword.trim();
      },
      handleClearSearch() {
        this.searchKeyword = '';
        this.activeSearchKeyword = '';
      },
      handleInputChange(value) {
        // 当输入框内容被手动删空时，重置搜索
        if (!value || !value.trim()) {
          this.activeSearchKeyword = '';
        }
      },
    },
    mounted() {
      // 立即创建非响应式数据副本，确保 kv-list 可以立即渲染骨架屏
      // 使用浅拷贝 + Object.freeze 创建非响应式数据副本
      // 防止整行日志对象进入 Vue2 深度响应式系统
      this.rawRowData = Object.freeze({ ...this.data });
    },
    watch: {
      // 监听数据变化，清空缓存
      data: {
        handler() {
          this.jsonShowDataCache = null;
        },
        deep: false, // 禁止深度监听，避免性能问题
      },
      // 监听视图切换，清空 JSON 缓存（如果需要）
      activeExpandView(newVal) {
        if (newVal === 'json' && this.jsonShowDataCache === null) {
          // 切换到 JSON 视图时，如果缓存为空，触发计算
          // computed 会自动计算
        }
      },
    },
  };
</script>

<style lang="scss" scoped>
  .expand-view-wrapper {
    width: 100%;
    color: #313238;
    background-color: #f5f7fa;

    .view-tab {
      display: flex;
      justify-content: space-between;
      padding-right: 15px;
      font-size: 0;
      background-color: #f5f7fa;

      .tab-left {
        span {
          display: inline-block;
          width: 46px;
          height: 23px;
          font-size: 12px;
          line-height: 23px;
          color: #313238;
          text-align: center;
          cursor: pointer;

          border-top: 0;

          &:first-child {
            border-left: 0;
          }

          &.activeKv,
          &.activeJson {
            position: relative;
            font-size: 12px;
            font-weight: 700;
          }

          &.activeKv::after {
            position: absolute;
            top: -2px; /* 确保线条在元素的上方 */
            left: 14px;
            width: 17px;
            height: 2px;
            content: ''; /* 必须有content属性，即使为空 */
            background-color: #313238; /* 红色横线 */
          }

          &.activeJson::after {
            position: absolute;
            top: -2px; /* 确保线条在元素的上方 */
            left: 10px;
            width: 30px;
            height: 2px;
            content: ''; /* 必须有content属性，即使为空 */
            background-color: #313238; /* 红色横线 */
          }
        }
      }

      .tab-right {
        position: sticky;
        right: 20px;
        display: flex;
        align-items: center;

        .search-input {
            margin-right: 10px;

            :deep(.bk-form-input) {
              width: 200px;
              height: 22px;
              background: #F5F7FA;
              padding: 0;
              border: none;
              border-bottom: 1px solid #c4c6cc;

              &:focus {
                background: #F5F7FA !important;
              }
            }

            :deep(.right-icon) {
              right: 0px !important;
            }
          }

        .bklog-icon {
          font-size: 16px;
          color: #63656e;
          cursor: pointer;

          &:hover {
            color: #3a84ff;
          }
        }
      }
    }

    .view-content {
      padding: 2px 15px 14px 15px;
      background-color: #f5f7fa;

      :deep(.vjs-tree) {
        /* stylelint-disable-next-line declaration-no-important */
        font-size: var(--table-fount-size) !important;

        .vjs-tree-node {
          line-height: 22px;
          .vjs-value {
            &.vjs-value-string {
              white-space: pre-wrap;
            }
          }
        }
      }

      :deep(.kv-content) {
        .bklog-text-segment {
          &.bklog-root-field {
            max-height: fit-content;
          }
        }
      }
    }
  }
</style>
<style lang="scss">
  .json-view-content {
    .vjs-tree-brackets,
    .vjs-key {
      /* stylelint-disable-next-line declaration-no-important */
      color: #9d694c !important;
    }

    .vjs-value-string {
      color: #357a94;
    }

    .vjs-value-number {
      color: #2caf5e;
    }

    .vjs-indent-unit.has-line {
      border-left: 1px solid #bfcbd9;
    }
  }
</style>
