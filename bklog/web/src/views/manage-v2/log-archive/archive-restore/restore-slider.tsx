/*
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
 */

import { defineComponent, ref, reactive, computed, watch, onMounted } from 'vue';

import * as authorityMap from '@/common/authority-map';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import ValidateUserSelector from '@/views/manage/manage-extract/manage-extract-permission/validate-user-selector.vue';
import { InfoBox, Message } from 'bk-magic-vue';

import http from '@/api';

import './restore-slider.scss';

export default defineComponent({
  name: 'RestoreSlider',
  components: {
    ValidateUserSelector,
  },
  props: {
    // 是否显示侧滑
    showSlider: {
      type: Boolean,
      default: false,
    },
    // 编辑回溯数据
    editRestore: {
      type: Object,
      default: null,
    },
    // 归档ID
    archiveId: {
      type: Number,
      default: null,
    },
    onHandleCancelSlider: { type: Function },
    onHandleUpdatedTable: { type: Function },
  },
  emits: ['handleCancelSlider', 'handleUpdatedTable'],

  setup(props, { emit }) {
    const store = useStore();
    const { t } = useLocale(); // 获取国际化函数
    const validateForm = ref<any>(null); // 表单验证引用

    const confirmLoading = ref(false); // 确认按钮加载状态
    const sliderLoading = ref(false); // 侧滑内容加载状态
    const userApi = ref((window as any).BK_LOGIN_URL); // 用户API
    const archiveList = ref<any[]>([]); // 归档列表
    const retentionDaysList = ref<any[]>([]); // 过期天数列表

    // 表单数据
    const formData = reactive({
      index_set_name: '',
      archive_config_id: '',
      datePickerValue: ['', ''],
      datePickerExpired: '',
      expired_time: '',
      notice_user: [],
      start_time: '',
      end_time: '',
    });

    // 表单验证规则
    const basicRules = reactive({});
    const requiredRules = {
      required: true,
      trigger: 'blur',
    };

    // 过期时间选择器配置
    const expiredDatePicker = reactive({
      disabledDate(time: Date) {
        return time.getTime() < Date.now();
      },
    });

    const bkBizId = computed(() => store.getters.bkBizId); // 业务ID
    const globalsData = computed(() => store.getters['globals/globalsData']); // 全局数据
    const authorityMapComputed = computed(() => authorityMap); // 权限映射

    // 是否为编辑模式
    const isEdit = computed(() => props.editRestore !== null);

    // 获取归档列表
    const getArchiveList = async () => {
      const query = {
        bk_biz_id: bkBizId.value,
      };

      try {
        const res = await http.request('archive/getAllArchives', { query });
        archiveList.value = res.data || [];

        if (!isEdit.value && archiveList.value.length) {
          formData.archive_config_id = archiveList.value[0].archive_config_id || '';
          handleArchiveChange(archiveList.value[0].archive_config_id);
        }
      } catch (error) {
        console.warn('获取归档列表失败:', error);
      } finally {
        sliderLoading.value = false;
      }
    };

    // 更新天数列表
    const updateDaysList = () => {
      const retentionDaysListData = [...globalsData.value.storage_duration_time].filter(item => {
        return item.id;
      });
      retentionDaysList.value = retentionDaysListData;
    };

    // 归档项变更处理
    const handleArchiveChange = (nval: any) => {
      const selectArchive = archiveList.value.find(el => el.archive_config_id === nval);
      const date = new Date();
      const year = date.getFullYear();
      const month = date.getMonth() * 1 + 1 >= 10 ? date.getMonth() * 1 + 1 : `0${date.getMonth() * 1 + 1}`;
      const day = date.getDate() >= 10 ? date.getDate() : `0${date.getDate()}`;
      const hour = date.getHours() >= 10 ? date.getHours() : `0${date.getHours()}`;
      const min = date.getMinutes() >= 10 ? date.getMinutes() : `0${date.getMinutes()}`;
      const dateStr = `${year}${month}${day}${hour}${min}`;
      formData.index_set_name = selectArchive ? `${selectArchive?.instance_name}-${t('回溯')}-${dateStr}` : '';
    };

    // 时间范围变更处理
    const handleTimeChange = (val: any) => {
      formData.start_time = val[0];
      formData.end_time = val[1];
    };

    // 过期时间变更处理
    const handleExpiredChange = (val: any) => {
      formData.expired_time = val;
    };

    // 取消处理
    const handleCancel = () => {
      InfoBox({
        title: t('确认离开当前页？'),
        subTitle: t('离开将会导致未保存信息丢失'),
        okText: t('离开'),
        cancelText: t('取消'),
        confirmFn: () => emit('handleCancelSlider'),
      });
    };

    // 确认提交表单逻辑
    const handleConfirm = async () => {
      try {
        // 验证表单
        await validateForm.value?.validate();

        // 确定请求URL和参数
        let url = '/archive/createRestore';
        const params: any = {};
        let paramsData: any = {
          ...formData,
          bk_biz_id: bkBizId.value,
        };

        // 删除不需要的字段
        const { datePickerValue: _datePickerValue, datePickerExpired: _datePickerExpired, ...other } = paramsData;
        paramsData = other;

        // 编辑模式下的参数调整
        if (isEdit.value) {
          url = '/archive/editRestore';
          const { expired_time } = formData;
          const { restore_config_id } = props.editRestore;
          paramsData = {
            expired_time,
            restore_config_id,
          };
          params.restore_config_id = restore_config_id;
        }

        // 设置提交按钮为加载状态
        confirmLoading.value = true;

        // 调用接口提交数据
        await http.request(url, {
          data: paramsData,
          params,
        });

        // 提示保存成功
        Message({
          theme: 'success',
          message: t('保存成功'),
          delay: 1500,
        });

        // 通知父组件更新
        emit('handleUpdatedTable');
      } catch (error) {
        // 捕获异常并输出
        console.warn('提交失败:', error);
      } finally {
        // 关闭加载状态
        confirmLoading.value = false;
      }
    };

    // 渲染归档项选项
    const renderArchiveOptions = () => {
      return archiveList.value.map(option => (
        <bk-option
          id={option.archive_config_id}
          key={option.archive_config_id}
          disabled={!option.permission[authorityMapComputed.value.MANAGE_COLLECTION_AUTH]}
          name={option.instance_name}
        >
          {option.instance_name}
        </bk-option>
      ));
    };

    // 监听 showSlider 变化
    watch(
      () => props.showSlider,
      async val => {
        if (val) {
          sliderLoading.value = isEdit.value;
          await getArchiveList();
          updateDaysList();

          if (isEdit.value) {
            const {
              index_set_name,
              archive_config_id,
              expired_time: expiredTime,
              notice_user,
              start_time,
              end_time,
            } = props.editRestore;

            Object.assign(formData, {
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
            const { userMeta } = store.state;
            if (userMeta?.username) {
              formData.notice_user.push(userMeta.username);
            }
          }

          if (props.archiveId) {
            // 从归档列表新建回溯
            formData.archive_config_id = props.archiveId.toString();
          }
        } else {
          // 清空表单数据
          Object.assign(formData, {
            index_set_name: '',
            archive_config_id: '',
            datePickerValue: ['', ''],
            expired_time: '',
            datePickerExpired: '',
            notice_user: [],
            start_time: '',
            end_time: '',
          });
        }
      },
    );

    // 组件挂载时初始化验证规则
    onMounted(() => {
      Object.assign(basicRules, {
        index_set_name: [requiredRules],
        archive_config_id: [requiredRules],
        datePickerExpired: [requiredRules],
        datePickerValue: [
          {
            validator: (val: any) => {
              if (val.length) {
                return !!val.every((item: any) => item);
              }
              return false;
            },
            trigger: 'blur',
          },
        ],
        notice_user: [
          {
            validator: (val: any) => {
              return !!val.length;
            },
            trigger: 'blur',
          },
        ],
      });
    });

    // 侧滑组件主渲染
    return () => (
      <div class='restore-slider-container'>
        <bk-sideslider
          width={676}
          is-show={props.showSlider}
          quick-close={true}
          show-mask={true}
          title={isEdit.value ? t('编辑回溯') : t('新建回溯')}
          transfer
          onAnimation-end={handleCancel}
        >
          <template slot='content'>
            <div
              class='restore-slider-content'
              v-bkloading={{ isLoading: sliderLoading.value }}
            >
              {/* 加载完成后渲染表单 */}
              {!sliderLoading.value && (
                <bk-form
                  ref={validateForm}
                  class='king-form'
                  data-test-id='restore_div_addNewRestore'
                  form-type='vertical'
                  label-width={150}
                  {...{
                    props: {
                      model: formData,
                      rules: basicRules,
                    },
                  }}
                >
                  {/* 索引集名称 */}
                  <bk-form-item
                    label={t('索引集名称')}
                    property='index_set_name'
                    required
                  >
                    <bk-input
                      data-test-id='addNewRestore_input_indexSetName'
                      disabled={isEdit.value}
                      value={formData.index_set_name}
                      onChange={(val: string) => (formData.index_set_name = val)}
                    />
                  </bk-form-item>

                  {/* 归档项 */}
                  <bk-form-item
                    label={t('归档项')}
                    property='archive_config_id'
                    required
                  >
                    <bk-select
                      data-test-id='addNewRestore_select_selectCollector'
                      disabled={isEdit.value}
                      value={formData.archive_config_id}
                      onChange={(val: any) => {
                        formData.archive_config_id = val;
                        handleArchiveChange(val);
                      }}
                    >
                      {renderArchiveOptions()}
                    </bk-select>
                  </bk-form-item>

                  {/* 时间范围 */}
                  <bk-form-item
                    label={t('时间范围')}
                    property='datePickerValue'
                    required
                  >
                    <bk-date-picker
                      disabled={isEdit.value}
                      format='yyyy-MM-dd HH:mm'
                      placeholder={t('选择日期时间范围')}
                      type='datetimerange'
                      value={formData.datePickerValue}
                      onChange={val => {
                        formData.datePickerValue = val;
                        handleTimeChange(val);
                      }}
                    />
                  </bk-form-item>

                  {/* 过期时间 */}
                  <bk-form-item
                    label={t('过期时间')}
                    property='datePickerExpired'
                    required
                  >
                    <bk-date-picker
                      data-test-id='addNewRestore_div_datePickerExpired'
                      format='yyyy-MM-dd HH:mm'
                      options={expiredDatePicker}
                      value={formData.datePickerExpired}
                      onChange={val => {
                        formData.datePickerExpired = val;
                        handleExpiredChange(val);
                      }}
                    />
                  </bk-form-item>

                  {/* 结果通知人 */}
                  <bk-form-item
                    label={t('结果通知人')}
                    property='notice_user'
                    required
                  >
                    <ValidateUserSelector
                      style='width: 500px'
                      api={userApi.value}
                      data-test-id='addNewRestore_input_notifiedUser'
                      disabled={isEdit.value}
                      // @ts-expect-error
                      value={formData.notice_user}
                      onChange={(val: any) => (formData.notice_user = val)}
                    />
                  </bk-form-item>

                  {/* 提交/取消按钮 */}
                  <bk-form-item style='margin-top: 30px'>
                    <bk-button
                      class='king-button mr10'
                      data-test-id='addNewRestore_button_submit'
                      loading={confirmLoading.value}
                      theme='primary'
                      onClick={handleConfirm}
                    >
                      {t('提交')}
                    </bk-button>
                    <bk-button
                      data-test-id='addNewRestore_button_cancel'
                      onClick={handleCancel}
                    >
                      {t('取消')}
                    </bk-button>
                  </bk-form-item>
                </bk-form>
              )}
            </div>
          </template>
        </bk-sideslider>
      </div>
    );
  },
});
