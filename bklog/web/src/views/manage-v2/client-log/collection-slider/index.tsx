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

import { InfoBox } from 'bk-magic-vue';

import { t } from '@/hooks/use-locale';

import './index.scss';

// 任务阶段选项
const TASK_STAGE_OPTIONS = [
  { value: 1, label: t('登录前') },
  { value: 4, label: t('登录后') },
];

// 客户类型选项
const CLIENT_TYPE_OPTIONS = [
  { value: '默认', label: t('默认') },
  { value: '安装', label: t('安装') },
  { value: 'iOS', label: 'iOS' },
  { value: 'macOS', label: 'macOS' },
  { value: 'Windows', label: 'Windows' },
  { value: 'Harmony', label: 'Harmony' },
];

// 触发频率选项
const TRIGGER_FREQUENCY_OPTIONS = [
  { value: 'single', label: t('单次触发') },
  { value: 'sustain', label: t('持续触发') },
];

// 持续触发时长选项
const SUSTAIN_TIME_OPTIONS = [
  { value: 3600, label: t('1小时') }, // 1小时 = 3600秒
  { value: 10800, label: t('{n}小时', { n: 3 }) }, // 3小时 = 10800秒
  { value: 43200, label: t('{n}小时', { n: 12 }) }, // 12小时 = 43200秒
  { value: 86400, label: t('1天') }, // 1天 = 86400秒
  { value: 259200, label: t('{n}天', { n: 3 }) }, // 3天 = 259200秒
  { value: 604800, label: t('{n}天', { n: 7 }) }, // 7天 = 604800秒
];

export default defineComponent({
  name: 'CollectionSlider',
  props: {
    showSlider: {
      type: Boolean,
      default: false,
    },
    onHandleCancelSlider: { type: Function, default: () => {} },
    onHandleUpdatedTable: { type: Function, default: () => {} },
  },
  emits: ['handleCancelSlider', 'handleUpdatedTable'],
  setup(props, { emit }) {
    const confirmLoading = ref(false); // 确认按钮加载状态
    const formData = ref({
      taskName: '', // 任务名称
      openid: '', // openid
      taskStage: TASK_STAGE_OPTIONS[1].value, // 任务阶段
      clientType: CLIENT_TYPE_OPTIONS[0].value, // 客户类型
      triggerFrequency: TRIGGER_FREQUENCY_OPTIONS[0].value, // 触发频率
      sustainTime: SUSTAIN_TIME_OPTIONS[0].value, // 持续触发时长(单位 s)
      logPath: '', // 日志路径
      maxFileCount: 100, // 最大文件个数
      fileModifyTimeRange: [new Date(), new Date()], // 文件修改时间范围
      remark: '', // 备注
    });
    const formRef = ref(null);

    // 表单验证规则
    const basicRules = {
      required: true,
      trigger: 'blur',
    };

    const formRules = {
      taskName: [basicRules],
      openid: [basicRules],
      taskStage: [basicRules],
      clientType: [basicRules],
      triggerFrequency: [basicRules],
      sustainTime: [basicRules],
      logPath: [basicRules],
      maxFileCount: [basicRules],
      fileModifyTimeRange: [basicRules],
    };

    // 确认提交表单逻辑
    const handleConfirm = async () => {
      try {
        // 先进行表单验证
        const isValid = await formRef.value.validate();
        if (!isValid) {
          return;
        }

        console.log('提交表单数据:', formData.value);
        // 设置提交按钮为加载状态
        confirmLoading.value = true;

        // 调用接口提交数据

        // 通知父组件刷新列表
        emit('handleUpdatedTable');
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
        taskName: '',
        openid: '',
        taskStage: TASK_STAGE_OPTIONS[1].value,
        clientType: CLIENT_TYPE_OPTIONS[0].value,
        triggerFrequency: TRIGGER_FREQUENCY_OPTIONS[0].value,
        sustainTime: SUSTAIN_TIME_OPTIONS[0].value,
        logPath: '',
        maxFileCount: 100,
        fileModifyTimeRange: [new Date(), new Date()],
        remark: '',
      };
    };

    // 取消操作/关闭侧滑弹窗
    const handleCancel = () => {
      InfoBox({
        title: t('确认离开当前页？'),
        subTitle: t('离开将会导致未保存信息丢失'),
        okText: t('离开'),
        cancelText: t('取消'),
        confirmFn: () => emit('handleCancelSlider'),
      });
    };

    // 监听showSlider变化
    watch(
      () => props.showSlider,
      () => {
        initFormData();
      },
    );

    return () => (
      <bk-sideslider
        width={678}
        quick-close
        is-show={props.showSlider}
        title={t('新建采集')}
        transfer
        onAnimation-end={handleCancel}
      >
        <template slot='content'>
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
                property='taskName'
              >
                <bk-input
                  value={formData.value.taskName}
                  on-change={value => (formData.value.taskName = value)}
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
                  on-change={value => (formData.value.openid = value)}
                  placeholder={t('多个 openid 用「换行」分隔')}
                />
              </bk-form-item>
              <bk-form-item
                label={t('任务阶段')}
                required
                property='taskStage'
              >
                <bk-radio-group
                  value={formData.value.taskStage}
                  on-change={value => (formData.value.taskStage = value)}
                >
                  {TASK_STAGE_OPTIONS.map(option => (
                    <bk-radio value={option.value}>{option.label}</bk-radio>
                  ))}
                </bk-radio-group>
              </bk-form-item>
              <bk-form-item
                label={t('客户端类型')}
                required
                property='clientType'
              >
                <bk-radio-group
                  value={formData.value.clientType}
                  on-change={value => (formData.value.clientType = value)}
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
                property='triggerFrequency'
              >
                <bk-radio-group
                  value={formData.value.triggerFrequency}
                  on-change={value => (formData.value.triggerFrequency = value)}
                >
                  {TRIGGER_FREQUENCY_OPTIONS.map(option => (
                    <bk-radio value={option.value}>{option.label}</bk-radio>
                  ))}
                </bk-radio-group>
              </bk-form-item>
              {formData.value.triggerFrequency === 'sustain' && (
                <bk-form-item
                  label={t('持续触发时长')}
                  required
                  desc={t('持续触发时长')}
                  property='sustainTime'
                >
                  <bk-select
                    value={formData.value.sustainTime}
                    on-change={value => (formData.value.sustainTime = value)}
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
                property='logPath'
                desc={t('日志路径')}
              >
                <bk-input
                  type='textarea'
                  value={formData.value.logPath}
                  on-change={value => (formData.value.logPath = value)}
                />
              </bk-form-item>
              <bk-form-item
                label={t('最大文件个数')}
                required
                property='maxFileCount'
              >
                <bk-input
                  type='number'
                  min={0}
                  value={formData.value.maxFileCount}
                  on-change={value => (formData.value.maxFileCount = value)}
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
                />
              </bk-form-item>
              <bk-form-item label={t('备注')}>
                <bk-input
                  type='textarea'
                  value={formData.value.remark}
                  on-change={value => (formData.value.remark = value)}
                />
              </bk-form-item>
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
            </bk-form>
          </div>
        </template>
      </bk-sideslider>
    );
  },
});
