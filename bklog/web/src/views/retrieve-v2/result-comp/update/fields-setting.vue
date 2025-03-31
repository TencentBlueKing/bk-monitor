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
    class="update-fields-setting"
    v-bkloading="{ isLoading: isLoading }"
  >
    <!-- 设置列表字段 -->
    <div class="fields-container">
      <div
        v-if="isShowLeft"
        class="fields-config-container"
      >
        <div class="config-container-header">
          <div
            class="header-config-operation"
            v-show="!isShowAddInput"
          >
            <bk-button
              class="config-btn"
              :text="true"
              @click="handleClickAddNew"
            >
              <i class="bk-icon icon-plus-circle-shape" />
              <span>{{ $t('新建') }}</span>
            </bk-button>
            <log-export
              class="config-btn"
              @change="handleFieldConfigImport"
            >
              <i class="bk-icon bklog-icon bklog-import" />
              <span>{{ $t('导入') }}</span>
            </log-export>
          </div>
          <div
            class="header-config-new-input"
            v-show="isShowAddInput"
          >
            <bk-input
              v-model="newConfigStr"
              :class="['config-new-input', { 'input-error': isInputError }]"
              size="small"
            >
            </bk-input>
            <div class="new-input-operation">
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
        </div>
        <bk-tab
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
          <div class="show-field">
            <div class="text-type">字段显示：</div>
            <fieldSetting
              ref="fieldSettingRef"
              :init-data="shadowVisible"
            />
          </div>
          <div
            v-if="!isShowLeft"
            style="padding-left: 12px"
            class="table-sort"
          >
            <div class="text-type">表格排序：</div>
            <tableSort
              ref="tableSortRef"
              style="max-height: 340px; overflow: scroll"
              :init-data="shadowSort"
            />
          </div>
        </div>
      </div>
    </div>
    <div
      :style="{ 'justify-content': !isShowLeft ? 'space-between' : 'flex-end' }"
      class="fields-button-container"
    >
      <div
        v-if="!isShowLeft"
        style="color: #4d4f56"
      >
        <span
          style="font-size: 14px"
          class="bklog-icon bklog-help"
        ></span>
        当前设置仅对个人生效，可以
        <span style="color: #3a84ff"
          ><span
            style="margin-right: 4px; font-size: 14px"
            class="bklog-icon bklog-save"
          ></span
          >另存为模板</span
        >
        <span>，也可以使用 <span style="color: #3a84ff">其他模板</span></span>
      </div>
      <div>
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
  </div>
</template>

<script>
  import { random, downJsonFile } from '@/common/util';
  import { getFieldNameByField } from '@/hooks/use-field-name';
  import VueDraggable from 'vuedraggable';
  import { mapGetters } from 'vuex';

  import LogExport from '../../../../components/log-import/log-import';
  import fieldSetting from './field-setting';
  import fieldsSettingOperate from './fields-setting-operate';
  import tableSort from './table-sort';

  /** 导出配置字段文件名前缀 */
  const FIELD_CONFIG_FILENAME_PREFIX = 'log-field-';

  export default {
    components: {
      // eslint-disable-next-line vue/no-unused-components
      VueDraggable,
      fieldSetting,
      tableSort,
      LogExport,
    },
    props: {
      retrieveParams: {
        type: Object,
        required: true,
      },
      isShowLeft: {
        type: Boolean,
        default: false,
      },
    },
    data() {
      return {
        isLoading: false,
        tableSortRef: null,
        fieldSettingRef: null,
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
        return this.$store.state.showFieldAlias;
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
      this.currentClickConfigID = this.filedSettingConfigID;
      this.initRequestConfigListShow();
    },
    mounted() {
      window.addEventListener('click', this.handleDocumentClick);
    },
    unmounted() {
      window.removeEventListener('click', this.handleDocumentClick);
    },
    methods: {
      handleDocumentClick(e) {
        if (e.target?.closest?.('.bklog-v3-popover-tag')) {
          return;
        }

        if (!this.$el.contains(e.target)) {
          this.$emit('cancel');
        }
      },
      getFiledDisplayByFieldName(name) {
        const field = this.shadowTotal.find(item => item.field_name === name);
        return this.getFiledDisplay(field);
      },
      getFiledDisplay(field) {
        if (this.showFieldAlias) {
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
        const currentSortList = this.$refs?.tableSortRef?.shadowSort || this.shadowSort;
        const currentVisibleList = this.$refs.fieldSettingRef.shadowVisible.map(item => item.field_name);

        if (currentVisibleList.length === 0) {
          this.messageWarn(this.$t('显示字段不能为空'));
          return;
        }
        try {
          const confirmConfigData = {
            editStr: this.currentClickConfigData.name,
            sort_list: currentSortList,
            display_fields: currentVisibleList,
            id: this.currentClickConfigData.id,
          };
          this.isConfirmSubmit = true;
          await this.handleUpdateConfig(confirmConfigData);
          // 判断当前应用的config_id 与 索引集使用的config_id是否相同 不同则更新config
          if (this.currentClickConfigData.id !== this.filedSettingConfigID) {
            await this.submitFieldsSet(this.currentClickConfigData.id);
          }
          this.cancelModifyFields();
          // this.$store.commit('updateShowFieldAlias', this.showFieldAlias);
          this.$store.commit('updateIsSetDefaultTableColumn', false);
          this.$store
            .dispatch('userFieldConfigChange', {
              displayFields: currentVisibleList,
              fieldsWidth: {},
            })
            .then(() => {
              this.$store.commit('resetVisibleFields', currentVisibleList);
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
            hasMoreIcon: index !== 0,
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
            this.handleUpdateConfig(configItem, false, this.$t('修改成功'));
            break;
          case 'cancel':
            this.handleCancelEditConfig(configItem.index);
            break;
          case 'export':
            this.handleFieldConfigExport(configItem);
            break;
        }
      },

      /**
       * @description 导入字段配置
       * @param fieldContent 导入文件的内容
       *
       */
      handleFieldConfigImport(fieldContent) {
        try {
          const fieldConfig = JSON.parse(fieldContent);
          fieldConfig.editStr = `导入模板-${random(3)}`;
          this.handleUpdateConfig(fieldConfig, true, this.$t('导入成功'));
        } catch (error) {
          this.messageWarn(this.$t('请导入正确的JSON格式文件~'));
          return;
        }
      },

      /**
       * @description 导出选中字段配置为 JSON 文件
       *
       */
      handleFieldConfigExport(updateItem) {
        let fieldName = `${updateItem.name}`;
        const fieldConfigParam = {
          name: fieldName,
          sort_list: updateItem.sort_list,
          display_fields: updateItem.display_fields,
          config_id: undefined,
          index_set_id: window.__IS_MONITOR_COMPONENT__ ? this.$route.query.indexId : this.$route.params.indexId,
          index_set_ids: this.unionIndexList,
          index_set_type: this.isUnionSearch ? 'union' : 'single',
        };
        downJsonFile(JSON.stringify(fieldConfigParam, null, 4), `${FIELD_CONFIG_FILENAME_PREFIX}${fieldName}.json`);
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
        this.handleUpdateConfig(configValue, true, this.$t('修改成功'));
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
      async handleUpdateConfig(updateItem, isCreate = false, successMsg) {
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
          successMsg && this.messageInfo(successMsg);
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
            // this.$store.commit('updateShowFieldAlias', this.showFieldAlias);
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
  @import '../../../../scss/mixins/scroller';

  .update-fields-setting {
    position: relative;
    background: #ffffff;
    border: 1px solid #dcdee5;
    border-radius: 2px;
    box-shadow: 0 2px 6px 0 #0000001a;

    .fields-container {
      display: flex;

      .fields-config-container {
        width: 150px;
        background-color: #f5f7fa;
        border-right: 1px solid #dcdee5;
        %config-input-common {
          width: 100%;
        }

        .config-container-header {
          display: flex;
          align-items: center;
          justify-content: center;
          height: 42px;

          .header-config-operation {
            display: flex;
            column-gap: 12px;
            margin-top: 3px;
            color: #3a84ff;
            cursor: pointer;

            .config-btn {
              height: 100%;
              line-height: 100%;

              .bk-icon {
                transform: translateY(-2px);
              }
            }
          }

          .header-config-new-input {
            --config-padding: 4px;
            position: relative;
            padding: 0 var(--config-padding);

            .config-new-input {
              @extend %config-input-common;
            }

            .new-input-operation {
              position: absolute;
              right: var(--config-padding);
              bottom: calc(100% + 2px);

              .bk-icon {
                display: inline-block;
                width: 28px;
                height: 28px;
                font-size: 18px;
                line-height: 28px;
                cursor: pointer;
                background: #fafbfd;
                border: 1px solid #dcdee5;
                border-radius: 2px;
                box-shadow: 0 1px 3px 1px #0000001f;

                &:hover {
                  background: #f0f1f5;
                }
              }

              .icon-check-line {
                color: hsl(143, 60%, 43%);
              }

              .icon-close-line-2 {
                color: hsl(0, 81%, 56%);
              }
            }
          }
        }

        .bk-tab-label-list-has-bar::after {
          display: none !important;
        }

        .config-tab {
          width: 100%;
          height: calc(100% - 43px);

          :deep(.bk-tab-header) {
            padding: 0px;
            background-color: #f5f7fa;
          }
        }

        :deep(.bk-tab-label) {
          width: 100%;
        }

        :deep(.bk-tab-label-item) {
          padding: 0;

          /* stylelint-disable-next-line declaration-no-important */
          line-height: 36px !important;
          text-align: left;

          .bk-tab-label {
            font-size: 12px;
            color: #4d4f56;
          }

          &:hover {
            background: #eaebf0;
          }

          &.active {
            /* stylelint-disable-next-line declaration-no-important */
            background: #e1ecff !important;

            .bk-tab-label {
              color: #3a84ff;
            }
          }
        }

        :deep(.bk-tab-header) {
          width: 100%;
          min-width: 150px;
          padding: 0 0 10px;
          // &::after {
          //   display: none;
          // }
          &::before {
            display: none;
          }
        }

        :deep(.bk-tab-section) {
          display: none;
        }
      }
    }

    .fields-tab-container {
      display: flex;
      max-width: 930px;
      padding: 12px 16px 0px 16px;

      .show-field {
        width: 587px;
      }

      .table-sort {
        flex: 1;
      }

      .text-type {
        margin-bottom: 8px;
        font-family: MicrosoftYaHei;
        font-size: 14px;
        line-height: 22px;
        color: #313238;
      }
    }

    .fields-button-container {
      display: flex;
      align-items: center;

      width: 100%;
      height: 51px;
      padding: 0 24px;
      background-color: #fafbfd;
      border-top: 1px solid #dcdee5;
      border-radius: 0 0 2px 2px;
    }
  }
</style>
<style lang="scss">
  .update-fields-setting {
    .fields-config-container {
      .input-error {
        .bk-form-input {
          border: 1px solid #d7473f;
        }
      }

      .config-tab {
        .bk-tab-label-list-has-bar::after {
          display: none;
        }
      }
    }
  }
</style>
