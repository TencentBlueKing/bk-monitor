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
import { computed, defineComponent, onMounted, provide, reactive, readonly, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';
import { Button, DatePicker, Input, Switcher, TagInput } from 'bkui-vue';
import { random } from 'lodash';

import { createDutyRule, retrieveDutyRule, updateDutyRule } from '../../../monitor-api/modules/model';
import { getReceiver } from '../../../monitor-api/modules/notice_group';
import { previewDutyRulePlan } from '../../../monitor-api/modules/user_groups';
import NavBar from '../../components/nav-bar/nav-bar';

import { getCalendar, setPreviewDataOfServer } from './components/calendar-preview';
import FixedRotationTab, { FixedDataModel } from './components/fixed-rotation-tab';
import FormItem from './components/form-item';
import ReplaceRotationTab, { ReplaceDataModel } from './components/replace-rotation-tab';
import RotationCalendarPreview from './components/rotation-calendar-preview';
import { RotationSelectTypeEnum, RotationTabTypeEnum } from './typings/common';
import { fixedRotationTransform, replaceRotationTransform } from './utils';

import './rotation-config.scss';

interface RotationTypeData {
  [RotationTabTypeEnum.REGULAR]: FixedDataModel[];
  [RotationTabTypeEnum.HANDOFF]: ReplaceDataModel;
}

export default defineComponent({
  name: 'RotationConfig',
  setup() {
    const { t } = useI18n();
    const router = useRouter();
    const route = useRoute();
    const id = computed(() => route.params.id);
    /* 路由 */
    const navList = computed(() => {
      return [{ name: id.value ? t('route-编辑轮值') : t('route-新增轮值'), id: '' }];
    });
    const formData = reactive({
      name: '',
      labels: [],
      enabled: true,
      effective: {
        startTime: '',
        endTime: ''
      }
    });
    const previewData = ref([]);
    const loading = ref(false);
    /**
     * 表单错误信息
     */
    const errMsg = reactive({
      name: '',
      effective: '',
      rotationType: ''
    });

    function handleEffectiveChange(val: string, type: 'startTime' | 'endTime') {
      formData.effective[type] = val;
      getPreviewData();
    }

    // --------------轮值类型-------------------
    const defaultUserGroup = ref([]);
    provide('defaultGroup', readonly(defaultUserGroup));
    const rotationType = ref<RotationTabTypeEnum>(RotationTabTypeEnum.REGULAR);
    const fixedRotationTabRef = ref<InstanceType<typeof FixedRotationTab>>();
    const replaceRotationTabRef = ref<InstanceType<typeof ReplaceRotationTab>>();
    const rotationTypeData = reactive<RotationTypeData>(createDefaultRotation());
    function handleRotationTypeDataChange<T extends RotationTabTypeEnum>(val: RotationTypeData[T], type: T) {
      rotationTypeData[type] = val;
      getPreviewData();
    }

    function handleRotationTabChange(type: RotationTabTypeEnum) {
      rotationType.value = type;
      Object.assign(rotationTypeData, createDefaultRotation());
      previewData.value = [];
    }

    function handleRotationDataReset<T extends RotationTabTypeEnum>(val: RotationTypeData[T], type: T) {
      rotationTypeData[type] = val;
      previewData.value = [];
    }

    function getGroupList() {
      getReceiver().then(data => {
        defaultUserGroup.value = data;
      });
    }
    function createDefaultRotation(): RotationTypeData {
      return {
        regular: [],
        handoff: {
          id: undefined,
          date: {
            type: RotationSelectTypeEnum.WorkDay,
            workTimeType: 'time_range',
            isCustom: false,
            customTab: 'duration',
            customWorkDays: [],
            periodSettings: { unit: 'day', duration: 1 },
            value: [{ key: random(8, true), workTime: [], workDays: [1, 2, 3, 4, 5] }]
          },
          users: {
            type: 'specified',
            groupNumber: 1,
            value: [{ key: random(8, true), value: [] }]
          }
        }
      };
    }

    // -----------------表单----------------
    /**
     * 表单校验
     * @returns 是否校验成功
     */
    function validate() {
      let valid = true;
      const rotationValid = validRotationRule();
      // 清空错误信息
      Object.keys(errMsg).forEach(key => (errMsg[key] = ''));
      // 轮值类型
      if (rotationValid.err) {
        errMsg.rotationType = rotationValid.msg;
        valid = false;
      }
      // 生效时间范围
      if (!formData.effective.startTime) {
        errMsg.effective = t('生效起始时间必填');
        valid = false;
      }
      // 规则名称
      if (!formData.name) {
        errMsg.name = t('必填项');
        valid = false;
      }
      return valid;
    }

    function validRotationRule() {
      const res = { err: false, msg: '' };
      if (rotationType.value === RotationTabTypeEnum.REGULAR) {
        const data = rotationTypeData[RotationTabTypeEnum.REGULAR];
        const hasUsers = data.every(item => item.users.length);
        if (!hasUsers || !data.length) {
          res.err = true;
          res.msg = t('每条轮值规则最少添加一个用户');
        }
      } else {
        const data = rotationTypeData[RotationTabTypeEnum.HANDOFF];
        const hasUsers = data.users.value.some(item => item.value.length);
        if (!hasUsers) {
          res.err = true;
          res.msg = t('每条轮值规则最少添加一个用户');
        }
        const type = data.date.isCustom ? RotationSelectTypeEnum.Custom : data.date.type;
        switch (type) {
          case RotationSelectTypeEnum.Daily:
          case RotationSelectTypeEnum.WorkDay:
          case RotationSelectTypeEnum.Weekend: {
            if (!data.date.value.some(item => item.workTime.length)) {
              res.err = true;
              res.msg = t('最少选择一个单班时间');
            }
          }
          case RotationSelectTypeEnum.Weekly:
          case RotationSelectTypeEnum.Monthly: {
            if (data.date.workTimeType === 'time_range' && !data.date.value.some(item => item.workDays.length)) {
              res.msg = t('最少选择一个单班时间');
            }
            if (data.date.workTimeType === 'datetime_range' && !data.date.value.some(item => item.workTime.length)) {
              res.msg = t('最少添加一个单班时间');
            }
          }
        }
      }
      return res;
    }

    function getParams() {
      let dutyArranges;
      // 轮值类型数据转化
      if (rotationType.value === RotationTabTypeEnum.REGULAR) {
        dutyArranges = fixedRotationTransform(rotationTypeData.regular, 'params');
      } else {
        dutyArranges = replaceRotationTransform(rotationTypeData.handoff, 'params');
      }
      const { name, labels, effective, enabled } = formData;
      const params = {
        id: id.value,
        name,
        category: rotationType.value,
        labels,
        enabled,
        duty_arranges: dutyArranges,
        effective_time: effective.startTime,
        end_time: effective.endTime
      };
      return params;
    }

    function handleSubmit() {
      if (!validate()) return;
      const params = getParams();
      loading.value = true;
      const req = id.value ? updateDutyRule(id.value, params) : createDutyRule(params);
      req
        .then(() => {
          router.push({ name: 'rotation' });
        })
        .finally(() => {
          loading.value = false;
        });
    }

    function getData() {
      retrieveDutyRule(id.value).then(res => {
        rotationType.value = res.category;
        formData.name = res.name;
        formData.labels = res.labels;
        formData.enabled = res.enabled;
        formData.effective.startTime = res.effective_time || '';
        formData.effective.endTime = res.end_time || '';
        if (res.category === 'regular') {
          rotationTypeData.regular = fixedRotationTransform(res.duty_arranges, 'data');
        } else {
          rotationTypeData.handoff = replaceRotationTransform(res.duty_arranges, 'data');
        }
        getPreviewData(true);
      });
    }

    /**
     * @description 获取预览数据
     */
    async function getPreviewData(init = false) {
      if (!validate()) {
        previewData.value = [];
        return;
      }
      const startDate = getCalendar()[0][0];
      const beginTime = `${startDate.year}-${startDate.month + 1}-${startDate.day} 00:00:00`;
      if (init) {
        const params = {
          source_type: 'DB',
          id: id.value,
          begin_time: beginTime,
          days: 42
        };
        const data = await previewDutyRulePlan(params).catch(() => []);
        previewData.value = setPreviewDataOfServer(data);
      } else {
        const dutyParams = getParams();
        const params = {
          begin_time: beginTime,
          days: 42,
          source_type: 'API',
          config: dutyParams
        };
        const data = await previewDutyRulePlan(params, { needCancel: true }).catch(() => []);
        previewData.value = setPreviewDataOfServer(data);
      }
    }

    onMounted(() => {
      id.value && getData();
      getGroupList();
    });

    function handleBack() {
      router.push({
        name: 'rotation'
      });
    }

    function handleBackPage() {
      router.back();
    }

    return {
      t,
      navList,
      formData,
      errMsg,
      handleEffectiveChange,
      rotationType,
      fixedRotationTabRef,
      replaceRotationTabRef,
      rotationTypeData,
      handleRotationTabChange,
      previewData,
      getPreviewData,
      loading,
      handleRotationTypeDataChange,
      handleRotationDataReset,
      handleSubmit,
      handleBack,
      handleBackPage
    };
  },
  render() {
    return (
      <div class='rotation-config-page'>
        <NavBar
          routeList={this.navList}
          needBack={true}
          callbackRouterBack={this.handleBack}
        ></NavBar>
        <div class='rotation-config-page-content'>
          <FormItem
            label={this.t('规则名称')}
            require
            class='mt-24'
            errMsg={this.errMsg.name}
          >
            <Input
              class='width-508'
              v-model={this.formData.name}
            ></Input>
          </FormItem>
          <FormItem
            label={this.t('标签')}
            class='mt-24'
          >
            <TagInput
              class='width-508'
              v-model={this.formData.labels}
              allowCreate
            ></TagInput>
          </FormItem>
          <FormItem
            label={this.t('启/停')}
            class='mt-24'
          >
            <div class='enabled-switch'>
              <Switcher
                theme='primary'
                v-model={this.formData.enabled}
              ></Switcher>
            </div>
          </FormItem>
          <FormItem
            label={this.t('轮值类型')}
            require
            errMsg={this.errMsg.rotationType}
            class='mt-24'
          >
            <div class='rotation-type-wrapper'>
              <div class='tab-list'>
                <div
                  class={['tab-list-item fixed', this.rotationType === RotationTabTypeEnum.REGULAR && 'active']}
                  onClick={() => this.handleRotationTabChange(RotationTabTypeEnum.REGULAR)}
                >
                  {this.t('固定值班')}
                </div>
                <div
                  class={['tab-list-item replace', this.rotationType === RotationTabTypeEnum.HANDOFF && 'active']}
                  onClick={() => this.handleRotationTabChange(RotationTabTypeEnum.HANDOFF)}
                >
                  {this.t('交替轮值')}
                </div>
              </div>
              <div class='tab-content'>
                {this.rotationType === RotationTabTypeEnum.REGULAR ? (
                  <FixedRotationTab
                    ref='fixedRotationTabRef'
                    data={this.rotationTypeData.regular}
                    onChange={val => this.handleRotationTypeDataChange(val, RotationTabTypeEnum.REGULAR)}
                    onReset={val => this.handleRotationDataReset(val, RotationTabTypeEnum.REGULAR)}
                  />
                ) : (
                  <ReplaceRotationTab
                    ref='replaceRotationTabRef'
                    v-show={this.rotationType === RotationTabTypeEnum.HANDOFF}
                    data={this.rotationTypeData.handoff}
                    onChange={val => this.handleRotationTypeDataChange(val, RotationTabTypeEnum.HANDOFF)}
                    onReset={val => this.handleRotationDataReset(val, RotationTabTypeEnum.HANDOFF)}
                    onDrop={this.getPreviewData}
                  />
                )}
              </div>
            </div>
          </FormItem>
          <FormItem
            label={this.t('生效时间范围')}
            require
            class='mt-24'
            errMsg={this.errMsg.effective}
          >
            <DatePicker
              modelValue={this.formData.effective.startTime}
              clearable
              type='datetime'
              placeholder={`${this.t('如')}: 2019-01-30 12:12:21`}
              onChange={val => this.handleEffectiveChange(val, 'startTime')}
            ></DatePicker>
            <span class='split-line'>-</span>
            <DatePicker
              class='effective-end'
              modelValue={this.formData.effective.endTime}
              clearable
              type='datetime'
              placeholder={this.t('永久')}
              onChange={val => this.handleEffectiveChange(val, 'endTime')}
            ></DatePicker>
          </FormItem>
          <FormItem
            label={this.t('轮值预览')}
            class='mt-24'
          >
            <RotationCalendarPreview
              class='width-974'
              value={this.previewData}
            ></RotationCalendarPreview>
          </FormItem>
          <FormItem class='mt-32'>
            <Button
              theme='primary'
              class='mr-8 width-88'
              onClick={this.handleSubmit}
              loading={this.loading}
            >
              {this.t('提交')}
            </Button>
            <Button
              class='width-88'
              onClick={this.handleBack}
            >
              {this.t('取消')}
            </Button>
          </FormItem>
        </div>
      </div>
    );
  }
});
