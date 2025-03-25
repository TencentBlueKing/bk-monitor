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
  <div class="kv-list-wrapper">
    <div class="kv-content">
      <div
        v-for="(field, index) in renderList"
        class="log-item"
        :key="index"
      >
        <div
          :style="`max-width: ${getMaxWidth}px; width: ${getMaxWidth}px;`"
          class="field-label"
        >
          <span
            class="field-type-icon mr5"
            v-bk-tooltips="fieldTypePopover(field.field_name)"
            :class="getFieldIcon(field.field_name)"
            :style="{ backgroundColor: getFieldIconColor(field.field_name) }"
          ></span>
          <span class="field-text">{{ getFieldName(field) }}</span>
        </div>
        <div class="field-value">
          <template v-if="isJsonFormat(formatterStr(data, field.field_name))">
            <JsonFormatter
              :jsonValue="formatterStr(data, field.field_name)"
              :fields="getFieldItem(field.field_name)"
              @menu-click="agrs => handleJsonSegmentClick(agrs, field.field_name)"
            ></JsonFormatter>
          </template>

          <span
            v-if="getRelationMonitorField(field.field_name)"
            class="relation-monitor-btn"
            @click="handleViewMonitor(field.field_name)"
          >
            <span>{{ getRelationMonitorField(field.field_name) }}</span>
            <i class="bklog-icon bklog-jump"></i>
          </span>
          <template v-if="!isJsonFormat(formatterStr(data, field.field_name))">
            <text-segmentation
              :content="formatterStr(data, field.field_name)"
              :field="getFieldItem(field.field_name)"
              :forceAll="true"
              :autoWidth="true"
              @menu-click="agrs => handleJsonSegmentClick(agrs, field.field_name)"
            />
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
  import { getTextPxWidth, TABLE_FOUNT_FAMILY } from '@/common/util';
  import tableRowDeepViewMixin from '@/mixins/table-row-deep-view-mixin';
  import _escape from 'lodash/escape';
  import { mapGetters, mapState } from 'vuex';
  import JsonFormatter from '@/global/json-formatter.vue';
  import TextSegmentation from '../search-result-panel/log-result/text-segmentation';
  import { getFieldNameByField } from '@/hooks/use-field-name';
  export default {
    components: {
      TextSegmentation,
      JsonFormatter,
    },
    mixins: [tableRowDeepViewMixin],
    inheritAttrs: false,
    props: {
      data: {
        type: Object,
        default: () => {},
      },
      fieldList: {
        type: Array,
        default: () => [],
      },
      visibleFields: {
        type: Array,
        required: true,
      },
      totalFields: {
        type: Array,
        required: true,
      },
      kvShowFieldsList: {
        type: Array,
        require: true,
      },
      sortList: {
        type: Array,
        require: true,
      },
      listData: {
        type: Object,
        default: () => {},
      },
    },
    data() {
      return {
        toolMenuList: [
          { id: 'is', icon: 'bk-icon icon-enlarge-line search' },
          { id: 'not', icon: 'bk-icon icon-narrow-line search' },
          { id: 'display', icon: 'bk-icon icon-arrows-up-circle' },
          // { id: 'chart', icon: 'bklog-icon bklog-chart' },
          { id: 'copy', icon: 'bklog-icon bklog-copy' },
        ],
        toolMenuTips: {
          is: this.$t('添加 {n} 过滤项', { n: '=' }),
          not: this.$t('添加 {n} 过滤项', { n: '!=' }),
          hiddenField: this.$t('将字段从表格中移除'),
          displayField: this.$t('将字段添加至表格中'),
          copy: this.$t('复制'),
          text_is: this.$t('文本类型不支持 {n} 操作', { n: '=' }),
          text_not: this.$t('文本类型不支持 {n} 操作', { n: '!=' }),
        },
        mappingKay: {
          // is is not 值映射
          is: '=',
          'is not': '!=',
        },
        renderList: [],
      };
    },
    computed: {
      ...mapState('globals', ['fieldTypeMap']),
      ...mapGetters({
        retrieveParams: 'retrieveParams',
      }),
      ...mapState({
        formatJson: state => state.tableJsonFormat,
        showFieldAlias: state => state.showFieldAlias ?? false,
        isAllowEmptyField: state => state.tableAllowEmptyField,
      }),
      apmRelation() {
        return this.$store.state.indexSetFieldConfig.apm_relation;
      },
      bkBizId() {
        return this.$store.state.bkBizId;
      },
      showFieldList() {
        return this.totalFields.filter(item => {
          if (this.isAllowEmptyField) {
            return this.kvShowFieldsList.includes(item.field_name);
          }

          return (
            this.kvShowFieldsList.includes(item.field_name) &&
            !['--', '{}', '[]'].includes(this.formatterStr(this.data, item.field_name))
          );
        });
      },
      fieldKeyMap() {
        return this.totalFields
          .filter(item => this.kvShowFieldsList.includes(item.field_name))
          .map(el => el.field_name);
      },
      /** 获取字段里最大的字段宽度 */
      getMaxWidth() {
        // 表格内字体如果用12px在windows系统下表格字体会显得很细，所以用13px来加粗
        const fieldWidthList = this.fieldKeyMap.map(item => getTextPxWidth(item, '13px', TABLE_FOUNT_FAMILY));
        return Math.max(...fieldWidthList) + 22; // 22是icon的宽度
      },
      hiddenFields() {
        return this.fieldList.filter(item => !this.visibleFields.some(visibleItem => item === visibleItem));
      },
      filedSettingConfigID() {
        // 当前索引集的显示字段ID
        return this.$store.state.retrieve.filedSettingConfigID;
      },
      isHaveBkHostIDAndHaveValue() {
        // 当前是否有bk_host_id字段且有值
        return !!this.data?.bk_host_id;
      },
    },
    watch: {
      isAllowEmptyField() {
        this.onMountedRender();
      },
    },
    mounted() {
      this.onMountedRender();
    },
    methods: {
      onMountedRender() {
        const size = 40;
        let startIndex = 0;
        this.renderList = [];
        const setRenderList = () => {
          if (startIndex < this.showFieldList.length) {
            this.renderList.push(...this.showFieldList.slice(startIndex, startIndex + size));
            startIndex = startIndex + size;
            setTimeout(setRenderList);
          }
        };
        setRenderList();
      },
      isJsonFormat(content) {
        return this.formatJson && /^\[|\{/.test(content);
      },
      formatterStr(row, field) {
        // 判断当前类型是否为虚拟字段 若是虚拟字段则不使用origin_list而使用list里的数据
        const fieldType = this.getFieldType(field);
        // const rowData = fieldType === '__virtual__' ? this.listData : row;
        const rowData = this.listData;
        return this.tableRowDeepView(rowData, field, fieldType);
      },
      getFieldType(field) {
        const target = this.fieldList.find(item => item.field_name === field);
        return target ? target.field_type : '';
      },
      getFieldIcon(field) {
        const fieldType = this.getFieldType(field);
        return this.fieldTypeMap[fieldType] ? this.fieldTypeMap[fieldType].icon : 'bklog-icon bklog-unkown';
      },
      fieldTypePopover(field) {
        const target = this.fieldList.find(item => item.field_name === field);
        const fieldType = target ? target.field_type : '';

        return {
          content: this.fieldTypeMap[fieldType]?.name,
          disabled: !this.fieldTypeMap[fieldType],
        };
      },
      getFieldIconColor(type) {
        const fieldType = this.getFieldType(type);
        return this.fieldTypeMap?.[fieldType] ? this.fieldTypeMap?.[fieldType]?.color : '#EAEBF0';
      },
      checkDisable(id, field) {
        const type = this.getFieldType(field);
        const isExist = this.filterIsExist(id, field);
        return (['is', 'not'].includes(id) && type === 'text') || type === '__virtual__' || isExist
          ? 'is-disabled'
          : '';
      },
      handleJsonSegmentClick({ isLink, option }, fieldName) {
        // 为了兼容旧的逻辑，先这么写吧
        // 找时间梳理下这块，写的太随意了
        const { operation, value, depth, isNestedField } = option;
        const operator = operation === 'not' ? 'is not' : operation;
        const field = this.totalFields.find(f => f.field_name === fieldName);
        this.$emit('value-click', operator, value, isLink, field, depth, isNestedField);
      },

      /**
       * @desc 关联跳转
       * @param { string } field
       */
      handleViewMonitor(field) {
        const key = field.toLowerCase();
        let path = '';
        switch (key) {
          // trace检索
          case 'trace_id':
          case 'traceid':
            if (this.apmRelation.is_active) {
              const { app_name: appName, bk_biz_id: bkBizId } = this.apmRelation.extra;
              path = `/?bizId=${bkBizId}#/trace/home?app_name=${appName}&search_type=accurate&trace_id=${this.data[field]}`;
            } else {
              this.$bkMessage({
                theme: 'warning',
                message: this.$t('未找到相关的应用，请确认是否有Trace数据的接入。'),
              });
            }
            break;
          // 主机监控
          case 'serverip':
          case 'ip':
          case 'bk_host_id':
            {
              const endStr = `${this.data[field]}${field === 'bk_host_id' && this.isHaveBkHostIDAndHaveValue ? '' : '-0'}`;
              path = `/?bizId=${this.bkBizId}#/performance/detail/${endStr}`;
            }
            break;
          // 容器
          case 'container_id':
          case '__ext.container_id':
            path = `/?bizId=${this.bkBizId}#/k8s?dashboardId=pod`;
            break;
          default:
            break;
        }

        if (path) {
          const url = `${window.__IS_MONITOR_COMPONENT__ ? location.origin : window.MONITOR_URL}${path}`;
          window.open(url, '_blank');
        }
      },
      /**
       * @desc 判断是否有关联监控跳转
       * @param { string } field
       */
      getRelationMonitorField(field) {
        // 外部版不提供外链跳转
        if (this.$store.state.isExternal) return false;

        const key = field.toLowerCase();
        switch (key) {
          // trace检索
          case 'trace_id':
          case 'traceid':
            return this.$t('trace检索');
          // 主机监控
          case 'serverip':
          case 'ip':
          case 'bk_host_id': {
            const lowerKeyData = Object.entries(this.data).reduce((pre, [curKey, curVal]) => {
              pre[curKey.toLowerCase()] = curVal;
              return pre;
            }, {});
            return !!lowerKeyData[key] ? this.$t('主机') : null; // 判断ip和serverIp是否有值 无值则不显示主机
          }
          // 容器
          case 'container_id':
          case '__ext.container_id':
            return this.$t('容器');
          default:
            return;
        }
      },
      filterIsExist(id, field) {
        if (this.retrieveParams?.addition.length) {
          if (id === 'not') id = 'is not';
          const curValue = this.tableRowDeepView(this.data, field, this.getFieldType(field), false);
          return this.retrieveParams.addition.some(addition => {
            return (
              addition.field === field &&
              addition.operator === (this.mappingKay[id] ?? id) && // is is not 值映射 判断是否
              addition.value.toString() === curValue.toString()
            );
          });
        }
        return false;
      },
      getFieldItem(fieldName) {
        return this.fieldList.find(item => item.field_name === fieldName);
      },
      getFieldName(field) {
        return getFieldNameByField(field, this.$store);
      },
    },
  };
</script>

<style lang="scss" scoped>
  /* stylelint-disable no-descending-specificity */
  .kv-list-wrapper {
    font-family: var(--table-fount-family);
    font-size: var(--table-fount-size);

    .log-item {
      display: flex;
      align-items: start;
      min-height: 24px;

      .field-label {
        display: flex;
        flex-shrink: 0;
        flex-wrap: nowrap;
        align-items: baseline;
        height: 100%;
        margin-right: 18px;

        .field-type-icon {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-width: 16px;
          height: 16px;
          margin: 0 5px 0 0;
          font-size: 12px;
          color: #63656e;
          background: #dcdee5;
          border-radius: 2px;
        }

        .field-text {
          display: block;
          width: auto;
          overflow: hidden;
          word-break: normal;
          word-wrap: break-word;
        }

        :deep(.bklog-ext) {
          min-width: 22px;
          height: 22px;
          transform: translateX(-3px) scale(0.7);
        }
      }

      .field-value {
        display: flex;
        word-break: break-all;
      }
    }

    .relation-monitor-btn {
      min-width: fit-content;
      padding-right: 6px;
      // margin-left: 12px;
      font-size: 12px;
      color: #3a84ff;
      cursor: pointer;
    }
  }
</style>
