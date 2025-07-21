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
    ref="addNewCustomBoxRef"
    :style="`padding-right: ${introWidth + 20}px;`"
    class="custom-create-container"
    v-bkloading="{ isLoading: containerLoading }"
    data-test-id="custom_div_addNewCustomBox"
  >
    <bk-form
      ref="validateForm"
      :label-width="getLabelWidth"
      :model="formData"
    >
      <div class="create-form">
        <div class="form-title">{{ $t('基础信息') }}</div>
        <!-- 数据ID -->
        <bk-form-item
          v-if="isEdit"
          :label="$t('数据ID')"
          :property="'bk_data_id'"
          required
        >
          <bk-input
            class="form-input"
            v-model="formData.bk_data_id"
            disabled
          >
          </bk-input>
        </bk-form-item>
        <!-- <bk-form-item :label="$t('数据token')" required :property="'name'">
          <bk-input class="form-input" :disabled="true" v-model="formData.name"></bk-input>
        </bk-form-item> -->
        <!-- 数据名称 -->
        <bk-form-item
          :disabled="submitLoading"
          :label="$t('数据名称')"
          :property="'collector_config_name'"
          :rules="baseRules.collector_config_name"
          required
        >
          <bk-input
            class="form-input"
            v-model="formData.collector_config_name"
            data-test-id="addNewCustomBox_input_dataName"
            maxlength="50"
            show-word-limit
          ></bk-input>
        </bk-form-item>
        <!-- 数据类型 -->
        <bk-form-item
          :label="$t('数据类型')"
          :property="'name'"
          required
        >
          <div style="min-width: 500px; margin-top: -4px">
            <div class="bk-button-group">
              <bk-button
                v-for="(item, index) of globalsData.databus_custom"
                :class="`${formData.custom_type === item.id ? 'is-selected' : ''}`"
                :data-test-id="`addNewCustomBox_button_typeTo${item.id}`"
                :disabled="isEdit"
                :key="index"
                size="small"
                @click="handleChangeType(item.id)"
              >
                {{ item.name }}
              </bk-button>
            </div>
            <p
              class="group-tip"
              slot="tip"
            >
              {{
                $t(
                  '自定义上报数据，可以通过采集器，或者指定协议例如otlp等方式进行上报，自定义上报有一定的使用要求，具体可以查看使用说明',
                )
              }}
            </p>
          </div>
        </bk-form-item>
        <bk-form-item
          ext-cls="en-bk-form"
          :icon-offset="120"
          :label="$t('数据名')"
          :property="'collector_config_name_en'"
          :rules="baseRules.collector_config_name_en"
          required
        >
          <div class="en-name-box">
            <div>
              <bk-input
                class="form-input"
                v-model="formData.collector_config_name_en"
                :disabled="submitLoading || isEdit"
                :placeholder="$t('支持数字、字母、下划线，长短5～50字符')"
                data-test-id="addNewCustomBox_input_englishName"
                maxlength="50"
                show-word-limit
              ></bk-input>
              <span
                v-if="!isTextValid"
                class="text-error"
                >{{ formData.collector_config_name_en }}</span
              >
            </div>
            <span v-bk-tooltips.top="$t('自动转换成正确的数据名格式')">
              <bk-button
                v-if="!isTextValid"
                text
                @click="handleEnConvert"
                >{{ $t('自动转换') }}</bk-button
              >
            </span>
          </div>
        </bk-form-item>
        <!-- 数据分类 -->
        <bk-form-item
          :label="$t('数据分类')"
          :property="'category_id'"
          :rules="baseRules.category_id"
          required
        >
          <bk-select
            style="width: 500px"
            v-model="formData.category_id"
            :disabled="submitLoading"
            data-test-id="addNewCustomBox_select_selectDataCategory"
          >
            <template>
              <bk-option-group
                v-for="(item, index) in globalsData.category"
                :id="item.id"
                :key="index"
                :name="item.name"
              >
                <bk-option
                  v-for="(option, key) in item.children"
                  :id="option.id"
                  :key="key"
                  :name="`${item.name}-${option.name}`"
                >
                  {{ option.name }}
                </bk-option>
              </bk-option-group>
            </template>
          </bk-select>
        </bk-form-item>
        <bk-form-item :label="$t('说明')">
          <bk-input
            class="form-input"
            v-model="formData.description"
            :disabled="submitLoading"
            :maxlength="100"
            :placeholder="$t('未输入')"
            data-test-id="addNewCustomBox_input_description"
            type="textarea"
          ></bk-input>
        </bk-form-item>
      </div>
      <!-- 存储设置 -->
      <div class="create-form">
        <div class="form-title">{{ $t('存储设置') }}</div>
        <!-- 存储集群 -->
        <bk-form-item
          :label="$t('存储集群')"
          :property="'data_link_id'"
          required
        >
          <cluster-table
            :is-change-select="true"
            :storage-cluster-id.sync="formData.storage_cluster_id"
            :table-list="clusterList"
          />
          <cluster-table
            style="margin-top: 20px"
            :is-change-select="true"
            :storage-cluster-id.sync="formData.storage_cluster_id"
            :table-list="exclusiveList"
            table-type="exclusive"
          />
        </bk-form-item>
        <!-- 数据链路 -->
        <bk-form-item
          v-if="!isCloseDataLink"
          :label="$t('数据链路')"
          :property="'data_link_id'"
          :rules="storageRules.data_link_id"
          required
        >
          <bk-select
            style="width: 500px"
            v-model="formData.data_link_id"
            :clearable="false"
            :disabled="submitLoading || isEdit"
            data-test-id="addNewCustomBox_select_selectDataLink"
          >
            <bk-option
              v-for="item in linkConfigurationList"
              :id="item.data_link_id"
              :key="item.data_link_id"
              :name="item.link_group_name"
            >
            </bk-option>
          </bk-select>
        </bk-form-item>
        <!-- 索引集名称 -->
        <bk-form-item
          class="form-inline-div"
          :label="$t('索引名')"
          :property="'table_id'"
          :rules="storageRules.table_id"
        >
          <bk-input
            style="width: 500px"
            v-model="formData.collector_config_name_en"
            :placeholder="$t('英文或者数字，5～50长度')"
            data-test-id="addNewCustomBox_input_configName"
            maxlength="50"
            minlength="5"
            disabled
          >
            <template #prepend>
              <div class="group-text">{{ showGroupText }}</div>
            </template>
          </bk-input>
        </bk-form-item>
        <!-- 过期时间 -->
        <bk-form-item :label="$t('过期时间')">
          <bk-select
            style="width: 500px"
            v-model="formData.retention"
            :clearable="false"
            :disabled="submitLoading"
            data-test-id="addNewCustomBox_select_expireDate"
          >
            <template #trigger>
              <div class="bk-select-name">
                {{ formData.retention + $t('天') }}
              </div>
            </template>
            <template>
              <bk-option
                v-for="(option, index) in retentionDaysList"
                :id="option.id"
                :key="index"
                :name="option.name"
              ></bk-option>
            </template>
            <template #extension>
              <div style="padding: 8px 0">
                <bk-input
                  v-model="customRetentionDay"
                  :placeholder="$t('输入自定义天数，按 Enter 确认')"
                  :show-controls="false"
                  size="small"
                  type="number"
                  @enter="enterCustomDay($event, 'retention')"
                ></bk-input>
              </div>
            </template>
          </bk-select>
        </bk-form-item>
        <!-- 副本数 -->
        <bk-form-item :label="$t('副本数')">
          <bk-input
            class="copy-number-input"
            v-model="formData.storage_replies"
            :clearable="false"
            :disabled="submitLoading"
            :max="replicasMax"
            :min="0"
            :precision="0"
            :show-controls="true"
            data-test-id="addNewCustomBox_input_copyNumber"
            type="number"
            @blur="changeCopyNumber"
          ></bk-input>
        </bk-form-item>
        <!-- 分片数 -->
        <bk-form-item :label="$t('分片数')">
          <bk-input
            class="copy-number-input"
            v-model="formData.es_shards"
            :clearable="false"
            :disabled="submitLoading"
            :max="shardsMax"
            :min="1"
            :precision="0"
            :show-controls="true"
            type="number"
            @blur="changeShardsNumber"
          ></bk-input>
        </bk-form-item>
        <!-- 热数据\冷热集群存储期限 -->
        <bk-form-item
          v-if="selectedStorageCluster.enable_hot_warm"
          class="hot-data-form-item"
          :label="$t('热数据天数')"
        >
          <bk-select
            style="width: 320px"
            v-model="formData.allocation_min_days"
            :clearable="false"
            :disabled="!selectedStorageCluster.enable_hot_warm"
            data-test-id="addNewCustomBox_select_selectHotData"
          >
            <template>
              <bk-option
                v-for="(option, index) in hotDataDaysList"
                :id="option.id"
                :key="index"
                :name="option.name"
              ></bk-option>
            </template>
            <template #extension>
              <div style="padding: 8px 0">
                <bk-input
                  v-model="customHotDataDay"
                  :placeholder="$t('输入自定义天数，按 Enter 确认')"
                  :show-controls="false"
                  data-test-id="storageBox_input_customize"
                  size="small"
                  type="number"
                  @enter="enterCustomDay($event, 'hot')"
                ></bk-input>
              </div>
            </template>
          </bk-select>
          <span
            v-if="!selectedStorageCluster.enable_hot_warm"
            class="disable-tips"
          >
            {{ $t('该集群未开启热数据设置') }}
            <a
              href="javascript:void(0);"
              @click="jumpToEsAccess"
              >{{ $t('前往ES源进行设置') }}</a
            >
          </span>
        </bk-form-item>
      </div>
      <FieldSetting
        v-if="isEdit"
        ref="fieldSettingRef"
        v-model="fieldSettingData"
      ></FieldSetting>
    </bk-form>
    <div
      :style="`width: ${introWidth}px`"
      :class="['intro-container', isDraging && 'draging-move']"
    >
      <div
        :style="`right: ${introWidth - 18}px`"
        :class="`drag-item ${!introWidth && 'hidden-drag'}`"
      >
        <span
          class="bk-icon icon-more"
          @mousedown.left="dragBegin"
        ></span>
      </div>
      <intro-panel
        :data="formData"
        :is-open-window="isOpenWindow"
        @handle-active-details="handleActiveDetails"
      />
    </div>

    <div class="submit-btn">
      <bk-button
        style="margin-right: 20px"
        :loading="submitLoading"
        theme="primary"
        @click="handleSubmitChange"
      >
        {{ $t('提交') }}
      </bk-button>
      <bk-button
        theme="default"
        @click="cancel"
      >
        {{ $t('取消') }}
      </bk-button>
    </div>
  </div>
</template>

<script>
import clusterTable from '@/components/collection-access/components/cluster-table';
import dragMixin from '@/mixins/drag-mixin';
import storageMixin from '@/mixins/storage-mixin';
import { mapGetters } from 'vuex';

import IntroPanel from './components/intro-panel';
import FieldSetting from './components/field-setting';

export default {
  name: 'CustomReportCreate',
  components: {
    IntroPanel,
    clusterTable,
    FieldSetting,
  },
  mixins: [storageMixin, dragMixin],
  data() {
    return {
      isItsm: window.FEATURE_TOGGLE.collect_itsm === 'on',
      customRetentionDay: '', // 过期时间天数
      customHotDataDay: 0, // 热数据天数
      retentionDaysList: [], // 过期时间列表
      hotDataDaysList: [], // 热数据
      linkConfigurationList: [], // 数据链路
      storageList: [], // 存储集群
      selectedStorageCluster: {}, // 选择的es集群
      isOpenWindow: true, // 是否展开使用列表
      isSubmit: false, // 是否提交
      containerLoading: false, // 全局loading
      isEdit: false, // 是否是编辑
      submitLoading: false,
      collectorId: null,
      formData: {
        bk_data_id: '',
        collector_config_name: '',
        collector_config_name_en: '',
        custom_type: 'log',
        data_link_id: '',
        storage_cluster_id: '',
        retention: '',
        allocation_min_days: '0',
        storage_replies: 0,
        category_id: '',
        description: '',
        es_shards: 0,
      },
      replicasMax: 7,
      shardsMax: 7,
      baseRules: {
        collector_config_name: [
          // 采集名称
          {
            required: true,
            trigger: 'blur',
          },
          {
            max: 50,
            trigger: 'blur',
          },
        ],
        collector_config_name_en: [
          // 采集数据名称
          {
            required: true,
            trigger: 'blur',
          },
          {
            max: 50,
            message: this.$t('不能多于{n}个字符', { n: 50 }),
            trigger: 'blur',
          },
          {
            min: 5,
            message: this.$t('不能少于5个字符'),
            trigger: 'blur',
          },
          {
            validator: this.checkEnNameValidator,
            message: this.$t('只支持输入字母，数字，下划线'),
            trigger: 'blur',
          },
        ],
        category_id: [
          // 数据分类
          {
            required: true,
            trigger: 'blur',
          },
        ],
      },
      storageRules: {
        data_link_id: [
          {
            required: true,
            trigger: 'blur',
          },
        ],
        table_id: [
          {
            required: true,
            trigger: 'blur',
          },
          {
            max: 50,
            trigger: 'blur',
          },
          {
            min: 5,
            trigger: 'blur',
          },
          {
            regex: /^[A-Za-z0-9_]+$/,
            trigger: 'blur',
          },
        ],
        cluster_id: [
          {
            validator(val) {
              return val !== '';
            },
            trigger: 'change',
          },
        ],
      },
      clusterList: [], // 共享集群
      exclusiveList: [], // 独享集群
      editStorageClusterID: null,
      isTextValid: true,
      fieldSettingData: {
        indexSetId: 0,
        targetFields: [],
        sortFields: [],
      },
    };
  },
  computed: {
    ...mapGetters({
      bkBizId: 'bkBizId',
      globalsData: 'globals/globalsData',
    }),
    defaultRetention() {
      const { storage_duration_time } = this.globalsData;

      return storage_duration_time?.filter(item => item.default === true)[0].id;
    },
    isCloseDataLink() {
      // 没有可上报的链路时，编辑采集配置链路ID为0或null时，隐藏链路配置框，并且不做空值校验。
      return !this.linkConfigurationList.length || (this.isEdit && !this.formData.data_link_id);
    },
    showGroupText() {
      return Number(this.bkBizId) > 0 ? `${this.bkBizId}_bklog_` : `space_${Math.abs(Number(this.bkBizId))}_bklog_`;
    },
    getLabelWidth() {
      return this.$store.getters.isEnLanguage ? 133 : 103;
    },
  },
  watch: {
    linkConfigurationList: {
      deep: true,
      handler(val) {
        const {
          params: { collectorId },
        } = this.$route;
        if (val.length > 0 && !collectorId) {
          this.formData.data_link_id = val[0]?.data_link_id;
        }
      },
    },
  },
  created() {
    const {
      params: { collectorId },
      name,
    } = this.$route;
    if (collectorId && name === 'custom-report-edit') {
      this.collectorId = collectorId;
      this.isEdit = true;
    }
  },
  mounted() {
    this.containerLoading = true;
    Promise.all([this.getLinkData(), this.getStorage()])
      .then(async () => {
        await this.initFormData();
      })
      .finally(() => {
        this.containerLoading = false;
      });
    this.$nextTick(() => {
      this.maxIntroWidth = this.$refs.addNewCustomBoxRef.clientWidth - 380;
    });
  },
  methods: {
    handleChangeType(id) {
      this.formData.custom_type = id;
    },
    handleSubmitChange() {
      if (this.formData.storage_cluster_id === '') {
        this.$bkMessage({
          theme: 'error',
          message: this.$t('请选择集群'),
        });
        return;
      }
      this.$refs.validateForm.validate().then(
        () => {
          this.submitLoading = true;
          if (this.isCloseDataLink) delete this.formData.data_link_id;
          this.$http
            .request(`custom/${this.isEdit ? 'setCustom' : 'createCustom'}`, {
              params: {
                collector_config_id: this.collectorId,
              },
              data: {
                ...this.formData,
                storage_replies: Number(this.formData.storage_replies),
                allocation_min_days: Number(this.formData.allocation_min_days),
                es_shards: Number(this.formData.es_shards),
                bk_biz_id: Number(this.bkBizId),
                sort_fields: this.fieldSettingData.sortFields || [],
                target_fields: this.fieldSettingData.targetFields || [],
              },
            })
            .then(res => {
              res.result && this.messageSuccess(this.$t('保存成功'));
              this.isSubmit = true;
              this.cancel();
            })
            .finally(() => {
              this.submitLoading = false;
            });
        },
        () => {}
      );
    },
    // 数据链路
    async getLinkData() {
      try {
        this.tableLoading = true;
        const res = await this.$http.request('linkConfiguration/getLinkList', {
          query: {
            bk_biz_id: this.bkBizId,
          },
        });
        this.linkConfigurationList = res.data.filter(item => item.is_active);
      } catch (e) {
        console.warn(e);
      } finally {
        this.tableLoading = false;
      }
    },
    async initFormData() {
      if (this.isEdit) {
        const res = await this.$http.request('collect/details', {
          params: {
            collector_config_id: this.collectorId,
          },
        });
        const {
          index_set_id,
          collector_config_name,
          collector_config_name_en,
          custom_type,
          data_link_id,
          storage_cluster_id,
          retention,
          allocation_min_days,
          storage_replies,
          category_id,
          description,
          bk_data_id,
          target_fields,
          sort_fields,
          storage_shards_nums: storageShardsNums,
        } = res?.data;
        Object.assign(this.formData, {
          collector_config_name,
          collector_config_name_en,
          custom_type,
          data_link_id,
          storage_cluster_id,
          retention: retention ? `${retention}` : this.defaultRetention,
          allocation_min_days,
          storage_replies,
          category_id,
          description,
          bk_data_id,
          es_shards: storageShardsNums,
        });
        // 缓存编辑时的集群ID

        this.editStorageClusterID = storage_cluster_id;
        this.fieldSettingData = {
          indexSetId: index_set_id || 0,
          targetFields: target_fields || [],
          sortFields: sort_fields || [],
        };
      } else {
        const { retention } = this.formData;
        Object.assign(this.formData, {
          retention: retention ? `${retention}` : this.defaultRetention,
        });
      }
    },
    cancel() {
      this.$router.back(-1);
    },
    handleActiveDetails(state) {
      this.isOpenWindow = state;
      this.introWidth = state ? 360 : 0;
    },
    checkEnNameValidator(val) {
      this.isTextValid = new RegExp(/^[A-Za-z0-9_]+$/).test(val);
      return this.isTextValid;
    },
    handleEnConvert() {
      const str = this.formData.collector_config_name_en;
      const convertStr = str.split('').reduce((pre, cur) => {
        if (cur === '-') cur = '_';
        if (!/\w/.test(cur)) cur = '';
        return (pre += cur);
      }, '');
      this.formData.collector_config_name_en = convertStr;
      this.$refs.validateForm
        .validate()
        .then(() => {
          this.isTextValid = true;
        })
        .catch(() => {
          if (convertStr.length < 5) this.isTextValid = true;
        });
    },
  },

  beforeRouteLeave(to, from, next) {
    if (!this.isSubmit) {
      this.$bkInfo({
        title: this.$t('是否放弃本次操作？'),
        confirmFn: () => {
          next();
        },
      });
      return;
    }
    next();
  },
};
</script>

<style lang="scss">
  @import '@/scss/mixins/clearfix';
  @import '@/scss/mixins/flex';
  @import '@/scss/mixins/scroller';
  @import '@/scss/storage';

  .custom-create-container {
    padding: 0 24px;

    .en-bk-form {
      width: 680px;

      .en-name-box {
        align-items: center;

        @include flex-justify(space-between);
      }

      .text-error {
        position: absolute;
        top: 6px;
        left: 12px;
        display: inline-block;
        font-size: 12px;
        color: transparent;

        /* stylelint-disable-next-line declaration-no-important */
        text-decoration: red wavy underline !important;
        pointer-events: none;
      }
    }

    .create-form {
      padding: 24px 37px;
      margin-top: 20px;
      overflow-x: hidden;
      background: #fff;
      border: 1px solid #dcdee5;
      border-radius: 2px;

      .form-title {
        margin-bottom: 24px;
        font-size: 14px;
        font-weight: 700;
        color: #63656e;
      }

      .form-input {
        width: 500px;
      }

      .group-tip {
        font-size: 12px;
        color: #979ba5;
      }
    }

    .submit-btn {
      margin: 20px 20px 100px;
    }

    .intro-container {
      position: fixed;
      top: 99px;
      right: 0;
      z-index: 999;
      height: calc(100vh - 99px);
      overflow: hidden;

      .drag-item {
        position: absolute;
        top: 48%;
        right: 304px;
        z-index: 100;
        display: inline-block;
        width: 20px;
        height: 40px;
        color: #c4c6cc;
        cursor: col-resize;
        user-select: none;

        &.hidden-drag {
          display: none;
        }

        .icon-more::after {
          position: absolute;
          top: 12px;
          left: 0;
          content: '\e189';
        }
      }

      &.draging-move {
        border-left-color: #3a84ff;
      }
    }
  }
</style>
