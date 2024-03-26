/*
 * Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 * BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
 *
 * License for BK-LOG 蓝鲸日志平台:
 * --------------------------------------------------------------------
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
 * and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all copies or substantial
 * portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
 * LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
 * NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
 * WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
 */

import { mapState } from 'vuex';
import { formatDate, random, copyMessage, setDefaultTableWidth, TABLE_LOG_FIELDS_SORT_REGULAR } from '@/common/util';
import tableRowDeepViewMixin from '@/mixins/table-row-deep-view-mixin';
import TextHighlight from 'vue-text-highlight';
import OperatorTools from '@/views/retrieve/result-table-panel/original-log/operator-tools';
import RetrieveLoader from '@/skeleton/retrieve-loader';
import TableColumn from '@/views/retrieve/result-comp/table-column';
import ExpandView from '@/views/retrieve/result-table-panel/original-log/expand-view.vue';
import EmptyView from '@/views/retrieve/result-table-panel/original-log/empty-view';
import TimeFormatterSwitcher from '@/views/retrieve/result-table-panel/original-log/time-formatter-switcher';
import OriginalLightHeight from '@/views/retrieve/result-comp/original-light-height.tsx';

export default {
  components: {
    TextHighlight,
    OperatorTools,
    RetrieveLoader,
    TableColumn,
    ExpandView,
    EmptyView,
    TimeFormatterSwitcher,
    OriginalLightHeight
  },
  mixins: [tableRowDeepViewMixin],
  props: {
    tableList: {
      type: Array,
      required: true
    },
    originTableList: {
      type: Array,
      required: true
    },
    totalFields: {
      type: Array,
      required: true
    },
    visibleFields: {
      type: Array,
      required: true
    },
    showFieldAlias: {
      type: Boolean,
      default: false
    },
    fieldAliasMap: {
      type: Object,
      default: () => {}
    },
    isWrap: {
      type: Boolean,
      default: false
    },
    retrieveParams: {
      type: Object,
      required: true
    },
    tableLoading: {
      type: Boolean,
      required: true
    },
    isPageOver: {
      type: Boolean,
      required: false
    },
    timeField: {
      type: String,
      default: ''
    },
    operatorConfig: {
      type: Object,
      required: true
    },
    handleClickTools: Function
  },
  data() {
    return {
      formatDate,
      cacheExpandStr: [], // 记录展开收起的行
      cacheOverFlowCol: [], // 记录超出四行高度的列
      tableRandomKey: '',
      /** 原始日志复制弹窗实例 */
      originStrInstance: null,
      /** 当前需要复制的原始日志 */
      hoverOriginStr: ''
    };
  },
  computed: {
    ...mapState('globals', ['fieldTypeMap']),
    ...mapState(['isNotVisibleFieldsShow', 'clearTableWidth']),
    showHandleOption() {
      return Boolean(this.tableList.length);
    },
    getOperatorToolsWidth() {
      return this.operatorConfig?.bcsWebConsole?.is_active ? '84' : '58';
    },
    getShowTableVisibleFields() {
      this.tableRandomKey = random(6);
      return this.isNotVisibleFieldsShow ? this.fullQuantityFields : this.visibleFields;
    },
    /** 清空所有字段后所展示的默认字段  顺序: 时间字段，log字段，索引字段 */
    fullQuantityFields() {
      const dataFields = [];
      const indexSetFields = [];
      const logFields = [];
      this.totalFields.forEach(item => {
        if (item.field_type === 'date') {
          dataFields.push(item);
        } else if (item.field_name === 'log' || item.field_alias === 'original_text') {
          logFields.push(item);
        } else if (!(item.field_type === '__virtual__' || item.is_built_in)) {
          indexSetFields.push(item);
        }
      });
      const sortIndexSetFieldsList = indexSetFields.sort((a, b) => {
        const sortA = a.field_name.replace(TABLE_LOG_FIELDS_SORT_REGULAR, 'z');
        const sortB = b.field_name.replace(TABLE_LOG_FIELDS_SORT_REGULAR, 'z');
        return sortA.localeCompare(sortB);
      });
      const sortFieldsList = [...dataFields, ...logFields, ...sortIndexSetFieldsList];
      setDefaultTableWidth(sortFieldsList, this.tableList);
      return sortFieldsList;
    }
  },
  watch: {
    retrieveParams: {
      deep: true,
      handler() {
        this.cacheExpandStr = [];
        this.cacheOverFlowCol = [];
      }
    },
    '$route.params.indexId'() {
      // 切换索引集重置状态
      this.cacheExpandStr = [];
      this.cacheOverFlowCol = [];
    },
    clearTableWidth() {
      const columnObj = JSON.parse(localStorage.getItem('table_column_width_obj'));
      const {
        params: { indexId },
        query: { bizId }
      } = this.$route;
      if (columnObj === null || JSON.stringify(columnObj) === '{}') {
        return;
      }
      const isHaveBizId = Object.keys(columnObj).some(el => el === bizId);

      if (!isHaveBizId || columnObj[bizId].fields[indexId] === undefined) {
        return;
      }

      for (const bizKey in columnObj) {
        if (bizKey === bizId) {
          for (const fieldKey in columnObj[bizKey].fields) {
            if (fieldKey === indexId) {
              delete columnObj[bizId].fields[indexId];
              columnObj[bizId].indexsetIds.splice(columnObj[bizId].indexsetIds.indexOf(indexId, 1));
              columnObj[bizId].indexsetIds.length === 0 && delete columnObj[bizId];
            }
          }
        }
      }

      localStorage.setItem('table_column_width_obj', JSON.stringify(columnObj));
    }
  },
  methods: {
    handleShowWhole(index) {
      this.cacheExpandStr.push(index);
    },
    handleHideWhole(index) {
      this.cacheExpandStr = this.cacheExpandStr.map(item => item !== index);
    },
    handleOverColumn(fieldName) {
      if (!this.cacheOverFlowCol.includes(fieldName)) this.cacheOverFlowCol.push(fieldName);
    },
    getMarkList(content) {
      // 匹配高亮标签
      let markList = [];

      const markVal = content.match(/(<mark>).*?(<\/mark>)/g) || [];
      if (markVal.length) {
        markList = markVal.map(item => item.replace(/<mark>/g, '').replace(/<\/mark>/g, ''));
      }

      return markList;
    },
    formatterStr(content) {
      // 匹配高亮标签
      let value = content;

      const markVal = content.match(/(<mark>).*?(<\/mark>)/g) || [];
      if (markVal.length) {
        value = String(value)
          .replace(/<mark>/g, '')
          .replace(/<\/mark>/g, '');
      }

      return value;
    },
    // 展开表格行JSON
    tableRowClick(row, option, column) {
      if (column.className && column.className.includes('original-str')) return;
      const ele = this.$refs.resultTable;
      ele.toggleRowExpansion(row);
    },
    handleHeaderDragend(newWidth, oldWidth, { index }) {
      const {
        params: { indexId },
        query: { bizId }
      } = this.$route;
      if (index === undefined || bizId === undefined || indexId === undefined) {
        return;
      }
      // 缓存其余的宽度
      const widthObj = {};
      widthObj[index] = Math.ceil(newWidth);

      let columnObj = JSON.parse(localStorage.getItem('table_column_width_obj'));
      if (columnObj === null) {
        columnObj = {};
        columnObj[bizId] = this.initSubsetObj(bizId, indexId);
      }
      const isIncludebizId = Object.keys(columnObj).some(el => el === bizId);
      isIncludebizId === false && (columnObj[bizId] = this.initSubsetObj(bizId, indexId));

      for (const key in columnObj) {
        if (key === bizId) {
          if (columnObj[bizId].fields[indexId] === undefined) {
            columnObj[bizId].fields[indexId] = {};
            columnObj[bizId].indexsetIds.push(indexId);
          }
          columnObj[bizId].fields[indexId] = Object.assign(columnObj[bizId].fields[indexId], widthObj);
        }
      }

      localStorage.setItem('table_column_width_obj', JSON.stringify(columnObj));
    },
    initSubsetObj(bizId, indexId) {
      const subsetObj = {};
      subsetObj.bizId = bizId;
      subsetObj.indexsetIds = [indexId];
      subsetObj.fields = {};
      subsetObj.fields[indexId] = {};
      return subsetObj;
    },
    // eslint-disable-next-line no-unused-vars
    renderHeaderAliasName(h, { column, $index }) {
      const field = this.getShowTableVisibleFields[$index - 1];
      const isShowSwitcher = field?.field_type === 'date';
      if (field) {
        const fieldName = this.showFieldAlias ? this.fieldAliasMap[field.field_name] : field.field_name;
        const fieldType = field.field_type;
        const fieldIcon = this.getFieldIcon(field.field_type);
        const content = this.fieldTypeMap[fieldType] ? this.fieldTypeMap[fieldType].name : undefined;

        return h(
          'div',
          {
            class: 'render-header'
          },
          [
            h('span', {
              class: `field-type-icon ${fieldIcon}`,
              style: {
                marginRight: '4px'
              },
              directives: [
                {
                  name: 'bk-tooltips',
                  value: content
                }
              ]
            }),
            h('span', { directives: [{ name: 'bk-overflow-tips' }], class: 'title-overflow' }, [fieldName]),
            h(TimeFormatterSwitcher, {
              class: 'timer-formatter',
              style: {
                display: isShowSwitcher ? 'inline-block' : 'none'
              }
            }),
            h('i', {
              class: `bk-icon icon-minus-circle-shape toggle-display ${this.isNotVisibleFieldsShow ? 'is-hidden' : ''}`,
              directives: [
                {
                  name: 'bk-tooltips',
                  value: this.$t('将字段从表格中移除')
                }
              ],
              on: {
                click: e => {
                  e.stopPropagation();
                  const displayFieldNames = [];
                  this.visibleFields.forEach(field => {
                    if (field.field_name !== fieldName) {
                      displayFieldNames.push(field.field_name);
                    }
                  });
                  this.$emit('fieldsUpdated', displayFieldNames, undefined, false);
                }
              }
            })
          ]
        );
      }
    },
    handleIconClick(type, content, field, row, isLink) {
      let value = field.field_type === 'date' ? row[field.field_name] : content;
      value = String(value)
        .replace(/<mark>/g, '')
        .replace(/<\/mark>/g, '');
      if (type === 'search') {
        // 将表格单元添加到过滤条件
        this.$emit('addFilterCondition', field.field_name, 'eq', value, isLink);
      } else if (type === 'copy') {
        // 复制单元格内容
        copyMessage(value);
      } else if (['is', 'is not'].includes(type)) {
        this.$emit('addFilterCondition', field.field_name, type, value === '--' ? '' : value.toString(), isLink);
      }
    },
    getFieldIcon(fieldType) {
      return this.fieldTypeMap[fieldType] ? this.fieldTypeMap[fieldType].icon : 'log-icon icon-unkown';
    },
    handleMenuClick(option, isLink) {
      switch (option.operation) {
        case 'is':
        case 'is not':
          // eslint-disable-next-line no-case-declarations
          const { fieldName, operation, value } = option;
          this.$emit('addFilterCondition', fieldName, operation, value === '--' ? '' : value.toString(), isLink);
          break;
        case 'copy':
          copyMessage(option.value);
          break;
        case 'display':
          this.$emit('fieldsUpdated', option.displayFieldNames, undefined, false);
          break;
        default:
          break;
      }
    },
    /**
     * @desc: 单条字段排序
     * @param {Object} column 字段信息
     * @param {String} order 排序
     */
    handleSortTable({ column, order }) {
      const sortMap = {
        ascending: 'asc',
        descending: 'desc'
      };
      const sortList = !!column ? [[column.columnKey, sortMap[order]]] : [];
      this.$emit('shouldRetrieve', { sort_list: sortList }, false);
    }
  }
};
