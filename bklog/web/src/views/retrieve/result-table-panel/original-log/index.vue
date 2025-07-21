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
  <div class="original-log-panel">
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
        <div class="field-select">
          <img
            class="icon-field-config"
            :src="require('@/images/icons/field-config.svg')"
          />
          <bk-select
            ref="configSelectRef"
            :clearable="false"
            :disabled="fieldConfigIsLoading"
            :popover-min-width="240"
            :value="filedSettingConfigID"
            size="small"
            searchable
            @selected="handleSelectFieldConfig"
          >
            <bk-option
              v-for="option in fieldsConfigList"
              :id="option.id"
              :key="option.id"
              :name="option.name"
            >
            </bk-option>
            <template #extension>
              <div>
                <span
                  class="extension-add-new-config"
                  @click="handleAddNewConfig"
                >
                  <span class="bk-icon icon-close-circle"></span>
                  <span>{{ $t('查看配置') }}</span>
                </span>
              </div>
            </template>
          </bk-select>
        </div>
      </div>
      <div class="tools-more">
        <div style="margin-right: 12px">
          <span class="switch-label">{{ $t('展开长字段') }}</span>
          <bk-switcher
            v-model="expandTextView"
            theme="primary"
            @change="handleChangeExpandView"
          />
        </div>
        <div>
          <span class="switch-label">{{ $t('换行') }}</span>
          <bk-switcher
            v-model="isWrap"
            theme="primary"
          ></bk-switcher>
        </div>
        <!-- <time-formatter v-show="!showOriginalLog" /> -->
        <div class="operation-icons">
          <export-log
            v-bind="$attrs"
            :async-export-usable="asyncExportUsable"
            :async-export-usable-reason="asyncExportUsableReason"
            :queue-status="queueStatus"
            :retrieve-params="retrieveParams"
            :total-count="totalCount"
          >
          </export-log>
          <bk-popover
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
                  :field-alias-map="$attrs['field-alias-map']"
                  :retrieve-params="retrieveParams"
                  @cancel="cancelModifyFields"
                  @confirm="confirmModifyFields"
                  @modify-fields="modifyFields"
                  @set-popper-instance="setPopperInstance"
                />
              </div>
            </template>
          </bk-popover>
        </div>
      </div>
    </div>

    <table-log
      v-bind="$attrs"
      v-on="$listeners"
      :is-wrap="isWrap"
      :retrieve-params="retrieveParams"
      :show-original="showOriginalLog"
    />
  </div>
</template>

<script>
import axios from 'axios';
import { mapGetters } from 'vuex';

import ExportLog from '../../result-comp/export-log.vue';
import FieldsSetting from '../../result-comp/fields-setting';
import TableLog from './table-log.vue';
const CancelToken = axios.CancelToken;

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
    configWatchBool: {
      type: Boolean,
      default: false,
    },
    isThollteField: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      contentType: 'table',
      isWrap: true,
      /** 是否是第一次加载字段列表 用于初始化原始日志，否则会导致操作列表失效 */
      isFirstInitFiled: false,
      showFieldsSetting: false,
      showAsyncExport: false, // 异步下载弹窗
      exportLoading: false,
      fieldsConfigList: [],
      fieldConfigIsLoading: false,
      expandTextView: false,
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
    watchQueryIndexValue() {
      return `${this.routeIndexSet}_${this.configWatchBool}`;
    },
    routeIndexSet() {
      return this.$route.params.indexId;
    },
    showFieldsConfigPopoverNum() {
      return this.$store.state.showFieldsConfigPopoverNum;
    },
  },
  watch: {
    watchQueryIndexValue: {
      handler() {
        if ((!this.isUnionSearch && this.routeIndexSet) || (this.isUnionSearch && this.unionIndexList?.length)) {
          this.requestFiledConfig();
        }
      },
    },
    isThollteField(v) {
      if (!v && !this.isFirstInitFiled) {
        this.isFirstInitFiled = true;
        this.contentType = localStorage.getItem('SEARCH_STORAGE_ACTIVE_TAB') || 'table';
      }
    },
    showFieldsConfigPopoverNum() {
      this.handleAddNewConfig();
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
      this.$emit('fields-updated', displayFieldNames, showFieldAlias);
      this.$emit('should-retrieve');
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
    async requestFiledConfig() {
      /** 获取配置列表 */
      this.fieldConfigIsLoading = true;
      try {
        const res = await this.$http.request(
          'retrieve/getFieldsListConfig',
          {
            data: {
              ...(this.isUnionSearch ? { index_set_ids: this.unionIndexList } : { index_set_id: this.routeIndexSet }),
              scope: 'default',
              index_set_type: this.isUnionSearch ? 'union' : 'single',
            },
          },
          {
            cancelToken: new CancelToken(c => {
              this.getFieldsConfigCancelFn = c;
            }),
          }
        );
        this.fieldsConfigList = res.data;
      } catch (error) {
      } finally {
        this.fieldConfigIsLoading = false;
      }
    },
    getFieldsConfigCancelFn() {},
    async handleSelectFieldConfig(configID, option) {
      const { display_fields: displayFields, sort_list: sortList } = option;
      // 更新config
      await this.$http
        .request('retrieve/postFieldsConfig', {
          data: {
            index_set_id: this.routeIndexSet,
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
      this.confirmModifyFields(displayFields, sortList);
    },
    handleAddNewConfig() {
      this.$refs.configSelectRef?.close();
      this.$refs.fieldsSettingPopper?.instance.show();
    },
    handleClickTableBtn(active = 'table') {
      this.contentType = active;
      localStorage.setItem('SEARCH_STORAGE_ACTIVE_TAB', active);
    },
    handleChangeExpandView(val) {
      this.$store.commit('updateStorage', { isLimitExpandView: val });
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
