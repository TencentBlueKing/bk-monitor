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

import { mapState, mapGetters } from 'vuex';
import { formatDate, random, copyMessage } from '@/common/util';
import tableRowDeepViewMixin from '@/mixins/table-row-deep-view-mixin';
import EventPopover from '@/views/retrieve/result-comp/event-popover.vue';
import RegisterColumn from '@/views/retrieve/result-comp/register-column.vue';
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
    EventPopover,
    TextHighlight,
    OperatorTools,
    RetrieveLoader,
    TableColumn,
    ExpandView,
    RegisterColumn,
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
      default: () => { },
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
    };
  },
  computed: {
    ...mapState('globals', ['fieldTypeMap']),
    ...mapGetters({
      isUnionSearch: 'isUnionSearch',
      unionIndexList: 'unionIndexList',
      unionIndexItemList: 'unionIndexItemList',
    }),
    showHandleOption() {
      return Boolean(this.visibleFields.length);
    },
    getOperatorToolsWidth() {
      return this.operatorConfig?.bcsWebConsole.is_active ? '84' : '58';
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
    '$route.params.indexId'() { // 切换索引集重置状态
      this.cacheExpandStr = [];
      this.cacheOverFlowCol = [];
    },
    visibleFields: {
      deep: true,
      handler(list) {
        this.tableRandomKey = random(6);
        if (list.length !== 0) {
          const columnObj = JSON.parse(localStorage.getItem('table_column_width_obj'));
          const { params: { indexId }, query: { bizId } } = this.$route;
          let widthObj = {};

          for (const bizKey in columnObj) {
            if (bizKey === bizId) {
              for (const fieldKey in columnObj[bizId].fields) {
                fieldKey === indexId && (widthObj = columnObj[bizId].fields[indexId]);
              }
            }
          }

          list.forEach((el, index) => {
            el.width = widthObj[index] || el.width;
          });
        }
      },
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
        markList = markVal.map(item => item.replace(/<mark>/g, '')
          .replace(/<\/mark>/g, ''));
      }

      return markList;
    },
    formatterStr(content) {
      // 匹配高亮标签
      let value = content;

      const markVal = content.match(/(<mark>).*?(<\/mark>)/g) || [];
      if (markVal.length) {
        value = String(value).replace(/<mark>/g, '')
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
      const { params: { indexId }, query: { bizId } } = this.$route;
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
      const field = this.visibleFields[$index - 1];
      const isShowSwitcher = field.field_type === 'date';
      if (field) {
        const fieldName = this.showFieldAlias ? this.fieldAliasMap[field.field_name] : field.field_name;
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
        const isLackIndexFields = (!!unionContent && this.isUnionSearch);
        const isHiddenToggleDisplay = this.visibleFields.filter(item => item.tag !== 'union-source').length === 1 || isUnionSource;

        return h('div', {
          class: 'render-header',
        }, [
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
          h('span',
            {
              directives: [{
                name: 'bk-tooltips',
                value: { content: isLackIndexFields ? unionContent : fieldName },
              }],
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
            class: `bk-icon icon-minus-circle-shape toggle-display ${isHiddenToggleDisplay ? 'is-hidden' : ''}`,
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
                this.$emit('fieldsUpdated', displayFieldNames, undefined, false);
              },
            },
          }),
        ]);
      }
    },
    handleIconClick(type, content, field, row) {
      let value = field.field_type === 'date' ? row[field.field_name] : content;
      value = String(value).replace(/<mark>/g, '')
        .replace(/<\/mark>/g, '');
      if (type === 'search') { // 将表格单元添加到过滤条件
        this.$emit('addFilterCondition', field.field_name, 'eq', value);
      } else if (type === 'copy') { // 复制单元格内容
        copyMessage(value);
      } else if (['is', 'is not'].includes(type)) {
        this.$emit('addFilterCondition', field.field_name, type, value === '--' ? '' : value.toString());
      }
    },
    getFieldIcon(fieldType) {
      return this.fieldTypeMap[fieldType] ? this.fieldTypeMap[fieldType].icon : 'log-icon icon-unkown';
    },
    handleMenuClick(option) {
      switch (option.operation) {
        case 'is':
        case 'is not':
          // eslint-disable-next-line no-case-declarations
          const { fieldName, operation, value } = option;
          this.$emit('addFilterCondition', fieldName, operation, value === '--' ? '' : value.toString());
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
     * @desc: 鼠标放到原始日志上
     * @param {Element} e hover的dom
     * @param {String} originStr hover的原始日志的字符串
     */
    handleHoverFavoriteName(e, originStr = '') {
      if (!this.originStrInstance) {
        this.hoverOriginStr = originStr;
        this.originStrInstance = this.$bkPopover(e.target, {
          content: this.$refs.copyTools,
          arrow: true,
          placement: 'top',
          offset: '0, -50',
          theme: 'light',
          // allowHTML: true,
          interactive: true,
          appendTo: 'parent',
          boundary: this.scrollContent,
          onHidden: () => {
            this.originStrInstance?.destroy();
            this.originStrInstance = null;
          },
        });
        this.originStrInstance.show(500);
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
      this.$emit('shouldRetrieve', { sort_list: sortList }, false);
    },
    getTableColumnContent(row, field) {
      // 日志来源 展示来源的索引集名称
      if (field?.tag === 'union-source') {
        return this.unionIndexItemList.find(item => item.index_set_id === String(row.__index_set_id__))?.index_set_name ?? '';
      }
      return this.tableRowDeepView(row, field.field_name, field.field_type);
    },
  },
};
