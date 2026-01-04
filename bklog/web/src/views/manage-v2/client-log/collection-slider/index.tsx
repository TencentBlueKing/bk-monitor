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

import { defineComponent, ref, watch } from 'vue';

import useStore from '@/hooks/use-store';
import { InfoBox, Message } from 'bk-magic-vue';
import { BK_LOG_STORAGE } from '@/store/store.type';

import { t } from '@/hooks/use-locale';
import { TRIGGER_FREQUENCY_OPTIONS, CLIENT_TYPE_OPTIONS, TASK_STAGE_OPTIONS, SUSTAIN_TIME_OPTIONS } from '../constant';

import http from '@/api';

import './index.scss';

export default defineComponent({
  name: 'CollectionSlider',
  props: {
    showSlider: {
      type: Boolean,
      default: false,
    },
    logData: {
      type: Object,
      default: () => null,
    },
    operateType: {
      type: String,
      default: 'create',
    },
  },
  emits: ['cancel-slider', 'updated-table'],
  setup(props, { emit }) {
    const store = useStore();

    const confirmLoading = ref(false); // 确认按钮加载状态
    const formData = ref({
      task_name: '', // 任务名称
      openid: '', // openid
      scene: TASK_STAGE_OPTIONS[1].value, // 任务阶段
      platform: CLIENT_TYPE_OPTIONS[0].value, // 客户端类型
      frequency: TRIGGER_FREQUENCY_OPTIONS[0].value, // 触发频率
      trigger_duration: SUSTAIN_TIME_OPTIONS[0].value, // 持续触发时长(单位 s)
      log_path: '', // 日志路径
      max_file_num: 100, // 最大文件个数
      fileModifyTimeRange: [new Date(), new Date()], // 文件修改时间范围
      comment: '', // 备注
    });
    const formRef = ref(null);

    // 通用表单验证规则
    const basicRules = {
      required: true,
      trigger: 'blur',
    };

    // 文件修改时间范围的自定义验证规则
    const dateRangeRule = {
      required: true,
      trigger: 'blur',
      validator: (value: string[]) => {
        // 检查开始时间和结束时间都不为空
        return value[0] && value[1] && value[0] !== '' && value[1] !== '';
      },
    };

    const formRules = {
      task_name: [basicRules],
      openid: [basicRules],
      scene: [basicRules],
      frequency: [basicRules],
      trigger_duration: [basicRules],
      log_path: [basicRules],
      max_file_num: [basicRules],
      fileModifyTimeRange: [dateRangeRule],
    };

    // 确认提交表单逻辑
    const handleConfirm = async () => {
      try {
        // 先进行表单验证
        const isValid = await formRef.value.validate();
        if (!isValid) {
          return;
        }

        // 设置提交按钮为加载状态
        confirmLoading.value = true;

        const postData = {
          bk_biz_id: store.state.storage[BK_LOG_STORAGE.BK_BIZ_ID],
          task_name: formData.value.task_name,
          openid: formData.value.openid,
          scene: formData.value.scene,
          platform: formData.value.platform,
          frequency: formData.value.frequency,
          log_path: formData.value.log_path,
          max_file_num: formData.value.max_file_num,
          start_time: formData.value.fileModifyTimeRange[0],
          end_time: formData.value.fileModifyTimeRange[1],
          comment: formData.value.comment,
        };

        // 如果频率为持续触发，添加trigger_duration字段
        if (formData.value.frequency === 'sustain') {
          postData.trigger_duration = formData.value.trigger_duration;
        }

        // 调用接口提交数据
        await http.request('collect/createCollectionTask', {
          data: postData,
        });
        Message({ theme: 'success', message: t('保存成功'), delay: 1500 });

        // 通知父组件刷新列表
        emit('updated-table');
      } catch (error) {
        // 捕获异常并输出
        console.warn('提交失败:', error);
      } finally {
        // 关闭加载状态
        confirmLoading.value = false;
      }
    };

    // 初始化表单数据
    const initFormData = () => {
      formData.value = {
        task_name: '',
        openid: '',
        scene: TASK_STAGE_OPTIONS[1].value,
        platform: CLIENT_TYPE_OPTIONS[0].value,
        frequency: TRIGGER_FREQUENCY_OPTIONS[0].value,
        trigger_duration: SUSTAIN_TIME_OPTIONS[0].value,
        log_path: '',
        max_file_num: 100,
        fileModifyTimeRange: [new Date(), new Date()],
        comment: '',
      };
    };

    // 设置表单数据
    const setFormData = (data: Record<string, any>) => {
      formData.value = {
        task_name: data.task_name,
        openid: data.openid,
        scene: data.scene,
        platform: data.platform,
        frequency: data.frequency,
        trigger_duration: data.trigger_duration || SUSTAIN_TIME_OPTIONS[0].value,
        log_path: data.log_path,
        max_file_num: data.max_file_num,
        fileModifyTimeRange: [data.start_time, data.end_time],
        comment: '',
      };
    };

    // 取消操作/关闭侧滑弹窗
    const handleCancel = () => {
      if (props.operateType === 'view') {
        emit('cancel-slider');
        return;
      }
      InfoBox({
        title: t('确认离开当前页？'),
        subTitle: t('离开将会导致未保存信息丢失'),
        okText: t('离开'),
        cancelText: t('取消'),
        confirmFn: () => emit('cancel-slider'),
      });
    };

    // 监听showSlider变化
    watch(
      () => props.showSlider,
      (newVal) => {
        if (newVal && props.logData) {
          setFormData(props.logData);
        } else {
          initFormData();
        }
      },
    );

    // 根据操作类型获取标题
    const getTitleByOperateType = () => {
      switch (props.operateType) {
        case 'create':
          return t('新建采集');
        case 'clone':
          return t('克隆采集');
        case 'view':
          return t('查看采集');
        default:
          return t('新建采集');
      }
    };

    // 根据客户端类型值获取对应的标签
    const getClientTypeLabel = (platformValue: string) => {
      const clientType = CLIENT_TYPE_OPTIONS.find(option => option.value === platformValue);
      return clientType ? clientType.label : '-';
    };

    // 根据触发频率值获取对应的标签
    const getTriggerFrequencyLabel = (frequencyValue: string) => {
      const frequency = TRIGGER_FREQUENCY_OPTIONS.find(option => option.value === frequencyValue);
      return frequency ? frequency.label : '-';
    };

    // 根据持续触发时长值获取对应的标签
    const getSustainTimeLabel = (durationValue: number) => {
      const duration = SUSTAIN_TIME_OPTIONS.find(option => option.value === durationValue);
      return duration ? duration.label : '-';
    };

    return () => (
      <bk-sideslider
        width={678}
        quick-close
        is-show={props.showSlider}
        title={getTitleByOperateType()}
        transfer
        onAnimation-end={handleCancel}
      >
        <template slot='content'>
          {/* 新建、克隆 */}
          {props.operateType !== 'view' && (
            <div class='new-collection-container'>
              <bk-form
                label-width={158}
                ref={formRef}
                {...{
                  props: {
                    model: formData.value,
                    rules: formRules,
                  },
                }}
              >
                <bk-form-item
                  label={t('任务名称')}
                  required
                  property='task_name'
                >
                  <bk-input
                    value={formData.value.task_name}
                    on-change={(value: string) => (formData.value.task_name = value)}
                  />
                </bk-form-item>
                <bk-form-item
                  label='openid'
                  required
                  property='openid'
                >
                  <bk-input
                    type='textarea'
                    value={formData.value.openid}
                    on-change={(value: string) => (formData.value.openid = value)}
                    placeholder={t('多个 openid 用「换行」分隔')}
                  />
                </bk-form-item>
                <bk-form-item
                  label={t('任务阶段')}
                  required
                  property='scene'
                >
                  <bk-radio-group
                    value={formData.value.scene}
                    on-change={(value: number) => (formData.value.scene = value)}
                  >
                    {TASK_STAGE_OPTIONS.map(option => (
                      <bk-radio value={option.value}>{option.label}</bk-radio>
                    ))}
                  </bk-radio-group>
                </bk-form-item>
                <bk-form-item
                  label={t('客户端类型')}
                  required
                  property='platform'
                >
                  <bk-radio-group
                    value={formData.value.platform}
                    on-change={(value: string) => (formData.value.platform = value)}
                    class='client-type-radio-group'
                  >
                    {CLIENT_TYPE_OPTIONS.map(option => (
                      <bk-radio value={option.value}>{option.label}</bk-radio>
                    ))}
                  </bk-radio-group>
                </bk-form-item>
                <bk-form-item
                  label={t('触发频率')}
                  required
                  property='frequency'
                >
                  <bk-radio-group
                    value={formData.value.frequency}
                    on-change={(value: string) => (formData.value.frequency = value)}
                  >
                    {TRIGGER_FREQUENCY_OPTIONS.map(option => (
                      <bk-radio value={option.value}>{option.label}</bk-radio>
                    ))}
                  </bk-radio-group>
                </bk-form-item>
                {formData.value.frequency === 'sustain' && (
                  <bk-form-item
                    label={t('持续触发时长')}
                    required
                    desc={t('持续触发时长')}
                    property='trigger_duration'
                  >
                    <bk-select
                      value={formData.value.trigger_duration}
                      on-change={(value: number) => (formData.value.trigger_duration = value)}
                      style='width: 200px;'
                    >
                      {SUSTAIN_TIME_OPTIONS.map(option => (
                        <bk-option
                          id={option.value}
                          key={option.value}
                          name={option.label}
                        />
                      ))}
                    </bk-select>
                  </bk-form-item>
                )}
                <bk-form-item
                  label={t('日志路径')}
                  required
                  property='log_path'
                  desc={t('日志路径')}
                >
                  <bk-input
                    type='textarea'
                    value={formData.value.log_path}
                    on-change={(value: string) => (formData.value.log_path = value)}
                  />
                </bk-form-item>
                <bk-form-item
                  label={t('最大文件个数')}
                  required
                  property='max_file_num'
                >
                  <bk-input
                    type='number'
                    min={0}
                    value={formData.value.max_file_num}
                    on-change={(value: number) => (formData.value.max_file_num = value)}
                  />
                </bk-form-item>
                <bk-form-item
                  label={t('文件修改时间范围')}
                  required
                  property='fileModifyTimeRange'
                >
                  <bk-date-picker
                    type='datetimerange'
                    value={formData.value.fileModifyTimeRange}
                    on-change={value => (formData.value.fileModifyTimeRange = value)}
                    transfer
                  />
                </bk-form-item>
                <bk-form-item label={t('备注')}>
                  <bk-input
                    type='textarea'
                    value={formData.value.comment}
                    on-change={value => (formData.value.comment = value)}
                  />
                </bk-form-item>
                {props.operateType !== 'view' && (
                  <bk-form-item class='button-group'>
                    <bk-button
                      theme='primary'
                      title='提交'
                      class='button-submit'
                      loading={confirmLoading.value}
                      onClick={handleConfirm}
                    >
                      {t('提交')}
                    </bk-button>
                    <bk-button
                      title='取消'
                      onClick={handleCancel}
                    >
                      {t('取消')}
                    </bk-button>
                  </bk-form-item>
                )}
              </bk-form>
            </div>
          )}
          {/* 查看 */}
          {props.operateType === 'view' && (
            <div class='view-collection-container'>
              <div>
                <span>{t('任务 ID')}</span>
                <span>{props.logData.task_id || '-'}</span>
              </div>
              <div>
                <span>{t('任务名称')}</span>
                <span>{props.logData.task_name || '-'}</span>
              </div>
              <div>
                <span>{'openid'}</span>
                <span>{props.logData.openid?.split('\n').join(';') || '-'}</span>
              </div>
              <div>
                <span>{t('任务状态')}</span>
                <span>{props.logData.status_name || '-'}</span>
              </div>
              <div>
                <span>{t('任务阶段')}</span>
                <span>{props.logData.scene_name || '-'}</span>
              </div>
              <div>
                <span>{t('创建人')}</span>
                <span>
                  <bk-user-display-name user-id={props.logData.created_by}></bk-user-display-name>
                </span>
              </div>
              <div>
                <span>{t('创建时间')}</span>
                <span>{props.logData.created_at || '-'}</span>
              </div>
              <div>
                <span>{t('日志路径')}</span>
                <span>{props.logData.log_path || '-'}</span>
              </div>
              <div>
                <span>{t('触发频率')}</span>
                <span>{getTriggerFrequencyLabel(props.logData.frequency)}</span>
              </div>
              {props.logData.frequency === 'sustain' && (
                <div>
                  <span>{t('持续触发时长')}</span>
                  <span>{getSustainTimeLabel(props.logData.trigger_duration)}</span>
                </div>
              )}
              <div>
                <span>{t('客户端类型')}</span>
                <span>{getClientTypeLabel(props.logData.platform) || '-'}</span>
              </div>
              <div>
                <span>{t('最大文件个数')}</span>
                <span>{props.logData.max_file_num || '-'}</span>
              </div>
              <div>
                <span>{t('备注')}</span>
                <span>{props.logData.comment || '-'}</span>
              </div>
            </div>
          )}
        </template>
      </bk-sideslider>
    );
  },
});
