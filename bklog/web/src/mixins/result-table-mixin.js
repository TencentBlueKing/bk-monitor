/*
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
 */

import TextHighlight from 'vue-text-highlight';

import {
  formatDate,
  random,
  copyMessage,
  setDefaultTableWidth,
  TABLE_LOG_FIELDS_SORT_REGULAR,
  formatDateNanos,
} from '@/common/util';
import tableRowDeepViewMixin from '@/mixins/table-row-deep-view-mixin';
import RetrieveLoader from '@/skeleton/retrieve-loader';
import OriginalLightHeight from '@/views/retrieve/result-comp/original-light-height.tsx';
import TableColumn from '@/views/retrieve/result-comp/table-column';
import EmptyView from '@/views/retrieve/result-table-panel/original-log/empty-view';
import ExpandView from '@/views/retrieve/result-table-panel/original-log/expand-view.vue';
import OperatorTools from '@/views/retrieve/result-table-panel/original-log/operator-tools';
import TimeFormatterSwitcher from '@/views/retrieve/result-table-panel/original-log/time-formatter-switcher';
import { BK_LOG_STORAGE } from '@/store/store.type';
import { mapState, mapGetters } from 'vuex';

export default {
  components: {
    TextHighlight,
    OperatorTools,
    RetrieveLoader,
    TableColumn,
    ExpandView,
    EmptyView,
    TimeFormatterSwitcher,
    OriginalLightHeight,
  },
  mixins: [tableRowDeepViewMixin],
  props: {
    tableList: {
      type: Array,
      required: true,
    },
    originTableList: {
      type: Array,
      required: true,
    },
    totalFields: {
      type: Array,
      required: true,
    },
    visibleFields: {
      type: Array,
      required: true,
    },
    showFieldAlias: {
      type: Boolean,
      default: false,
    },
    fieldAliasMap: {
      type: Object,
      default: () => {},
    },
    isWrap: {
      type: Boolean,
      default: false,
    },
    retrieveParams: {
      type: Object,
      required: true,
    },
    tableLoading: {
      type: Boolean,
      required: true,
    },
    isPageOver: {
      type: Boolean,
      required: false,
    },
    timeField: {
      type: String,
      default: '',
    },
    operatorConfig: {
      type: Object,
      required: true,
    },
    handleClickTools: Function,
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
      hoverOriginStr: '',
      logSourceField: {
        description: null,
        es_doc_values: false,
        field_alias: '',
        field_name: this.$t('日志来源'),
        field_operator: [],
        field_type: 'keyword',
        filterExpand: false,
        filterVisible: false,
        is_analyzed: false,
        is_display: false,
        is_editable: false,
        minWidth: 0,
        tag: 'union-source',
        width: 230,
      },
    };
  },
  computed: {
    ...mapState('globals', ['fieldTypeMap']),
    ...mapState(['isNotVisibleFieldsShow']),
    ...mapGetters({
      isUnionSearch: 'isUnionSearch',
      unionIndexList: 'unionIndexList',
      unionIndexItemList: 'unionIndexItemList',
      isLimitExpandView: 'isLimitExpandView',
    }),
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
      if (this.isUnionSearch && this.isShowSourceField) {
        sortFieldsList.unshift(this.logSourceField);
      }
      setDefaultTableWidth(sortFieldsList, this.tableList);
      return sortFieldsList;
    },
    /** 是否展示数据来源 */
    isShowSourceField() {
      return this.operatorConfig?.isShowSourceField ?? false;
    },
    timeFieldType() {
      return this.totalFields.find(item => item.field_name === this.timeField)?.field_type;
    },
    originFieldWidth() {
      return this.timeFieldType === 'date_nanos' ? 210 : 174;
    },
    userSettingConfig() {
      return this.$store.state.retrieve.catchFieldCustomConfig;
    },
  },
  watch: {
    retrieveParams: {
      deep: true,
      handler() {
        this.cacheExpandStr = [];
        this.cacheOverFlowCol = [];
      },
    },
    '$route.params.indexId'() {
      // 切换索引集重置状态
      this.cacheExpandStr = [];
      this.cacheOverFlowCol = [];
    },
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
      if (column.className?.includes('original-str')) return;
      const ele = this.$refs.resultTable;
      ele.toggleRowExpansion(row);
    },
    handleHeaderDragend(newWidth, oldWidth, { columnKey }) {
      const { fieldsWidth } = this.userSettingConfig;
      const newFieldsWidthObj = Object.assign(fieldsWidth, {
        [columnKey]: Math.ceil(newWidth),
      });
      this.$store.dispatch('userFieldConfigChange', {
        fieldsWidth: newFieldsWidthObj,
      });
    },
    initSubsetObj(bizId, indexKey) {
      const subsetObj = {};
      subsetObj.bizId = bizId;
      subsetObj.indexsetIds = [indexKey];
      subsetObj.fields = {};
      subsetObj.fields[indexKey] = {};
      return subsetObj;
    },

    renderHeaderAliasName(h, { _column, $index }) {
      const field = this.getShowTableVisibleFields[$index - 1];
      const isShowSwitcher = ['date', 'date_nanos'].includes(field?.field_type);
      if (field) {
        const fieldName = this[BK_LOG_STORAGE.SHOW_FIELD_ALIAS]
          ? this.fieldAliasMap[field.field_name]
          : field.field_name;
        const fieldType = field.field_type;
        const isUnionSource = field?.tag === 'union-source';
        const fieldIcon = this.getFieldIcon(field.field_type);
        const content = this.fieldTypeMap[fieldType] ? this.fieldTypeMap[fieldType].name : undefined;
        let unionContent = '';
        // 联合查询判断字段来源 若indexSetIDs缺少已检索的索引集内容 则增加字段来源判断
        if (this.isUnionSearch) {
          const indexSetIDs = field.index_set_ids?.map(item => String(item)) || [];
          const isDifferentFields = indexSetIDs.length !== this.unionIndexItemList.length;
          if (isDifferentFields && !isUnionSource) {
            const lackIndexNameList = this.unionIndexItemList
              .filter(item => indexSetIDs.includes(item.index_set_id))
              .map(item => item.index_set_name);
            unionContent = `${this.$t('字段来源')}: <br>${lackIndexNameList.join(' <br>')}`;
          }
        }
        const isLackIndexFields = !!unionContent && this.isUnionSearch;

        return h(
          'div',
          {
            class: 'render-header',
          },
          [
            h('span', {
              class: `field-type-icon ${fieldIcon}`,
              style: {
                marginRight: '4px',
              },
              directives: [
                {
                  name: 'bk-tooltips',
                  value: content,
                },
              ],
            }),
            h(
              'span',
              {
                directives: [
                  {
                    name: 'bk-tooltips',
                    value: { allowHTML: false, content: isLackIndexFields ? unionContent : fieldName },
                  },
                ],
                class: { 'lack-index-filed': isLackIndexFields },
              },
              [fieldName],
            ),
            h(TimeFormatterSwitcher, {
              class: 'timer-formatter',
              style: {
                display: isShowSwitcher ? 'inline-block' : 'none',
              },
            }),
            h('i', {
              class: `bk-icon icon-minus-circle-shape toggle-display ${this.isNotVisibleFieldsShow ? 'is-hidden' : ''}`,
              directives: [
                {
                  name: 'bk-tooltips',
                  value: this.$t('将字段从表格中移除'),
                },
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
                  this.$emit('fields-updated', displayFieldNames, undefined, false);
                },
              },
            }),
          ],
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
        this.$emit('add-filter-condition', field.field_name, 'eq', [value], isLink);
      } else if (type === 'copy') {
        // 复制单元格内容
        copyMessage(value);
      } else if (['is', 'is not'].includes(type)) {
        this.$emit('add-filter-condition', field.field_name, type, value === '--' ? [] : [value], isLink);
      }
    },
    getFieldIcon(fieldType) {
      return this.fieldTypeMap[fieldType] ? this.fieldTypeMap[fieldType].icon : 'bklog-icon bklog-unkown';
    },
    handleMenuClick(option, isLink) {
      switch (option.operation) {
        case 'is':
        case 'is not':
          const { fieldName, operation, value } = option;
          this.$emit('add-filter-condition', fieldName, operation, value === '--' ? [] : [value], isLink);
          break;
        case 'copy':
          copyMessage(option.value);
          break;
        case 'display':
          this.$emit('fields-updated', option.displayFieldNames, undefined, false);
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
        descending: 'desc',
      };
      const sortList = !!column ? [[column.columnKey, sortMap[order]]] : [];
      this.$emit('should-retrieve', { sort_list: sortList }, false);
    },
    getTableColumnContent(row, field) {
      // 日志来源 展示来源的索引集名称
      if (field?.tag === 'union-source') {
        return (
          this.unionIndexItemList.find(item => item.index_set_id === String(row.__index_set_id__))?.index_set_name ?? ''
        );
      }
      return this.tableRowDeepView(row, field.field_name, field.field_type);
    },
    getLimitState(index) {
      if (this[BK_LOG_STORAGE.IS_LIMIT_EXPAND_VIEW]) return false;
      return !this.cacheExpandStr.includes(index);
    },
    getOriginTimeShow(data) {
      if (this.timeFieldType === 'date') {
        return formatDate(Number(data)) || data;
      }

      // 处理纳秒精度的UTC时间格式
      if (this.timeFieldType === 'date_nanos') {
        return formatDateNanos(data);
      }

      return data;
    },
  },
};
