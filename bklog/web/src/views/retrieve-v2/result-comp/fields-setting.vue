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
    class="fields-setting"
    v-bkloading="{ isLoading: isLoading }"
  >
    <!-- 设置列表字段 -->
    <div class="fields-container">
      <div class="fields-config-container">
        <div
          class="add-fields-config"
          v-show="!isShowAddInput"
          @click="handleClickAddNew"
        >
          <bk-button
            class="config-btn"
            :text="true"
          >
            <i class="bk-icon icon-plus-circle-shape"></i>
            <span>{{ $t('新建配置') }}</span>
          </bk-button>
        </div>
        <div
          class="config-tab-item"
          v-show="isShowAddInput"
        >
          <bk-input
            v-model="newConfigStr"
            :class="['config-input', { 'input-error': isInputError }]"
          >
          </bk-input>
          <div class="panel-operate">
            <i
              class="bk-icon icon-check-line"
              @click="handleAddNewConfig"
            ></i>
            <i
              class="bk-icon icon-close-line-2"
              @click="handleCancelNewConfig"
            ></i>
          </div>
        </div>
        <bk-tab
          ref="configTabRef"
          ext-cls="config-tab"
          :active.sync="activeConfigTab"
          :tab-position="'left'"
          type="unborder-card"
        >
          <template>
            <bk-tab-panel
              v-for="(panel, index) in configTabPanels"
              :key="panel.name"
              :name="panel.name"
              :render-label="e => renderHeader(e, panel, index)"
            >
            </bk-tab-panel>
          </template>
        </bk-tab>
      </div>
      <div>
        <div class="fields-tab-container">
          <bk-tab
            :active.sync="activeFieldTab"
            :labelHeight="42"
            type="unborder-card"
          >
            <template v-for="(panel, index) in fieldTabPanels">
              <bk-tab-panel
                :key="index"
                v-bind="panel"
              ></bk-tab-panel>
            </template>
          </bk-tab>
        </div>
        <bk-input
          ref="menuSearchInput"
          class="menu-select-search"
          :clearable="false"
          :placeholder="$t('搜索')"
          :value="keyword"
          @change="searchChange"
        >
        </bk-input>
        <div class="fields-list-container">
          <div class="total-fields-list">
            <div class="title">
              <!-- 待选项列表 全部添加 -->
              <span>{{ $t('待选项列表') + '(' + toSelectLength + ')' }}</span>
              <span
                class="text-action add-all"
                @click="addAllField"
                >{{ $t('全部添加') }}</span
              >
            </div>
            <ul class="select-list">
              <li
                v-for="item in filterShadowTotal"
                style="cursor: pointer"
                class="select-item"
                v-show="activeFieldTab === 'visible' ? !item.is_display : !item.isSorted && item.es_doc_values"
                :key="item.field_name"
                @click="addField(item)"
              >
                <span
                  class="field-name"
                  v-bk-overflow-tips
                  >{{ getFiledDisplay(item) }}</span
                >
                <span class="icon bklog-icon bklog-filled-right-arrow"></span>
              </li>
            </ul>
          </div>
          <!-- 中间的箭头 -->
          <div class="sort-icon">
            <span class="icon bklog-icon bklog-double-arrow"></span>
          </div>
          <!-- 设置显示字段 -->
          <div
            class="visible-fields-list"
            v-show="activeFieldTab === 'visible'"
          >
            <div class="title">
              <!-- 已选项列表 -->
              <span>{{ $t('已选项列表') + '(' + shadowVisible.length + ')' }}</span>
              <span
                class="icon bklog-icon bklog-info-fill"
                v-bk-tooltips="$t('支持拖拽更改顺序，从上向下对应列表列从左到右顺序')"
              ></span>
              <span
                class="clear-all text-action"
                @click="deleteAllField"
                >{{ $t('取消') }}</span
              >
            </div>
            <vue-draggable
              v-bind="dragOptions"
              class="select-list"
              v-model="shadowVisible"
            >
              <transition-group>
                <li
                  v-for="(item, index) in shadowVisible"
                  class="select-item"
                  :key="item"
                >
                  <span class="icon bklog-icon bklog-drag-dots"></span>
                  <span
                    class="field-name"
                    v-bk-overflow-tips
                    >{{ getFiledDisplayByFieldName(item) }}</span
                  >
                  <span
                    class="bk-icon icon-close-circle-shape delete"
                    @click="deleteField(item, index)"
                  ></span>
                </li>
              </transition-group>
            </vue-draggable>
          </div>
          <!-- 设置权重排序 -->
          <div
            class="sort-fields-list"
            v-show="activeFieldTab === 'sort'"
          >
            <div class="title">
              <!-- 已选项列表 -->
              <span>{{ $t('已选项列表') + '(' + shadowSort.length + ')' }}</span>
              <span
                class="icon bklog-icon bklog-info-fill"
                v-bk-tooltips="$t('支持拖拽更改顺序，排在上面的拥有更高的排序权重')"
              ></span>
              <span
                class="clear-all text-action"
                @click="deleteAllField"
                >{{ $t('取消') }}</span
              >
            </div>
            <vue-draggable
              v-bind="dragOptions"
              class="select-list"
              v-model="shadowSort"
            >
              <transition-group>
                <li
                  v-for="(item, index) in shadowSort"
                  class="select-item"
                  :key="item[0]"
                >
                  <span class="icon bklog-icon bklog-drag-dots"></span>
                  <span
                    :style="`width: calc(100% - ${fieldWidth}px);`"
                    class="field-name"
                    v-bk-overflow-tips
                    >{{ getFiledDisplayByFieldName(item[0]) }}</span
                  >
                  <span :class="`bk-icon status ${filterStatusIcon(item[1])}`"></span>
                  <span
                    class="option text-action"
                    @click="setOrder(item)"
                    >{{ filterOption(item[1]) }}</span
                  >
                  <span
                    class="bk-icon icon-close-circle-shape delete"
                    @click="deleteField(item[0], index)"
                  ></span>
                </li>
              </transition-group>
            </vue-draggable>
          </div>
        </div>
      </div>
    </div>
    <div class="fields-button-container">
      <bk-button
        class="mr10"
        :theme="'primary'"
        type="submit"
        @click="confirmModifyFields"
      >
        {{ $t('保存') }}
      </bk-button>
      <bk-button
        :theme="'default'"
        type="submit"
        @click="cancelModifyFields"
      >
        {{ $t('取消') }}
      </bk-button>
    </div>
  </div>
</template>

<script>
import { getFieldNameByField } from '@/hooks/use-field-name';
import VueDraggable from 'vuedraggable';
import { mapGetters } from 'vuex';

// import useFieldNameHook from '@/hooks/use-field-name';
import fieldsSettingOperate from './fields-setting-operate';
import { BK_LOG_STORAGE } from '@/store/store.type';
export default {
  components: {
    VueDraggable,
  },
  props: {
    retrieveParams: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      isLoading: false,
      shadowVisible: [],
      shadowAllTotal: [], // 所有字段
      newConfigStr: '', // 新增配置配置名
      isShowAddInput: false, // 是否展示新增配置输入框
      currentClickConfigID: 0, // 当前配置项ID
      activeFieldTab: 'visible',
      activeConfigTab: 'default', // 当前活跃的配置配置名
      isConfirmSubmit: false, // 是否点击保存
      isInputError: false, // 新建配置名称是否不合法
      fieldTabPanels: [
        { name: 'visible', label: this.$t('显示字段') },
        { name: 'sort', label: this.$t('排序权重') },
      ],
      configTabPanels: [], // 配置列表
      dragOptions: {
        animation: 150,
        tag: 'ul',
        handle: '.bklog-drag-dots',
        'ghost-class': 'sortable-ghost-class',
      },
      isSortFieldChanged: false,
      keyword: '',
    };
  },
  computed: {
    shadowSort() {
      return this.$store.state.indexFieldInfo.sort_list;
    },
    shadowTotal() {
      return this.$store.state.indexFieldInfo.fields;
    },
    filterShadowTotal() {
      const fields = this.$store.state.indexFieldInfo.fields;
      return fields.filter(item => {
        const matchesKeyword = item.field_name?.includes(this.keyword) || item.query_alias?.includes(this.keyword);
        const isInShadowVisible = this.shadowVisible.some(shadowItem => shadowItem === item.field_name);
        return matchesKeyword && !isInShadowVisible;
      });
    },
    showFieldAlias() {
      return this.$store.state.storage[BK_LOG_STORAGE.SHOW_FIELD_ALIAS];
    },
    fieldAliasMap() {
      let fieldAliasMap = {};
      this.$store.state.indexFieldInfo.fields.forEach(item => {
        fieldAliasMap[item.field_name] = item.field_alias || item.field_name;
      });
      return fieldAliasMap;
    },
    toSelectLength() {
      if (this.keyword) {
        return this.filterShadowTotal.length;
      }
      if (this.activeFieldTab === 'visible') {
        return this.shadowTotal.length - this.shadowVisible.length;
      }
      let totalLength = 0;
      this.shadowTotal.forEach(fieldInfo => {
        if (fieldInfo.es_doc_values) {
          totalLength += 1;
        }
      });
      return totalLength - this.shadowSort.length;
    },

    filedSettingConfigID() {
      // 当前索引集的显示字段ID
      return this.$store.state.retrieve.filedSettingConfigID;
    },
    currentClickConfigData() {
      // 当前选中的配置
      return this.configTabPanels.find(item => item.id === this.currentClickConfigID) || this.configTabPanels?.[0];
    },
    fieldWidth() {
      return this.$store.state.isEnLanguage ? '60' : '114';
    },
    ...mapGetters({
      unionIndexList: 'unionIndexList',
      isUnionSearch: 'isUnionSearch',
    }),
  },
  watch: {
    newConfigStr() {
      this.isInputError = false;
    },
  },
  created() {
    this.currentClickConfigID = this.configTabPanels.length ? this.filedSettingConfigID : 0;
    this.initRequestConfigListShow();
  },
  methods: {
    getFiledDisplayByFieldName(name) {
      const field = this.shadowTotal.find(item => item.field_name === name);
      return this.getFiledDisplay(field);
    },
    getFiledDisplay(field) {
      if (this[BK_LOG_STORAGE.SHOW_FIELD_ALIAS]) {
        return getFieldNameByField(field, this.$store);
      }
      const alias = this.fieldAliasMap[field.field_name];
      if (alias && alias !== field.field_name) {
        return `${field.field_name}(${alias})`;
      }
      return field.field_name;
    },
    /** 带config列表请求的初始化 */
    async initRequestConfigListShow() {
      await this.getFiledConfigList();
      this.initShadowFields();
    },
    /** 保存或应用 */
    async confirmModifyFields() {
      if (this.shadowVisible.length === 0) {
        this.messageWarn(this.$t('显示字段不能为空'));
        return;
      }
      try {
        const confirmConfigData = {
          editStr: this.currentClickConfigData.name,
          sort_list: this.shadowSort,
          display_fields: this.shadowVisible,
          id: this.currentClickConfigData.id,
        };
        this.isConfirmSubmit = true;
        await this.handleUpdateConfig(confirmConfigData);
        // 判断当前应用的config_id 与 索引集使用的config_id是否相同 不同则更新config
        if (this.currentClickConfigData.id !== this.filedSettingConfigID) {
          await this.submitFieldsSet(this.currentClickConfigData.id);
        }
        this.cancelModifyFields();
        this.$store.commit('updateIsSetDefaultTableColumn', false);
        this.$store
          .dispatch('userFieldConfigChange', {
            displayFields: this.shadowVisible,
            fieldsWidth: {},
          })
          .then(() => {
            this.$store.commit('resetVisibleFields', this.shadowVisible);
            this.$store.commit('updateIsSetDefaultTableColumn');
          });
        await this.$store.dispatch('requestIndexSetFieldInfo');
        await this.$store.dispatch('requestIndexSetQuery');
      } catch (error) {
        console.warn(error);
      } finally {
        this.isConfirmSubmit = false;
      }
    },
    /** 更新config */
    async submitFieldsSet(configID) {
      await this.$http
        .request('retrieve/postFieldsConfig', {
          data: {
            index_set_id: window.__IS_MONITOR_COMPONENT__ ? this.$route.query.indexId : this.$route.params.indexId,
            index_set_ids: this.unionIndexList,
            index_set_type: this.isUnionSearch ? 'union' : 'single',
            display_fields: this.shadowVisible,
            sort_list: this.shadowSort,
            config_id: configID,
          },
        })
        .catch(e => {
          console.warn(e);
        });
    },
    cancelModifyFields() {
      this.$emit('cancel');
      this.isSortFieldChanged = false;
    },
    filterStatusIcon(val) {
      if (val === 'desc') {
        return 'icon-arrows-down-line';
      }
      if (val === 'asc') {
        return 'icon-arrows-up-line';
      }
      return '';
    },
    filterOption(val) {
      if (val === 'desc') {
        return this.$t('设为升序');
      }
      if (val === 'asc') {
        return this.$t('设为降序');
      }
      return '';
    },
    addField(fieldInfo) {
      this.isSortFieldChanged = true;
      if (this.activeFieldTab === 'visible') {
        fieldInfo.is_display = true;
        this.shadowVisible.push(fieldInfo.field_name);
      } else {
        fieldInfo.isSorted = true;
        this.isSortFieldChanged = true;
        this.shadowSort.push([fieldInfo.field_name, 'asc']);
      }
    },
    deleteField(fieldName, index) {
      this.isSortFieldChanged = true;
      const arr = this.shadowTotal;
      if (this.activeFieldTab === 'visible') {
        this.shadowVisible.splice(index, 1);
        for (let i = 0; i < arr.length; i++) {
          if (arr[i].field_name === fieldName) {
            arr[i].is_display = false;
            return;
          }
        }
      } else {
        this.shadowSort.splice(index, 1);
        for (let i = 0; i < arr.length; i++) {
          if (arr[i].field_name === fieldName) {
            this.isSortFieldChanged = true;
            arr[i].isSorted = false;
            return;
          }
        }
      }
    },
    addAllField() {
      if (this.activeFieldTab === 'visible') {
        this.shadowTotal.forEach(fieldInfo => {
          if (!fieldInfo.is_display) {
            fieldInfo.is_display = true;
            this.shadowVisible.push(fieldInfo.field_name);
          }
        });
      } else {
        this.shadowTotal.forEach(fieldInfo => {
          if (!fieldInfo.isSorted && fieldInfo.es_doc_values) {
            fieldInfo.isSorted = true;
            this.isSortFieldChanged = true;
            this.shadowSort.push([fieldInfo.field_name, 'asc']);
          }
        });
      }
    },
    deleteAllField() {
      if (this.activeFieldTab === 'visible') {
        this.shadowTotal.forEach(fieldInfo => {
          fieldInfo.is_display = false;
          this.shadowVisible.splice(0, this.shadowVisible.length);
        });
      } else {
        this.shadowTotal.forEach(fieldInfo => {
          fieldInfo.isSorted = false;
          this.isSortFieldChanged = this.isSortFieldChanged || this.shadowSort.length;
          this.shadowSort.splice(0, this.shadowSort.length);
        });
      }
    },
    setOrder(item) {
      this.isSortFieldChanged = true;
      item[1] = item[1] === 'asc' ? 'desc' : 'asc';
      this.$forceUpdate();
    },
    renderHeader(h, row, index) {
      row.index = index;
      return h(fieldsSettingOperate, {
        props: {
          configItem: row,
        },
        on: {
          operateChange: this.handleLeftOperateChange,
          setPopperInstance: this.setPopperInstance,
        },
      });
    },
    /** 用户操作 */
    handleLeftOperateChange(type, configItem) {
      switch (type) {
        case 'click':
          this.currentClickConfigID = configItem.id;
          this.initShadowFields();
          break;
        case 'delete':
          this.handleDeleteConfig(configItem.id);
          break;
        case 'edit':
          this.handleEditConfigName(configItem.index);
          break;
        case 'update':
          this.handleUpdateConfig(configItem);
          break;
        case 'cancel':
          this.handleCancelEditConfig(configItem.index);
          break;
      }
    },
    /** 编辑配置 */
    handleEditConfigName(index) {
      this.configTabPanels.forEach(item => (item.isShowEdit = false));
      this.configTabPanels[index].isShowEdit = true;
      this.isShowAddInput = false;
    },
    /** 点击新增配置 */
    handleClickAddNew() {
      this.configTabPanels.forEach(item => (item.isShowEdit = false));
      this.isShowAddInput = true;
    },
    /** 新增配置 */
    handleAddNewConfig() {
      if (!this.newConfigStr) {
        this.isInputError = true;
        return;
      }
      const configValue = this.configTabPanels[0];
      configValue.editStr = this.newConfigStr;
      this.handleUpdateConfig(configValue, true);
    },
    /** 取消新增配置 */
    handleCancelNewConfig() {
      this.newConfigStr = '';
      this.isShowAddInput = false;
      this.isInputError = false;
    },
    /** 取消编辑配置 */
    handleCancelEditConfig(index) {
      this.configTabPanels[index].editStr = this.configTabPanels[index].name;
      this.configTabPanels[index].isShowEdit = false;
    },
    /** 更新配置 */
    async handleUpdateConfig(updateItem, isCreate = false) {
      const requestStr = isCreate ? 'create' : 'update';
      const data = {
        name: updateItem.editStr,
        sort_list: updateItem.sort_list,
        display_fields: updateItem.display_fields,
        config_id: undefined,
        index_set_id: window.__IS_MONITOR_COMPONENT__ ? this.$route.query.indexId : this.$route.params.indexId,
        index_set_ids: this.unionIndexList,
        index_set_type: this.isUnionSearch ? 'union' : 'single',
      };
      if (!isCreate) data.config_id = updateItem.id;
      try {
        await this.$http.request(`retrieve/${requestStr}FieldsConfig`, {
          data,
        });
        if (this.activeFieldTab === 'sort') {
          if (this.isSortFieldChanged) {
            this.$store.dispatch('requestIndexSetQuery', { formChartChange: false }).then(() => {
              this.isSortFieldChanged = false;
            });
          }
          this.$emit('should-retrieve', undefined, false); // 不请求图表
        }
      } catch (error) {
      } finally {
        if (!this.isConfirmSubmit) this.initRequestConfigListShow();
        this.newConfigStr = '';
        this.isShowAddInput = false;
      }
    },
    /** 删除配置 */
    async handleDeleteConfig(configID) {
      try {
        await this.$http.request('retrieve/deleteFieldsConfig', {
          data: {
            config_id: configID,
            index_set_id: window.__IS_MONITOR_COMPONENT__ ? this.$route.query.indexId : this.$route.params.indexId,
            index_set_ids: this.unionIndexList,
            index_set_type: this.isUnionSearch ? 'union' : 'single',
          },
        });
      } catch (error) {
      } finally {
        this.initRequestConfigListShow();
        this.newConfigStr = '';
        if (this.filedSettingConfigID === configID) {
          this.currentClickConfigID = this.configTabPanels[0].id;
          const { display_fields } = this.configTabPanels[0];
          this.$store.commit('resetVisibleFields', display_fields);
          this.$store.dispatch('requestIndexSetQuery');
          this.cancelModifyFields();
        }
      }
    },
    /** 初始化显示字段 */
    initShadowFields() {
      this.activeConfigTab = this.currentClickConfigData.name;
      this.shadowTotal.forEach(fieldInfo => {
        this.shadowSort.forEach(item => {
          if (fieldInfo.field_name === item[0]) {
            fieldInfo.isSorted = true;
          }
        });
      });
      // 后台给的 display_fields 可能有无效字段 所以进行过滤，获得排序后的字段
      this.shadowVisible =
        this.currentClickConfigData.display_fields
          ?.map(displayName => {
            for (const field of this.shadowTotal) {
              if (field.field_name === displayName) {
                field.is_display = true;
                return displayName;
              }
            }
          })
          ?.filter(Boolean) || [];
    },
    /** 获取配置列表 */
    async getFiledConfigList() {
      this.isLoading = true;
      try {
        const res = await this.$http.request('retrieve/getFieldsListConfig', {
          data: {
            ...(this.isUnionSearch
              ? { index_set_ids: this.unionIndexList }
              : {
                  index_set_id: window.__IS_MONITOR_COMPONENT__
                    ? this.$route.query.indexId
                    : this.$route.params.indexId,
                }),
            scope: 'default',
            index_set_type: this.isUnionSearch ? 'union' : 'single',
          },
        });
        this.configTabPanels = res.data.map(item => ({
          ...item,
          isShowEdit: false,
          editStr: item.name,
        }));
      } catch (error) {
      } finally {
        this.isLoading = false;
      }
    },
    setPopperInstance(status) {
      this.$emit('set-popper-instance', status);
    },
    searchChange(v) {
      this.keyword = v;
    },
  },
};
</script>

<style lang="scss" scoped>
  @import '../../../scss/mixins/scroller';

  .fields-setting {
    position: relative;

    .fields-container {
      display: flex;

      .fields-config-container {
        .add-fields-config {
          height: 40px;
          color: #3a84ff;
          cursor: pointer;
          border-right: 1px solid #dcdee5;

          .config-btn {
            width: 100%;
            height: 100%;
            padding-left: 24px;
            line-height: 100%;
            text-align: left;

            .bk-icon {
              transform: translateY(-2px);
            }
          }
        }

        .config-tab {
          width: 100%;
          height: calc(100% - 40px);
          overflow-y: auto;
        }

        .config-tab-item {
          display: flex;
          align-items: center;
          justify-content: space-between;
          width: 100%;
          height: 40px;
          padding: 0 12px 0 4px;

          .config-input {
            width: 100px;
          }

          .input-error {
            :deep(.bk-form-input) {
              border: 1px solid #d7473f;
            }
          }

          .panel-name {
            padding-left: 20px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }

          .panel-operate {
            margin-left: 10px;
            font-size: 14px;
            color: #979ba5;
            cursor: pointer;

            .edit-icon:hover {
              color: #3a84ff;
            }

            .icon-check-line {
              color: #3a84ff;
            }

            .icon-close-line-2 {
              color: #d7473f;
            }
          }
        }

        :deep(.bk-tab-label) {
          width: 100%;
        }

        :deep(.bk-tab-label-item) {
          padding: 0;

          /* stylelint-disable-next-line declaration-no-important */
          line-height: 40px !important;
          color: #63656e;
          text-align: left;

          &:hover {
            background: #f0f1f5;
          }
        }

        :deep(.bk-tab-header) {
          width: 100%;
          min-width: 160px;
          padding: 0 0 10px;
          // &::after {
          //   display: none;
          // }
          &::before {
            display: none;
          }
        }

        :deep(.active) {
          color: #3a84ff;

          /* stylelint-disable-next-line declaration-no-important */
          background: #e1ecff !important;
        }

        :deep(.bk-tab-section) {
          display: none;
        }
      }
    }

    .fields-tab-container {
      width: 723px;
      padding: 0px 10px 0 10px;
    }

    .menu-select-search {
      width: 340px;
      padding-left: 10px;
      margin-top: -30px;
    }

    .fields-list-container {
      display: flex;
      width: 723px;
      padding: 0 10px 14px 10px;
      margin-top: 10px;

      .total-fields-list,
      .visible-fields-list,
      .sort-fields-list {
        width: 330px;
        height: 268px;
        border: 1px solid #dcdee5;

        .text-action {
          font-size: 12px;
          color: #3a84ff;
          cursor: pointer;
        }

        .title {
          position: relative;
          display: flex;
          align-items: center;
          height: 41px;
          padding: 0 16px;
          line-height: 40px;
          color: #313238;
          border-bottom: 1px solid #dcdee5;

          .bklog-info-fill {
            margin-left: 8px;
            font-size: 14px;
            color: #979ba5;
            outline: none;
          }

          .add-all,
          .clear-all {
            position: absolute;
            top: 0;
            right: 16px;
          }
        }

        .select-list {
          height: 223px;
          padding: 4px 0;
          overflow: auto;

          @include scroller;

          .select-item {
            display: flex;
            align-items: center;
            padding: 0 8px;
            font-size: 12px;
            line-height: 32px;

            .bklog-drag-dots {
              width: 16px;
              font-size: 14px;
              color: #979ba5;
              text-align: left;
              cursor: move;
              opacity: 0;
              transition: opacity 0.2s linear;
            }

            &.sortable-ghost-class {
              background: #eaf3ff;
              transition: background 0.2s linear;
            }

            &:hover {
              background: #eaf3ff;
              transition: background 0.2s linear;

              .bklog-drag-dots {
                opacity: 1;
                transition: opacity 0.2s linear;
              }
            }
          }
        }
      }

      /* stylelint-disable-next-line no-descending-specificity */
      .total-fields-list .select-list .select-item {
        .field-name {
          width: calc(100% - 24px);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .bklog-filled-right-arrow {
          width: 24px;
          font-size: 16px;
          color: #3a84ff;
          text-align: right;
          cursor: pointer;
          opacity: 0;
          transition: opacity 0.2s linear;
          transform: scale(0.5);
          transform-origin: right center;
        }

        &:hover .bklog-filled-right-arrow {
          opacity: 1;
          transition: opacity 0.2s linear;
        }
      }

      /* stylelint-disable-next-line no-descending-specificity */
      .visible-fields-list .select-list .select-item {
        .field-name {
          // 16 38
          width: calc(100% - 30px);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .delete {
          font-size: 16px;
          color: #c4c6cc;
          text-align: right;
          cursor: pointer;
        }
      }

      .sort-fields-list {
        flex-shrink: 0;

        .sort-list-header {
          display: flex;
          align-items: center;
          height: 31px;
          font-size: 12px;
          line-height: 30px;
          background: rgba(250, 251, 253, 1);
          border-bottom: 1px solid rgba(221, 228, 235, 1);
        }

        /* stylelint-disable-next-line no-descending-specificity */
        .select-list .select-item {
          .field-name {
            // 16 42 50 38
            width: calc(100% - 146px);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }

          .status {
            font-weight: 700;

            &.icon-arrows-down-line {
              color: #ea3636;
            }

            &.icon-arrows-up-line {
              color: #2dcb56;
            }
          }

          .option {
            width: 50px;
            margin: 0 8px;
            color: #3a84ff;
          }

          .delete {
            font-size: 16px;
            color: #c4c6cc;
            text-align: right;
            cursor: pointer;
          }
        }
      }

      .sort-icon {
        display: flex;
        flex-shrink: 0;
        align-items: center;
        justify-content: center;
        width: 35px;

        .bklog-double-arrow {
          font-size: 12px;
          color: #989ca5;
        }
      }
    }

    .fields-button-container {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      width: 100%;
      height: 51px;
      padding: 0 24px;
      background-color: #fafbfd;
      border-top: 1px solid #dcdee5;
      border-radius: 0 0 2px 2px;
    }

    .field-alias-setting {
      position: absolute;
      top: 0px;
      right: 20px;
      display: flex;
      align-items: center;
      height: 42px;
    }
  }
</style>
