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
    :style="{ height: `calc(100% - ${height + 12}px)` }"
    class="original-log-panel"
  >
    <div class="original-log-panel-tools">
      <div class="left-operate">
        <div class="bk-button-group">
          <bk-button
            :class="!showOriginalLog ? 'is-selected' : ''"
            size="small"
            @click="handleClickTableBtn('table')"
          >
            {{ $t('表格') }}
          </bk-button>
          <bk-button
            :class="showOriginalLog ? 'is-selected' : ''"
            size="small"
            @click="handleClickTableBtn('original')"
          >
            {{ $t('原始') }}
          </bk-button>
        </div>
        <bk-checkbox
          style="margin: 0 12px"
          class="bklog-option-item"
          :value="showRowIndex"
          theme="primary"
          @change="val => handleStorageChange(val, 'tableShowRowIndex')"
        >
          <span class="switch-label">{{ $t('显示行号') }}</span>
        </bk-checkbox>
        <bk-checkbox
          style="margin: 0 12px 0 0"
          class="bklog-option-item"
          :value="expandTextView"
          theme="primary"
          @change="val => handleStorageChange(val, 'isLimitExpandView')"
        >
          <span class="switch-label">{{ $t('展开长字段') }}</span>
        </bk-checkbox>
        <bk-checkbox
          style="margin: 0 12px 0 0"
          class="bklog-option-item"
          :value="isWrap"
          theme="primary"
          @change="val => handleStorageChange(val, 'tableLineIsWrap')"
          ><span class="switch-label">{{ $t('换行') }}</span></bk-checkbox
        >

        <bk-checkbox
          style="margin: 0 12px 0 0"
          class="bklog-option-item"
          :value="isJsonFormat"
          theme="primary"
          @change="val => handleStorageChange(val, 'tableJsonFormat')"
          ><span class="switch-label">{{ $t('JSON 解析') }}</span></bk-checkbox
        >

        <bk-input
          v-if="isJsonFormat"
          style="margin: 0 12px 0 0"
          class="json-depth-num"
          :max="15"
          :min="1"
          :value="jsonFormatDeep"
          type="number"
          @change="handleJsonFormatDeepChange"
        ></bk-input>

        <bk-checkbox
          style="margin: 0 12px 0 0"
          class="bklog-option-item"
          :value="isAllowEmptyField"
          theme="primary"
          @change="val => handleStorageChange(val, 'tableAllowEmptyField')"
        >
          <span class="switch-label">
            {{ $t('展示空字段') }}
          </span>
        </bk-checkbox>
      </div>
      <div class="tools-more">
        <div class="operation-icons">
          <export-log
            :index-set-list="indexSetList"
            :async-export-usable="asyncExportUsable"
            :async-export-usable-reason="asyncExportUsableReason"
            :queue-status="queueStatus"
            :retrieve-params="retrieveParams"
            :total-count="totalCount"
          >
          </export-log>
          <bk-popover
            v-if="!isMonitorTraceLog"
            ref="fieldsSettingPopper"
            :distance="15"
            :offset="0"
            :on-hide="handleDropdownHide"
            :on-show="handleDropdownShow"
            animation="slide-toggle"
            placement="bottom-end"
            theme="light bk-select-dropdown"
            trigger="click"
          >
            <slot name="trigger">
              <div class="operation-icon">
                <span class="icon bklog-icon bklog-set-icon"></span>
              </div>
            </slot>
            <template #content>
              <div class="fields-setting-container">
                <fields-setting
                  v-if="showFieldsSetting"
                  v-on="$listeners"
                  :field-alias-map="fieldAliasMap"
                  :retrieve-params="retrieveParams"
                  @cancel="cancelModifyFields"
                  @set-popper-instance="setPopperInstance"
                />
              </div>
            </template>
          </bk-popover>
        </div>
      </div>
    </div>

    <table-log
      :retrieve-params="retrieveParams"
      :show-original="showOriginalLog"
      :table-list="tableList"
    />
  </div>
</template>

<script>
  import { mapGetters, mapState } from 'vuex';
  // #if MONITOR_APP !== 'apm' && MONITOR_APP !== 'trace'
  import ExportLog from '../../result-comp/export-log.vue';
  // #else
  // #code const ExportLog = () => null;
  // #endif
  import FieldsSetting from '../../result-comp/fields-setting';
  import TableLog from './table-log.vue';

  export default {
    components: {
      TableLog,
      FieldsSetting,
      ExportLog,
    },
    inheritAttrs: false,
    props: {
      retrieveParams: {
        type: Object,
        required: true,
      },
      totalCount: {
        type: Number,
        default: 0,
      },
      queueStatus: {
        type: Boolean,
        default: true,
      },
      height: {
        type: Number,
      },
    },
    data() {
      return {
        contentType: 'table',
        showFieldsSetting: false,
        showAsyncExport: false, // 异步下载弹窗
        exportLoading: false,
        isInitActiveTab: false,
      };
    },
    computed: {
      showOriginalLog() {
        return this.contentType === 'original';
      },
      asyncExportUsable() {
        return this.$attrs['async-export-usable'];
      },
      asyncExportUsableReason() {
        return this.$attrs['async-export-usable-reason'];
      },
      filedSettingConfigID() {
        // 当前索引集的显示字段ID
        return this.$store.state.retrieve.filedSettingConfigID;
      },
      ...mapGetters({
        unionIndexList: 'unionIndexList',
        isUnionSearch: 'isUnionSearch',
      }),
      ...mapState({
        indexSetList: state => state.retrieve?.indexSetList ?? [],
        indexSetQueryResult: 'indexSetQueryResult',
        indexFieldInfo: 'indexFieldInfo',
        isWrap: state => state.storage.tableLineIsWrap,
        jsonFormatDeep: state => state.storage.tableJsonFormatDepth,
        isJsonFormat: state => state.storage.tableJsonFormat,
        isAllowEmptyField: state => state.storage.tableAllowEmptyField,
        showRowIndex: state => state.storage.tableShowRowIndex,
        expandTextView: state => state.storage.isLimitExpandView,
      }),

      routeIndexSet() {
        return window.__IS_MONITOR_COMPONENT__ ? this.$route.query.indexId : this.$route.params.indexId;
      },

      tableList() {
        return this.indexSetQueryResult.list ?? [];
      },

      fieldAliasMap() {
        return (this.indexFieldInfo.fields ?? []).reduce(
          (out, field) => ({ ...out, [field.field_name]: field.field_alias || field.field_name }),
          {},
        );
      },
      showFieldsConfigPopoverNum() {
        return this.$store.state.showFieldsConfigPopoverNum;
      },
      isMonitorApm() {
        return window.__IS_MONITOR_COMPONENT__;
      },
      isMonitorTraceLog() {
        return window?.__IS_MONITOR_TRACE__;
      },
    },
    watch: {
      showFieldsConfigPopoverNum() {
        this.handleAddNewConfig();
      },
    },
    mounted() {
      this.contentType = localStorage.getItem('SEARCH_STORAGE_ACTIVE_TAB') || 'table';
    },
    methods: {
      // 字段设置
      handleDropdownShow() {
        this.showFieldsSetting = true;
      },
      handleDropdownHide() {
        this.showFieldsSetting = false;
      },
      cancelModifyFields() {
        this.closeDropdown();
      },
      closeDropdown() {
        this.showFieldsSetting = false;
        this.$refs.fieldsSettingPopper?.instance.hide();
        this.$refs.fieldsSettingPopper?.instance.hide();
      },
      setPopperInstance(status = true) {
        this.$refs.fieldsSettingPopper?.instance.set({
          hideOnClick: status,
        });
      },
      handleAddNewConfig() {
        this.$refs.configSelectRef?.close();
        this.$refs.fieldsSettingPopper?.instance.show();
      },
      handleClickTableBtn(active = 'table') {
        this.contentType = active;
        localStorage.setItem('SEARCH_STORAGE_ACTIVE_TAB', active);
      },
      handleStorageChange(val, key) {
        this.$store.commit('updateStorage', { [key]: val });
      },
      handleJsonFormatDeepChange(val) {
        const value = Number(val);
        const target = value > 15 ? 15 : value < 1 ? 1 : value;
        this.$store.commit('updateStorage', { tableJsonFormatDepth: target });
      },
    },
  };
</script>

<style lang="scss" scoped>
  @import '@/scss/mixins/flex.scss';

  .original-log-panel {
    .original-log-panel-tools {
      display: flex;
      justify-content: space-between;
    }

    .tools-more {
      @include flex-center;

      .switch-label {
        margin-right: 2px;
        font-size: 12px;
        color: #63656e;
      }
    }

    .operation-icons {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-left: 16px;

      .operation-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;
        margin-left: 10px;
        cursor: pointer;
        border: 1px solid #c4c6cc;
        border-radius: 2px;
        outline: none;
        transition: boder-color 0.2s;

        &:hover {
          border-color: #979ba5;
          transition: boder-color 0.2s;
        }

        &:active {
          border-color: #3a84ff;
          transition: boder-color 0.2s;
        }

        .bklog-icon {
          width: 16px;
          font-size: 16px;
          color: #979ba5;
        }
      }

      .disabled-icon {
        cursor: not-allowed;
        background-color: #fff;
        border-color: #dcdee5;

        &:hover,
        .bklog-icon {
          color: #c4c6cc;
          border-color: #dcdee5;
        }
      }
    }

    .left-operate {
      flex-wrap: nowrap;
      align-items: center;

      @include flex-justify(space-between);

      > div {
        flex-shrink: 0;
      }

      .bklog-option-item {
        font-size: 12px;
        line-height: 20px;
        color: #63656e;
      }
    }

    .field-select {
      position: relative;
      width: 120px;
      margin-left: 16px;

      .icon-field-config {
        position: absolute;
        top: 4px;
        left: 4px;
        width: 18px;
      }

      :deep(.bk-select .bk-select-name) {
        padding: 0px 36px 0 30px;
      }
    }
  }

  .extension-add-new-config {
    cursor: pointer;

    @include flex-center();

    :last-child {
      margin-left: 4px;
      color: #63656e;
    }

    .icon-close-circle {
      margin-left: 4px;
      font-size: 14px;
      color: #979ba5;
      transform: rotateZ(45deg);
    }
  }
</style>
<style lang="scss">
  .json-depth-num {
    &.bk-form-control {
      width: 96px;

      .bk-input-number {
        input {
          &.bk-form-input {
            height: 26px;
          }
        }
      }
    }
  }
</style>
