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

import { Button, DatePicker, Input, Popover, Switcher, TagInput } from 'bkui-vue';
import dayjs from 'dayjs';
import { createDutyRule, retrieveDutyRule, updateDutyRule } from 'monitor-api/modules/model';
import { getReceiver } from 'monitor-api/modules/notice_group';
import { previewDutyRulePlan } from 'monitor-api/modules/user_groups';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import NavBar from '../../components/nav-bar/nav-bar';
import {
  getAutoOrderList,
  getPreviewParams,
  noOrderDutyData,
  setPreviewDataOfServer,
} from './components/calendar-preview';
import FixedRotationTab, { type FixedDataModel } from './components/fixed-rotation-tab';
import FormItem from './components/form-item';
import ReplaceRotationTab, { type ReplaceDataModel } from './components/replace-rotation-tab';
import RotationCalendarPreview from './components/rotation-calendar-preview';
import { RotationTabTypeEnum } from './typings/common';
import {
  createColorList,
  fixedRotationTransform,
  replaceRotationTransform,
  validFixedRotationData,
  validReplaceRotationData,
} from './utils';

import './rotation-config.scss';

interface RotationTypeData {
  [RotationTabTypeEnum.HANDOFF]: ReplaceDataModel[];
  [RotationTabTypeEnum.REGULAR]: FixedDataModel[];
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
        startTime: dayjs().format('YYYY-MM-DD HH:mm:ss'),
        endTime: '',
      },
    });
    const previewData = ref([]);
    const loading = ref(false);
    /**
     * 表单错误信息
     */
    const errMsg = reactive({
      name: '',
      effective: '',
      rotationType: '',
    });

    /* 关联告警组数量 */
    const userGroupsCount = ref(0);

    const enabledDisabled = computed(() => !!id.value && formData.enabled && !!userGroupsCount.value);

    function handleEffectiveChange(val: string, type: 'endTime' | 'startTime') {
      formData.effective[type] = val;
      errMsg.effective = validEffective().msg;
      getPreviewData();
    }
    function handleNameBlur() {
      errMsg.name = validName().msg;
    }

    const effectiveEndRef = ref();
    /** 禁止选择今天以前的日期 */
    function disabledDateFn(v) {
      const time = new Date(v).getTime();
      const curTime = new Date().getTime() - 24 * 60 * 60 * 1000;
      return time < curTime;
    }

    /** 取消按钮文本设置为永久 */
    function handleDatePickerOpen(state: boolean) {
      if (state) {
        const ele = effectiveEndRef.value.$el.querySelector('.bk-picker-confirm-action a');
        ele.innerText = t('永久');
        ele.setAttribute('class', 'confirm');
      }
    }

    /** 颜色色板，保持人员列表组和预览一致 */
    const colorList = reactive({
      value: createColorList(),
      setValue: (val: string[]) => {
        colorList.value = val;
      },
    });
    provide('colorList', colorList);

    // --------------轮值类型-------------------
    const defaultUserGroup = ref([]);
    provide('defaultGroup', readonly(defaultUserGroup));
    const rotationType = ref<RotationTabTypeEnum>(RotationTabTypeEnum.REGULAR);
    const fixedRotationTabRef = ref<InstanceType<typeof FixedRotationTab>>();
    const replaceRotationTabRef = ref<InstanceType<typeof ReplaceRotationTab>>();
    const rotationTypeData = reactive<RotationTypeData>(createDefaultRotation());
    function handleRotationTypeDataChange<T extends RotationTabTypeEnum>(val: RotationTypeData[T], type: T) {
      rotationTypeData[type] = val;
      resetEffectiveStartTime();
      resetUsersColor();
      getPreviewData();
    }

    /** 重置生效起始时间 */
    function resetEffectiveStartTime() {
      if (id.value) {
        // 编辑状态下 且 生效结束时间大于此时此刻（永久）， 将生效起始时间修改为此时此刻
        if (!formData.effective.endTime || new Date(formData.effective.endTime).getTime() > new Date().getTime()) {
          formData.effective.startTime = dayjs().format('YYYY-MM-DD HH:mm:ss');
        }
      }
    }

    /** 重置用户组所对应的颜色 */
    function resetUsersColor() {
      let orderIndex = 0;
      rotationTypeData[RotationTabTypeEnum.HANDOFF].forEach(item => {
        item.users.value.forEach(user => {
          const { groupType } = item.users;
          user.orderIndex = orderIndex;
          if (groupType === 'specified') {
            orderIndex += 1;
          } else {
            // 自动分组，每一个人员都算一个颜色
            orderIndex += user.value.length;
          }
          // if (user.value.length) {
          //   user.orderIndex = orderIndex;
          //   if (groupType === 'specified') {
          //     orderIndex += 1;
          //   } else {
          //     // 自动分组，每一个人员都算一个颜色
          //     orderIndex += user.value.length;
          //   }
          // } else {
          //   // 没有选择人员复用上一个人员组颜色
          //   user.orderIndex = orderIndex - 1 < 0 ? 0 : orderIndex - 1;
          // }
        });
      });
      orderIndex = 0;
      rotationTypeData[RotationTabTypeEnum.REGULAR].forEach(item => {
        item.orderIndex = orderIndex;
        orderIndex += 1;
        // if (item.users.length) {
        //   item.orderIndex = orderIndex;
        //   orderIndex += 1;
        // } else {
        //   item.orderIndex = orderIndex - 1 < 0 ? 0 : orderIndex - 1;
        // }
      });
    }

    function handleRotationTabChange(type: RotationTabTypeEnum) {
      rotationType.value = type;
      resetEffectiveStartTime();
      resetUsersColor();
      getPreviewData();
    }

    function handleReplaceUserDrop() {
      resetEffectiveStartTime();
      resetUsersColor();
      getPreviewData();
    }

    function getGroupList() {
      getReceiver().then(data => {
        defaultUserGroup.value = data;
      });
    }
    function createDefaultRotation(): RotationTypeData {
      return {
        regular: [],
        handoff: [],
      };
    }

    // -----------------表单----------------
    /**
     * 表单校验
     * @returns 是否校验成功
     */
    function validate(_type: 'preview' | 'submit' = 'submit') {
      let valid = true;
      // 清空错误信息
      Object.keys(errMsg).forEach(key => (errMsg[key] = ''));
      // 轮值类型
      const rotationValid = validRotationRule();
      if (rotationValid.err) {
        errMsg.rotationType = rotationValid.msg;
        valid = false;
      }
      // 生效时间范围
      const effectiveValid = validEffective();
      if (effectiveValid.err) {
        errMsg.effective = effectiveValid.msg;
        valid = false;
      }

      const nameValid = validName();
      if (nameValid.err) {
        errMsg.name = nameValid.msg;
        valid = false;
      }

      return valid;
    }

    function validRotationRule() {
      if (rotationTypeData[rotationType.value].length === 0) return { err: true, msg: t('最少添加一条轮值规则') };
      if (rotationType.value === RotationTabTypeEnum.REGULAR) {
        for (const item of rotationTypeData[RotationTabTypeEnum.REGULAR]) {
          const valid = validFixedRotationData(item);
          if (!valid.success) {
            return { err: true, msg: valid.msg };
          }
        }
      } else {
        for (const item of rotationTypeData[RotationTabTypeEnum.HANDOFF]) {
          const valid = validReplaceRotationData(item);
          if (!valid.success) {
            return { err: true, msg: valid.msg };
          }
        }
      }
      return { err: false, msg: '' };
    }

    function validName() {
      if (!formData.name) return { err: true, msg: t('必填项') };
      if (formData.name.length > 128) return { err: true, msg: t('轮值规则名称长度不能超过128个字符') };
      return { err: false, msg: '' };
    }

    function validEffective() {
      const { startTime, endTime } = formData.effective;
      if (!startTime) return { err: true, msg: t('生效起始时间必填') };
      if (endTime && new Date(endTime).getTime() < new Date(startTime).getTime())
        return { err: true, msg: t('生效结束时间不能小于生效起始时间') };
      if (endTime && disabledDateFn(endTime)) {
        return { err: true, msg: t('生效结束时间不能小于今天') };
      }
      return { err: false, msg: '' };
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
        end_time: effective.endTime,
      };
      return params;
    }

    function handleSubmit() {
      // 所有添加的轮值都必须填写完整
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
        userGroupsCount.value = res.user_groups_count;
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
        resetUsersColor();
        getPreviewData(true);
      });
    }

    /** 获取预览所需要的颜色列表 */
    function getPreviewColorList() {
      // 必须通过校验的规则且添加了人员
      const orderIndex = [];
      if (rotationType.value === RotationTabTypeEnum.REGULAR) {
        rotationTypeData[rotationType.value].forEach(item => {
          if (validFixedRotationData(item).success && item.users.length) orderIndex.push(item.orderIndex);
        });
      } else {
        rotationTypeData[rotationType.value].forEach(item => {
          if (validReplaceRotationData(item).success) {
            const { value, groupType } = item.users;
            value.forEach(user => {
              // 手动分组且有人员，直接把orderIndex存入
              if (groupType === 'specified') {
                user.value.length && orderIndex.push(user.orderIndex);
              } else {
                value.forEach(user => {
                  user.value.forEach((item, ind) => {
                    // 自动分组，需要把每个人员的索引加上orderIndex再存入
                    orderIndex.push(user.orderIndex + ind);
                  });
                });
              }
            });
          }
        });
      }
      return orderIndex.map(index => colorList.value[index]);
    }

    /**
     * @description 获取预览数据
     */
    async function getPreviewData(init = false) {
      if (init) {
        const params = {
          ...getPreviewParams(formData.effective.startTime),
          source_type: 'DB',
          id: id.value,
        };
        const data = await previewDutyRulePlan(params).catch(() => []);
        const dutyParams = getParams();
        const autoOrders = getAutoOrderList(dutyParams);
        previewData.value = setPreviewDataOfServer(
          dutyParams.category === 'regular' ? noOrderDutyData(data) : data,
          autoOrders,
          getPreviewColorList()
        );
      } else {
        const dutyParams = getParams();
        const params = {
          ...getPreviewParams(formData.effective.startTime),
          source_type: 'API',
          config: dutyParams,
        };
        const data = await previewDutyRulePlan(params, { needCancel: true }).catch(() => []);
        const autoOrders = getAutoOrderList(dutyParams);
        previewData.value = setPreviewDataOfServer(
          dutyParams.category === 'regular' ? noOrderDutyData(data) : data,
          autoOrders,
          getPreviewColorList()
        );
      }
    }

    onMounted(() => {
      id.value && getData();
      getGroupList();
    });

    function handleBack() {
      router.push({
        name: 'rotation',
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
      handleNameBlur,
      effectiveEndRef,
      handleDatePickerOpen,
      handleEffectiveChange,
      rotationType,
      fixedRotationTabRef,
      replaceRotationTabRef,
      rotationTypeData,
      handleReplaceUserDrop,
      handleRotationTabChange,
      previewData,
      getPreviewData,
      loading,
      enabledDisabled,
      handleRotationTypeDataChange,
      handleSubmit,
      handleBack,
      handleBackPage,
      disabledDateFn,
    };
  },
  render() {
    return (
      <div class='rotation-config-page'>
        <NavBar
          callbackRouterBack={this.handleBackPage}
          needBack={true}
          routeList={this.navList}
        />
        <div class='rotation-config-page-content'>
          <FormItem
            class='mt-24'
            errMsg={this.errMsg.name}
            label={this.t('规则名称')}
            require
          >
            <Input
              class='width-508'
              v-model={this.formData.name}
              showOverflowTooltips={false}
              onBlur={this.handleNameBlur}
            />
          </FormItem>
          <FormItem
            class='mt-24'
            label={this.t('标签')}
          >
            <TagInput
              class='width-508'
              v-model={this.formData.labels}
              allowCreate
            />
          </FormItem>
          <FormItem
            class='mt-24'
            label={this.t('启/停')}
          >
            <div class='enabled-switch'>
              <Popover
                arrow={true}
                disabled={!this.enabledDisabled}
                placement='top'
                popoverDelay={[300, 0]}
                trigger={'hover'}
              >
                {{
                  default: () => (
                    <Switcher
                      v-model={this.formData.enabled}
                      disabled={this.enabledDisabled}
                      theme='primary'
                    />
                  ),
                  content: () => <span>{this.t('存在关联的告警组')}</span>,
                }}
              </Popover>
            </div>
          </FormItem>
          <FormItem
            class='mt-24'
            errMsg={this.errMsg.rotationType}
            label={this.t('轮值类型')}
            require
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
                  />
                ) : (
                  <ReplaceRotationTab
                    ref='replaceRotationTabRef'
                    v-show={this.rotationType === RotationTabTypeEnum.HANDOFF}
                    data={this.rotationTypeData.handoff}
                    onChange={val => this.handleRotationTypeDataChange(val, RotationTabTypeEnum.HANDOFF)}
                    onDrop={() => this.handleReplaceUserDrop()}
                  />
                )}
              </div>
            </div>
          </FormItem>
          <FormItem
            class='mt-24'
            errMsg={this.errMsg.effective}
            label={this.t('生效时间范围')}
            require
          >
            <DatePicker
              appendToBody={true}
              clearable={false}
              disabledDate={this.disabledDateFn}
              modelValue={this.formData.effective.startTime}
              placeholder={`${this.t('如')}: 2019-01-30 12:12:21`}
              type='datetime'
              onChange={val => this.handleEffectiveChange(val, 'startTime')}
            />
            <span class='split-line'>-</span>
            <DatePicker
              ref='effectiveEndRef'
              class='effective-end'
              appendToBody={true}
              disabledDate={this.disabledDateFn}
              modelValue={this.formData.effective.endTime}
              placeholder={this.t('永久')}
              type='datetime'
              clearable
              onChange={val => this.handleEffectiveChange(val, 'endTime')}
              onOpen-change={this.handleDatePickerOpen}
            />
          </FormItem>
          <FormItem
            class='mt-24'
            contentCls={'flex1'}
            label={this.t('轮值预览')}
          >
            <RotationCalendarPreview
              class='min-width-974'
              value={this.previewData}
            />
          </FormItem>
          <FormItem class='mt-32'>
            <Button
              class='mr-8 width-88'
              loading={this.loading}
              theme='primary'
              onClick={this.handleSubmit}
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
  },
});
