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
  <div class="restore-slider-container">
    <bk-sideslider
      :before-close="handleCloseSidebar"
      :is-show="showSlider"
      :quick-close="true"
      :title="isEdit ? $t('编辑回溯') : $t('新建回溯')"
      :width="676"
      transfer
      @animation-end="updateIsShow"
    >
      <template #content>
        <div
          class="restore-slider-content"
          v-bkloading="{ isLoading: sliderLoading }"
        >
          <bk-form
            v-if="!sliderLoading"
            ref="validateForm"
            class="king-form"
            :label-width="150"
            :model="formData"
            :rules="basicRules"
            data-test-id="restore_div_addNewRestore"
            form-type="vertical"
          >
            <bk-form-item
              :label="$t('索引集名称')"
              property="index_set_name"
              required
            >
              <bk-input
                v-model="formData.index_set_name"
                :disabled="isEdit"
                data-test-id="addNewRestore_input_indexSetName"
              ></bk-input>
            </bk-form-item>
            <!-- <bk-alert type="info" :title="$t('COS的自动创建和关联，只能用于腾讯云')"></bk-alert> -->
            <bk-form-item
              :label="$t('归档项')"
              property="archive_config_id"
              required
            >
              <bk-select
                v-model="formData.archive_config_id"
                :disabled="isEdit"
                data-test-id="addNewRestore_select_selectCollector"
                @selected="handleArchiveChange"
              >
                <bk-option
                  v-for="option in archiveList"
                  :disabled="!option.permission[authorityMap.MANAGE_COLLECTION_AUTH]"
                  :id="option.archive_config_id"
                  :key="option.archive_config_id"
                  :name="option.instance_name"
                >
                </bk-option>
              </bk-select>
            </bk-form-item>
            <bk-form-item
              :label="$t('时间范围')"
              property="datePickerValue"
              required
            >
              <bk-date-picker
                v-model="formData.datePickerValue"
                :disabled="isEdit"
                :placeholder="$t('选择日期时间范围')"
                :type="'datetimerange'"
                format="yyyy-MM-dd HH:mm"
                @change="handleTimeChange"
              >
              </bk-date-picker>
            </bk-form-item>
            <bk-form-item
              :label="$t('过期时间')"
              property="datePickerExpired"
              required
            >
              <bk-date-picker
                v-model="formData.datePickerExpired"
                :options="expiredDatePicker"
                data-test-id="addNewRestore_div_datePickerExpired"
                format="yyyy-MM-dd HH:mm"
                @change="handleExpiredChange"
              >
              </bk-date-picker>
            </bk-form-item>
            <bk-form-item
              :label="$t('结果通知人')"
              property="notice_user"
              required
            >
              <validate-user-selector
                style="width: 500px"
                v-model="formData.notice_user"
                :api="userApi"
                :disabled="isEdit"
                data-test-id="addNewRestore_input_notifiedUser"
              />
            </bk-form-item>
            <bk-form-item style="margin-top: 30px">
              <bk-button
                class="king-button mr10"
                :loading="confirmLoading"
                data-test-id="addNewRestore_button_submit"
                theme="primary"
                @click.stop.prevent="handleConfirm"
              >
                {{ $t('提交') }}
              </bk-button>
              <bk-button
                data-test-id="addNewRestore_button_cancel"
                @click="handleCancel"
                >{{ $t('取消') }}</bk-button
              >
            </bk-form-item>
          </bk-form>
        </div>
      </template>
    </bk-sideslider>
  </div>
</template>

<script>
  import SidebarDiffMixin from '@/mixins/sidebar-diff-mixin';
  import { mapGetters } from 'vuex';

  import * as authorityMap from '../../../../common/authority-map';
  import ValidateUserSelector from '../../manage-extract/manage-extract-permission/validate-user-selector';

  export default {
    components: {
      ValidateUserSelector,
    },
    mixins: [SidebarDiffMixin],
    props: {
      showSlider: {
        type: Boolean,
        default: false,
      },
      editRestore: {
        type: Object,
        default: null,
      },
      archiveId: {
        type: Number,
        default: null,
      },
    },
    data() {
      return {
        confirmLoading: false,
        sliderLoading: false,
        userApi: window.BK_LOGIN_URL,
        customRetentionDay: '', // 自定义过期天数
        retentionDaysList: [], // 过期天数列表
        archiveList: [],
        formData: {
          index_set_name: '',
          archive_config_id: '',
          datePickerValue: ['', ''],
          datePickerExpired: '',
          expired_time: '',
          notice_user: [],
          start_time: '',
          end_time: '',
        },
        basicRules: {},
        requiredRules: {
          required: true,
          trigger: 'blur',
        },
        expiredDatePicker: {
          disabledDate(time) {
            return time.getTime() < Date.now();
          },
        },
      };
    },
    computed: {
      ...mapGetters({
        bkBizId: 'bkBizId',
        user: 'uesr',
        globalsData: 'globals/globalsData',
      }),
      authorityMap() {
        return authorityMap;
      },
      isEdit() {
        return this.editRestore !== null;
      },
    },
    watch: {
      showSlider(val) {
        if (val) {
          this.sliderLoading = this.isEdit;
          this.getArchiveList();
          this.updateDaysList();
          if (this.isEdit) {
            const {
              index_set_name,
              archive_config_id,
              expired_time: expiredTime,
              notice_user,
              start_time,
              end_time,
            } = this.editRestore;
            Object.assign(this.formData, {
              index_set_name,
              archive_config_id,
              expired_time: expiredTime,
              notice_user,
              start_time,
              end_time,

              datePickerValue: [start_time, end_time],
              datePickerExpired: expiredTime,
            });
          } else {
            const { userMeta } = this.$store.state;
            if (userMeta?.username) {
              this.formData.notice_user.push(userMeta.username);
            }
          }

          if (this.archiveId) {
            // 从归档列表新建回溯
            this.formData.archive_config_id = this.archiveId;
          }
          this.initSidebarFormData();
        } else {
          // 清空表单数据
          this.formData = {
            index_set_name: '',
            archive_config_id: '',
            datePickerValue: ['', ''],
            expired_time: '',
            datePickerExpired: '',
            notice_user: [],
            start_time: '',
            end_time: '',
          };
        }
      },
    },
    created() {
      this.basicRules = {
        index_set_name: [this.requiredRules],
        archive_config_id: [this.requiredRules],
        datePickerExpired: [this.requiredRules],
        datePickerValue: [
          {
            validator: val => {
              if (val.length) {
                return !!val.every(item => item);
              }
              return false;
            },
            trigger: 'blur',
          },
        ],
        notice_user: [
          {
            validator: val => {
              return !!val.length;
            },
            trigger: 'blur',
          },
        ],
      };
    },
    methods: {
      getArchiveList() {
        const query = {
          bk_biz_id: this.bkBizId,
        };
        this.$http
          .request('archive/getAllArchives', { query })
          .then(res => {
            this.archiveList = res.data || [];
            if (!this.isEdit) {
              this.formData.archive_config_id = res.data[0].archive_config_id || '';
              this.handleArchiveChange(res.data[0].archive_config_id);
            }
          })
          .finally(() => {
            this.sliderLoading = false;
          });
      },
      updateIsShow() {
        this.$emit('hidden');
        this.$emit('update:show-slider', false);
      },
      handleCancel() {
        this.$emit('update:show-slider', false);
      },
      handleTimeChange(val) {
        this.formData.start_time = val[0];
        this.formData.end_time = val[1];
      },
      handleExpiredChange(val) {
        this.formData.expired_time = val;
      },
      handleArchiveChange(nval) {
        const selectArchive = this.archiveList.find(el => el.archive_config_id === nval);
        const date = new Date();
        const year = date.getFullYear();
        const month = date.getMonth() * 1 + 1 >= 10 ? date.getMonth() * 1 + 1 : `0${date.getMonth() * 1 + 1}`;
        const day = date.getDate() >= 10 ? date.getDate() : `0${date.getDate()}`;
        const hour = date.getHours() >= 10 ? date.getHours() : `0${date.getHours()}`;
        const min = date.getMinutes() >= 10 ? date.getMinutes() : `0${date.getMinutes()}`;
        const dateStr = `${year}${month}${day}${hour}${min}`;
        this.formData.index_set_name = selectArchive
          ? `${selectArchive?.instance_name}-${this.$t('回溯')}-${dateStr}`
          : '';
      },
      updateDaysList() {
        const retentionDaysList = [...this.globalsData.storage_duration_time].filter(item => {
          return item.id;
        });
        this.retentionDaysList = retentionDaysList;
      },
      // 输入自定义过期天数
      enterCustomDay(val) {
        const numberVal = parseInt(val.trim(), 10);
        const stringVal = numberVal.toString();
        if (numberVal) {
          if (!this.retentionDaysList.some(item => item.id === stringVal)) {
            this.retentionDaysList.push({
              id: stringVal,
              name: stringVal + this.$t('天'),
            });
          }
          this.formData.snapshot_days = stringVal;
          this.customRetentionDay = '';
          document.body.click();
        } else {
          this.customRetentionDay = '';
          this.messageError(this.$t('请输入有效数值'));
        }
      },
      async handleConfirm() {
        try {
          await this.$refs.validateForm.validate();
          let url = '/archive/createRestore';
          let paramsData = {
            ...this.formData,
            bk_biz_id: this.bkBizId,
          };
          const params = {};
          delete paramsData.datePickerValue;
          delete paramsData.datePickerExpired;
          this.confirmLoading = true;

          if (this.isEdit) {
            url = '/archive/editRestore';
            const { expired_time } = this.formData;
            const { restore_config_id } = this.editRestore;

            paramsData = {
              expired_time,
              restore_config_id,
            };

            params.restore_config_id = restore_config_id;
          }

          await this.$http.request(url, {
            data: paramsData,
            params,
          });

          this.$bkMessage({
            theme: 'success',
            message: this.$t('保存成功'),
            delay: 1500,
          });
          this.$emit('updated');
        } catch (e) {
          console.warn(e);
        } finally {
          this.confirmLoading = false;
        }
      },
    },
  };
</script>

<style lang="scss">
  .restore-slider-content {
    height: calc(100vh - 60px);
    min-height: 394px;

    .bk-form.bk-form-vertical {
      padding: 10px 0 36px 36px;

      .bk-form-item {
        width: 500px;
        margin-top: 18px;
      }

      .bk-alert {
        width: 500px;
        margin-top: 12px;
      }

      .bk-select,
      .bk-date-picker {
        width: 300px;
      }

      .user-selector {
        /* stylelint-disable-next-line declaration-no-important */
        width: 500px !important;
      }
    }
  }
</style>
