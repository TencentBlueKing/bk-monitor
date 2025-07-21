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
  <bk-dialog
    :close-icon="false"
    :loading="confirmLoading"
    :mask-close="false"
    :position="{ top: '120' }"
    :title="dialogTitle"
    :value="visible"
    :width="800"
    header-position="left"
    @cancel="closeDialog"
    @confirm="handleConfirm"
  >
    <div
      class="link-config-form"
      data-test-id="addNewLinkConfig_div_linkConfigForm"
    >
      <bk-form
        ref="form"
        class="king-form"
        :label-width="220"
        :model="formData"
        :rules="rules"
      >
        <bk-form-item
          :label="$t('链路名称')"
          error-display-type="normal"
          property="link_group_name"
          required
        >
          <bk-input
            style="width: 380px"
            v-model="formData.link_group_name"
            :clearable="true"
            data-test-id="linkConfigForm_div_linkName"
          ></bk-input>
        </bk-form-item>
        <bk-form-item
          :label="$t('允许的空间')"
          error-display-type="normal"
          property="bk_biz_id"
          required
        >
          <bk-select
            ref="selectRef"
            style="width: 380px"
            v-model="formData.bk_biz_id"
            :clearable="false"
            :list="projectList"
            :virtual-scroll-render="virtualscrollSpaceList"
            data-test-id="linkConfigForm_select_selectPermitted"
            display-key="space_full_code_name"
            id-key="bk_biz_id"
            enable-virtual-scroll
            searchable
          >
          </bk-select>
        </bk-form-item>
        <bk-form-item
          error-display-type="normal"
          label="Kafka"
          property="kafka_cluster_id"
          required
        >
          <bk-select
            style="width: 380px"
            v-model="formData.kafka_cluster_id"
            :clearable="false"
            data-test-id="linkConfigForm_select_selectKafka"
          >
            <template>
              <bk-option
                v-for="item in selectData.kafka"
                :id="item.cluster_id"
                :key="item.cluster_id"
                :name="item.cluster_name"
              >
              </bk-option>
            </template>
          </bk-select>
        </bk-form-item>
        <bk-form-item
          error-display-type="normal"
          label="Transfer"
          property="transfer_cluster_id"
          required
        >
          <bk-select
            style="width: 380px"
            v-model="formData.transfer_cluster_id"
            :clearable="false"
            data-test-id="linkConfigForm_select_selectTransfer"
          >
            <template>
              <bk-option
                v-for="item in selectData.transfer"
                :id="item.cluster_id"
                :key="item.cluster_id"
                :name="item.cluster_name"
              >
              </bk-option>
            </template>
          </bk-select>
        </bk-form-item>
        <bk-form-item
          :label="$t('ES集群')"
          error-display-type="normal"
          property="es_cluster_ids"
          required
        >
          <bk-select
            style="width: 380px"
            v-model="formData.es_cluster_ids"
            :clearable="false"
            data-test-id="linkConfigForm_select_selectEsClusterIds"
            multiple
          >
            <template>
              <bk-option
                v-for="item in selectData.es"
                :id="item.cluster_id"
                :key="item.cluster_id"
                :name="item.cluster_name"
              >
              </bk-option>
            </template>
          </bk-select>
        </bk-form-item>
        <bk-form-item
          :label="$t('是否启用')"
          error-display-type="normal"
          property="is_active"
        >
          <bk-checkbox
            v-model="formData.is_active"
            data-test-id="linkConfigForm_checkbox_isEnable"
          ></bk-checkbox>
        </bk-form-item>
        <bk-form-item
          :label="$t('备注')"
          error-display-type="normal"
          property="description"
        >
          <bk-input
            style="width: 380px"
            v-model="formData.description"
            :clearable="true"
            :maxlength="64"
            data-test-id="linkConfigForm_input_Remark"
            type="textarea"
          >
          </bk-input>
        </bk-form-item>
      </bk-form>
    </div>
  </bk-dialog>
</template>

<script>
import SpaceSelectorMixin from '@/mixins/space-selector-mixin';

export default {
  mixins: [SpaceSelectorMixin],
  props: {
    visible: {
      type: Boolean,
      default: false,
    },
    type: {
      type: String,
      default: 'create',
    },
    projectList: {
      type: Array,
      required: true,
    },
    dataSource: {
      type: Object,
      default() {
        return {};
      },
    },
    selectData: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      dialogTitle: '',
      confirmLoading: false,
      formData: {},
      rules: {
        link_group_name: [
          {
            required: true,
            message: this.$t('必填项'),
            trigger: 'blur',
          },
        ],
        bk_biz_id: [
          {
            required: true,
            message: this.$t('必填项'),
            trigger: 'blur',
          },
        ],
        kafka_cluster_id: [
          {
            required: true,
            message: this.$t('必填项'),
            trigger: 'blur',
          },
        ],
        transfer_cluster_id: [
          {
            required: true,
            message: this.$t('必填项'),
            trigger: 'blur',
          },
        ],
        es_cluster_ids: [
          {
            required: true,
            message: this.$t('必填项'),
            trigger: 'blur',
          },
        ],
      },
      spaceMultiple: false,
      isUseMark: false,
    };
  },
  watch: {
    visible(val) {
      if (val) {
        this.dialogTitle = this.type === 'create' ? this.$t('新建链路配置') : this.$t('编辑链路配置');
        this.formData = JSON.parse(JSON.stringify(this.dataSource));
        this.$refs.form.clearError();
      }
    },
  },
  methods: {
    handleSelectSpaceChange(bkBiz) {
      this.formData.bk_biz_id = bkBiz;
      this.$refs.selectRef?.close();
    },
    async handleConfirm() {
      try {
        this.confirmLoading = true;
        await this.$refs.form.validate();
        const formData = { ...this.formData };
        formData.bk_biz_id = Number(formData.bk_biz_id);
        if (this.type === 'create') {
          // 新建
          await this.$http.request('linkConfiguration/createLink', {
            data: formData,
          });
          this.messageSuccess(this.$t('创建成功'));
        } else {
          // 编辑
          await this.$http.request('linkConfiguration/updateLink', {
            data: formData,
            params: {
              data_link_id: this.formData.data_link_id,
            },
          });
          this.messageSuccess(this.$t('修改成功'));
        }
        this.$emit('show-update-list');
        this.closeDialog();
      } catch (e) {
        console.warn(e);
        await this.$nextTick();
        this.$emit('update:visible', true);
      } finally {
        this.confirmLoading = false;
      }
    },
    closeDialog() {
      // 通过父组件关闭对话框
      this.$emit('update:visible', false);
    },
  },
};
</script>

<style lang="scss" scoped>
  .link-config-form {
    :deep(.bk-form-content) {
      position: relative;

      .form-error-tip {
        position: absolute;
        top: 32px;
        margin: 0;
      }
    }
  }
</style>

<style lang="scss">
  @import '@/scss/space-tag-option';
</style>
