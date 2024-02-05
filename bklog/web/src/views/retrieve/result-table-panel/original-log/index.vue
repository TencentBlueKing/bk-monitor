<!--
  - Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
  - Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
  - BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
  -
  - License for BK-LOG 蓝鲸日志平台:
  - -------------------------------------------------------------------
  -
  - Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
  - documentation files (the "Software"), to deal in the Software without restriction, including without limitation
  - the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
  - and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
  - The above copyright notice and this permission notice shall be included in all copies or substantial
  - portions of the Software.
  -
  - THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
  - LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
  - NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
  - WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
  - SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
  -->

<template>
  <div class="original-log-panel">
    <div class="original-log-panel-tools">
      <div class="left-operate">
        <div class="bk-button-group">
          <bk-button
            :class="!showOriginalLog ? 'is-selected' : ''"
            @click="contentType = 'table'"
            size="small">
            {{ $t('表格') }}
          </bk-button>
          <bk-button
            :class="showOriginalLog ? 'is-selected' : ''"
            @click="contentType = 'original'"
            size="small">
            {{ $t('原始') }}
          </bk-button>
        </div>
        <div class="field-select">
          <img class="icon-field-config" :src="require('@/images/icons/field-config.svg')" />
          <bk-select
            size="small"
            searchable
            ref="configSelectRef"
            :clearable="false"
            :value="filedSettingConfigID"
            :popover-min-width="240"
            @selected="handleSelectFieldConfig">
            <bk-option
              v-for="option in fieldsConfigList"
              :key="option.id"
              :id="option.id"
              :name="option.name">
            </bk-option>
            <div slot="extension">
              <span class="extension-add-new-config" @click="handleAddNewConfig">
                <span class="bk-icon icon-close-circle"></span>
                <span>{{$t('新建配置')}}</span>
              </span>
            </div>
          </bk-select>
        </div>
      </div>
      <div class="tools-more">
        <div :style="`margin-right: ${showOriginalLog ? 0 : 26}px`">
          <span class="switch-label">{{ $t('换行') }}</span>
          <bk-switcher v-model="isWrap" theme="primary"></bk-switcher>
        </div>
        <!-- <time-formatter v-show="!showOriginalLog" /> -->
        <div class="operation-icons">
          <export-log
            v-bind="$attrs"
            :retrieve-params="retrieveParams"
            :total-count="totalCount"
            :queue-status="queueStatus"
            :async-export-usable="asyncExportUsable"
            :async-export-usable-reason="asyncExportUsableReason">
          </export-log>
          <bk-popover
            v-if="!showOriginalLog"
            ref="fieldsSettingPopper"
            trigger="click"
            placement="bottom-end"
            theme="light bk-select-dropdown"
            animation="slide-toggle"
            :offset="0"
            :distance="15"
            :on-show="handleDropdownShow"
            :on-hide="handleDropdownHide">
            <slot name="trigger">
              <div class="operation-icon">
                <span class="icon log-icon icon-set-icon"></span>
              </div>
            </slot>
            <div slot="content" class="fields-setting-container">
              <fields-setting
                v-if="showFieldsSetting"
                v-on="$listeners"
                :field-alias-map="$attrs['field-alias-map']"
                :retrieve-params="retrieveParams"
                @setPopperInstance="setPopperInstance"
                @modifyFields="modifyFields"
                @confirm="confirmModifyFields"
                @cancel="cancelModifyFields" />
            </div>
          </bk-popover>
        </div>
      </div>
    </div>

    <table-log
      v-bind="$attrs"
      v-on="$listeners"
      :is-wrap="isWrap"
      :show-original="showOriginalLog"
      :retrieve-params="retrieveParams" />
  </div>
</template>

<script>
import TableLog from './table-log.vue';
import FieldsSetting from '../../result-comp/fields-setting';
import ExportLog from '../../result-comp/export-log.vue';

export default {
  components: {
    TableLog,
    FieldsSetting,
    ExportLog,
  },
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
  },
  data() {
    return {
      contentType: 'table',
      isWrap: true,
      showFieldsSetting: false,
      showAsyncExport: false, // 异步下载弹窗
      exportLoading: false,
      fieldsConfigList: [],
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
    filedSettingConfigID() { // 当前索引集的显示字段ID
      return this.$store.state.retrieve.filedSettingConfigID;
    },
    routeIndexSet() {
      return this.$route.params.indexId;
    },
  },
  watch: {
    routeIndexSet: {
      immediate: true,
      handler(val) {
        if (!!val) this.requestFiledConfig();
      },
    },
  },
  methods: {
    // 字段设置
    handleDropdownShow() {
      this.showFieldsSetting = true;
    },
    handleDropdownHide() {
      this.showFieldsSetting = false;
      this.requestFiledConfig();
    },
    confirmModifyFields(displayFieldNames, showFieldAlias) {
      this.modifyFields(displayFieldNames, showFieldAlias);
      this.closeDropdown();
    },
    cancelModifyFields() {
      this.closeDropdown();
    },
    /** 更新显示字段 */
    modifyFields(displayFieldNames, showFieldAlias) {
      this.$emit('fieldsUpdated', displayFieldNames, showFieldAlias);
      this.$emit('shouldRetrieve');
    },
    closeDropdown() {
      this.showFieldsSetting = false;
      this.$refs.fieldsSettingPopper?.instance.hide();
    },
    setPopperInstance(status = true) {
      this.$refs.fieldsSettingPopper?.instance.set({
        hideOnClick: status,
      });
    },
    async requestFiledConfig() {
      /** 获取配置列表 */
      this.isLoading = true;
      try {
        const res = await this.$http.request('retrieve/getFieldsListConfig', {
          params: { index_set_id: this.routeIndexSet, scope: 'default' },
        });
        this.fieldsConfigList = res.data;
      } catch (error) {
      } finally {
        this.isLoading = false;
      }
    },
    async handleSelectFieldConfig(configID, option) {
      const { display_fields: displayFields, sort_list: sortList } = option;
      // 更新config
      await this.$http
        .request('retrieve/postFieldsConfig', {
          params: { index_set_id: this.$route.params.indexId },
          data: {
            display_fields: displayFields,
            sort_list: sortList,
            config_id: configID,
          },
        })
        .catch((e) => {
          console.warn(e);
        });
      this.$store.commit('updateClearTableWidth', 1);
      this.confirmModifyFields(displayFields, sortList);
    },
    handleAddNewConfig() {
      this.$refs.configSelectRef?.close();
      this.$refs.fieldsSettingPopper?.instance.show();
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
        color: #63656e;
        font-size: 12px;
      }
    }

    .operation-icons {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-left: 16px;

      .operation-icon {
        display: flex;
        justify-content: center;
        align-items: center;
        width: 32px;
        height: 32px;
        margin-left: 10px;
        cursor: pointer;
        border: 1px solid #c4c6cc;
        transition: boder-color .2s;
        border-radius: 2px;
        outline: none;

        &:hover {
          border-color: #979ba5;
          transition: boder-color .2s;
        }

        &:active {
          border-color: #3a84ff;
          transition: boder-color .2s;
        }

        .log-icon {
          width: 16px;
          font-size: 16px;
          color: #979ba5;
        }
      }

      .disabled-icon {
        background-color: #fff;
        border-color: #dcdee5;
        cursor: not-allowed;

        &:hover,
        .log-icon {
          border-color: #dcdee5;
          color: #c4c6cc;
        }
      }
    }

    .left-operate {
      align-items: center;
      flex-wrap: nowrap;

      @include flex-justify(space-between);

      > div {
        flex-shrink: 0;
      }
    }

    .field-select {
      width: 120px;
      margin-left: 16px;
      position: relative;

      .icon-field-config {
        width: 18px;
        position: absolute;
        top: 4px;
        left: 4px;
      }

      :deep(.bk-select .bk-select-name) {
        padding: 0px 36px 0 30px
      }
    }
  }

  .extension-add-new-config {
    cursor: pointer;

    @include flex-center();

    :last-child {
      color: #63656e;
      margin-left: 4px;
    }

    .icon-close-circle {
      margin-left: 4px;
      font-size: 14px;
      color: #979ba5;
      transform: rotateZ(45deg);
    }
  }
</style>
