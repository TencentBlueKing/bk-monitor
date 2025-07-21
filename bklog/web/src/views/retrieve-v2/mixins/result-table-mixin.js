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

import {
  formatDate,
  random,
  copyMessage,
  TABLE_LOG_FIELDS_SORT_REGULAR,
  formatDateNanos,
} from '@/common/util';
import LazyRender from '@/global/lazy-render.vue';
import useFieldNameHook from '@/hooks/use-field-name';
import tableRowDeepViewMixin from '@/mixins/table-row-deep-view-mixin';
import RetrieveLoader from '@/skeleton/retrieve-loader';
import { RetrieveUrlResolver } from '@/store/url-resolver';
import TextHighlight from 'vue-text-highlight';
import { mapState, mapGetters } from 'vuex';

import { BK_LOG_STORAGE } from '../../../store/store.type';
import EmptyView from '../components/result-cell-element/empty-view.ts';
import OperatorTools from '../components/result-cell-element/operator-tools.ts';
import TimeFormatterSwitcher from '../components/result-cell-element/time-formatter-switcher.tsx';
import OriginalLightHeight from '../result-comp/original-light-height.tsx';
import TableColumn from '../result-comp/table-column';
import { getConditionRouterParams } from '../search-result-panel/panel-util';
import ExpandView from '../search-result-panel/result-cell-element/expand-view.vue';

export default {
  components: {
    EmptyView,
    ExpandView,
    LazyRender,
    OperatorTools,
    OriginalLightHeight,
    RetrieveLoader,
    TableColumn,
    TextHighlight,
    TimeFormatterSwitcher,
  },
  computed: {
    ...mapState('globals', ['fieldTypeMap']),
    ...mapState([
      'isNotVisibleFieldsShow',
      'indexSetQueryResult',
      {
        tableLineIsWrap: (state) =>
          state.storage[BK_LOG_STORAGE.TABLE_LINE_IS_WRAP],
      },
      'indexSetOperatorConfig',
      'indexFieldInfo',
      'indexItem',
      'tableShowRowIndex',
      'tableJsonFormat',
    ]),
    ...mapGetters({
      isLimitExpandView: 'isLimitExpandView',
      isUnionSearch: 'isUnionSearch',
      unionIndexItemList: 'unionIndexItemList',
      unionIndexList: 'unionIndexList',
    }),
    apmRelation() {
      return this.$store.state.indexSetFieldConfig.apm_relation;
    },
    fieldAliasMap() {
      return (this.indexFieldInfo.fields ?? []).reduce(
        (out, field) => ({
          ...out,
          [field.field_name]: field.field_alias || field.field_name,
        }),
        {}
      );
    },
    /** 清空所有字段后所展示的默认字段  顺序: 时间字段，log字段，索引字段 */
    fullQuantityFields() {
      const dataFields = [];
      const indexSetFields = [];
      const logFields = [];
      this.totalFields.forEach((item) => {
        if (item.field_type === 'date') {
          dataFields.push(item);
        } else if (
          item.field_name === 'log' ||
          item.field_alias === 'original_text'
        ) {
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
      const sortFieldsList = [
        ...dataFields,
        ...logFields,
        ...sortIndexSetFieldsList,
      ];
      if (this.isUnionSearch && this.isShowSourceField) {
        sortFieldsList.unshift(this.logSourceField);
      }

      this.$store.commit(
        'updateVisibleFieldMinWidth',
        this.tableList,
        sortFieldsList
      );
      setDefaultTableWidth(sortFieldsList, this.tableList);
      return sortFieldsList;
    },
    getOperatorToolsWidth() {
      return this.operatorConfig?.bcsWebConsole?.is_active ? '84' : '58';
    },
    getShowTableVisibleFields() {
      this.tableRandomKey = random(6);
      return this.isNotVisibleFieldsShow
        ? this.fullQuantityFields
        : this.visibleFields;
      // return [...(this[BK_LOG_STORAGE.TABLE_SHOW_ROW_INDEX] ? [{ field_name: '行号', __is_row_index: true }] : []), ...list]
    },
    indexSetId() {
      return window.__IS_MONITOR_COMPONENT__
        ? this.$route?.query?.indexId || this.$store.state.indexId
        : this.$route.params.indexId;
    },
    /** 是否展示数据来源 */
    isShowSourceField() {
      return this.operatorConfig?.isShowSourceField ?? false;
    },
    kvShowFieldsList() {
      return Object.keys(this.indexSetQueryResult?.fields ?? {}) || [];
    },
    operatorConfig() {
      return this.indexSetOperatorConfig;
    },
    originFieldWidth() {
      return this.timeFieldType === 'date_nanos' ? 210 : 174;
    },
    showHandleOption() {
      return Boolean(this.tableList.length);
    },
    timeFieldType() {
      return this.totalFields.find((item) => item.field_name === this.timeField)
        ?.field_type;
    },
    userSettingConfig() {
      return this.$store.state.retrieve.catchFieldCustomConfig;
    },
  },
  data() {
    return {
      cacheExpandStr: [], // 记录展开收起的行
      cacheOverFlowCol: [], // 记录超出四行高度的列
      formatDate,
      /** 当前需要复制的原始日志 */
      hoverOriginStr: '',
      lazyRoot: null,
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
      /** 原始日志复制弹窗实例 */
      originStrInstance: null,
      tableRandomKey: '',
    };
  },
  methods: {
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
    getFieldIcon(fieldType) {
      return this.fieldTypeMap[fieldType]
        ? this.fieldTypeMap[fieldType].icon
        : 'bklog-icon bklog-unkown';
    },
    getFieldIconColor(fieldType) {
      return this.fieldTypeMap?.[fieldType]
        ? this.fieldTypeMap?.[fieldType]?.color
        : '#EAEBF0';
    },
    getLimitState(index) {
      if (this[BK_LOG_STORAGE.IS_LIMIT_EXPAND_VIEW]) return false;
      return !this.cacheExpandStr.includes(index);
    },
    getMarkList(content) {
      // 匹配高亮标签
      let markList = [];

      const markVal = content.match(/(<mark>).*?(<\/mark>)/g) || [];
      if (markVal.length) {
        markList = markVal.map((item) =>
          item.replace(/<mark>/g, '').replace(/<\/mark>/g, '')
        );
      }

      return markList;
    },
    getOriginTimeShow(data) {
      if (this.timeFieldType === 'date') {
        return formatDate(Number(data)) || data;
      }
      // 处理纳秒精度的UTC时间格式
      if (this.timeFieldType === 'date_nanos') {
        return formatDateNanos(data, true, true);
      }
      return data;
    },
    getTableColumnContent(row, field) {
      // 日志来源 展示来源的索引集名称
      if (field?.tag === 'union-source') {
        return (
          this.unionIndexItemList.find(
            (item) => item.index_set_id === String(row.__index_set_id__)
          )?.index_set_name ?? ''
        );
      }
      return this.tableRowDeepView(row, field.field_name, field.field_type);
    },
    handleAddCondition(
      field,
      operator,
      value,
      isLink = false,
      depth = undefined
    ) {
      const router = this.$router;
      const route = this.$route;
      const store = this.$store;

      this.$store
        .dispatch('setQueryCondition', {
          depth,
          field,
          isLink,
          operator,
          value,
        })
        .then(([newSearchList, searchMode, isNewSearchPage]) => {
          if (isLink) {
            const openUrl = getConditionRouterParams(
              newSearchList,
              searchMode,
              isNewSearchPage
            );
            console.log(openUrl);
            window.open(openUrl, '_blank');
          }

          const query = { ...route.query };

          const resolver = new RetrieveUrlResolver({
            addition: store.getters.retrieveParams.addition,
            keyword: store.getters.retrieveParams.keyword,
          });

          Object.assign(query, resolver.resolveParamsToUrl());

          router.replace({
            query,
          });
        });
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
    handleHideWhole(index) {
      this.cacheExpandStr = this.cacheExpandStr.map((item) => item !== index);
    },
    handleIconClick(type, content, field, row, isLink, depth) {
      let value = ['date', 'date_nanos'].includes(field.field_type)
        ? row[field.field_name]
        : content;
      value = String(value)
        .replace(/<mark>/g, '')
        .replace(/<\/mark>/g, '');

      if (type === 'trace-view') {
        this.handleTraceIdClick(content);
        return;
      }
      if (type === 'search') {
        // 将表格单元添加到过滤条件
        this.handleAddCondition(field.field_name, 'eq', [value], isLink);
      } else if (type === 'copy') {
        // 复制单元格内容
        copyMessage(value);
      } else if (['is', 'is not', 'new-search-page-is'].includes(type)) {
        this.handleAddCondition(
          field.field_name,
          type,
          value === '--' ? [] : [value],
          isLink,
          depth
        );
      }
    },
    handleMenuClick(option, isLink) {
      switch (option.operation) {
        case 'is':
        case 'is not':
        case 'not':
        case 'new-search-page-is':
          const { depth, fieldName, operation, value } = option;
          const operator = operation === 'not' ? 'is not' : operation;
          this.handleAddCondition(
            fieldName,
            operator,
            value === '--' ? [] : [value],
            isLink,
            depth
          );
          break;
        case 'copy':
          copyMessage(option.value);
          break;
        case 'display':
          this.$emit(
            'fields-updated',
            option.displayFieldNames,
            undefined,
            false
          );
          break;
        case 'trace-view':
          this.handleTraceIdClick(option.value);
          break;
        default:
          break;
      }
    },
    handleOriginScroll() {
      if (this.isPageOver) return;
      clearTimeout(this.timer);
      this.timer = setTimeout(() => {
        const el = this.$refs.scrollContainer;
        this.showScrollTop = el.scrollTop > 550;
        if (el.scrollHeight - el.offsetHeight - el.scrollTop < 20) {
          if (this.count === this.limitCount || this.finishPolling) return;

          this.isPageOver = true;
          this.currentPage += 1;
          this.newScrollHeight = el.scrollTop;
          this.$emit('request-table-data');
        }
      }, 200);
    },
    handleOverColumn(fieldName) {
      if (!this.cacheOverFlowCol.includes(fieldName))
        this.cacheOverFlowCol.push(fieldName);
    },
    handleShowWhole(index) {
      this.cacheExpandStr.push(index);
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
      this.$store.commit('updateIndexItemParams', {
        sort_list: sortList,
      });
      this.$store.dispatch('requestIndexSetQuery');
      this.$router.replace({
        query: {
          ...this.$route.query,
          sort_list: JSON.stringify(sortList),
        },
      });
    },
    handleTraceIdClick(traceId) {
      if (this.apmRelation.is_active) {
        const { app_name: appName, bk_biz_id: bkBizId } =
          this.apmRelation.extra;
        const path = `/?bizId=${bkBizId}#/trace/home?app_name=${appName}&search_type=accurate&trace_id=${traceId}`;
        const url = `${window.__IS_MONITOR_COMPONENT__ ? location.origin : window.MONITOR_URL}${path}`;
        window.open(url, '_blank');
      } else {
        this.$bkMessage({
          message: this.$t('未找到相关的应用，请确认是否有Trace数据的接入。'),
          theme: 'warning',
        });
      }
    },
    initSubsetObj(bizId, indexKey) {
      const subsetObj = {};
      subsetObj.bizId = bizId;
      subsetObj.indexsetIds = [indexKey];
      subsetObj.fields = {};
      subsetObj.fields[indexKey] = {};
      return subsetObj;
    },
    isExistsOperator(operator) {
      // 是否是包含和不包含
      return ['exists', 'does not exists'].includes(operator);
    },
    renderHeaderAliasName(h, args) {
      const fieldIndex = args.column.index;
      const field = this.getShowTableVisibleFields[fieldIndex];
      const isShowSwitcher = ['date', 'date_nanos'].includes(field?.field_type);
      if (field) {
        const { getQueryAlias } = useFieldNameHook({ store: this.$store });
        const fieldName = getQueryAlias(field);
        const fieldType = field.field_type;
        const isUnionSource = field?.tag === 'union-source';
        const fieldIcon = this.getFieldIcon(field.field_type);
        const fieldIconColor = this.getFieldIconColor(field.field_type);
        const content = this.fieldTypeMap[fieldType]
          ? this.fieldTypeMap[fieldType].name
          : undefined;
        let unionContent = '';
        // 联合查询判断字段来源 若indexSetIDs缺少已检索的索引集内容 则增加字段来源判断
        if (this.isUnionSearch) {
          const indexSetIDs =
            field.index_set_ids?.map((item) => String(item)) || [];
          const isDifferentFields =
            indexSetIDs.length !== this.unionIndexItemList.length;
          if (isDifferentFields && !isUnionSource) {
            const lackIndexNameList = this.unionIndexItemList
              .filter((item) => indexSetIDs.includes(item.index_set_id))
              .map((item) => item.index_set_name);
            unionContent = `${this.$t('字段来源')}: ${lackIndexNameList.join(' ,')}`;
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
              directives: [
                {
                  name: 'bk-tooltips',
                  value: content,
                },
              ],

              style: {
                ...{
                  marginRight: '4px',
                },
                backgroundColor: fieldIconColor,
              },
            }),
            h(
              'span',
              {
                class: { 'lack-index-filed': isLackIndexFields },
                directives: [
                  {
                    name: 'bk-tooltips',
                    value: {
                      allowHTML: false,
                      content: isLackIndexFields ? unionContent : fieldName,
                    },
                  },
                ],
              },
              [fieldName]
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
                click: (e) => {
                  e.stopPropagation();
                  const displayFieldNames = [];
                  this.visibleFields.forEach((field) => {
                    if (field.field_name !== fieldName) {
                      displayFieldNames.push(field.field_name);
                    }
                  });
                  this.$store.dispatch('userFieldConfigChange', {
                    displayFields: displayFieldNames,
                  });
                  this.$store.commit('resetVisibleFields', displayFieldNames);
                },
              },
            }),
          ]
        );
      }
    },
    // 展开表格行JSON
    tableRowClick(row, option, column) {
      if (column?.className?.includes('original-str') ?? true) return;
      const ele = this.$refs.resultTable;
      ele.toggleRowExpansion(row);
    },
  },
  mixins: [tableRowDeepViewMixin],
  mounted() {
    this.lazyRoot = this.$el.parentNode;
  },
  props: {
    handleClickTools: Function,
    isPageOver: {
      required: false,
      type: Boolean,
    },
    isWrap: {
      default: false,
      type: Boolean,
    },
    originTableList: {
      required: true,
      type: Array,
    },
    retrieveParams: {
      required: true,
      type: Object,
    },
    showFieldAlias: {
      default: false,
      type: Boolean,
    },
    tableList: {
      required: true,
      type: Array,
    },
    tableLoading: {
      required: true,
      type: Boolean,
    },
    timeField: {
      default: '',
      type: String,
    },
    totalFields: {
      required: true,
      type: Array,
    },
    visibleFields: {
      required: true,
      type: Array,
    },
  },
  watch: {
    indexSetId() {
      // 切换索引集重置状态
      this.cacheExpandStr = [];
      this.cacheOverFlowCol = [];
    },
    retrieveParams: {
      deep: true,
      handler() {
        this.cacheExpandStr = [];
        this.cacheOverFlowCol = [];
      },
    },
    tableShowRowIndex: {
      handler() {
        console.log('');
      },
    },
  },
};
