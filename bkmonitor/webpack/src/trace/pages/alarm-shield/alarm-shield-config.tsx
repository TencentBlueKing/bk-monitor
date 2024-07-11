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
import { defineComponent, reactive, ref, shallowRef } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import { Button, Checkbox, Input, Loading, Message, Select, Switcher } from 'bkui-vue';
import dayjs from 'dayjs';
import { getNoticeWay, getReceiver } from 'monitor-api/modules/notice_group';
import { addShield, editShield, frontendCloneInfo, frontendShieldDetail } from 'monitor-api/modules/shield';
import { deepClone, random } from 'monitor-common/utils';

import { transformMonitorToValue, transformValueToMonitor } from '../../components/monitor-ip-selector/utils';
import NavBar from '../../components/nav-bar/nav-bar';
import { useAppStore } from '../../store/modules/app';
import AlarmShieldConfigDimension, { dimensionPropData } from './alarm-shield-config-dimension';
import AlarmShieldConfigScope, { scopeData as scopeDataParams } from './alarm-shield-config-scope';
import AlarmShieldConfigStrategy, { strategyDataProp } from './alarm-shield-config-strategy';
import FormItem from './components/form-item';
import MemberSelector from './components/member-selector';
import ScopeDateConfig from './components/scope-date-config';
import {
  categoryMap,
  EShieldCycle,
  EShieldType,
  INoticeDate,
  Ipv6FieldMap,
  ShieldDetailTargetFieldMap,
  ShieldDimension2NodeType,
} from './typing';

import './alarm-shield-config.scss';

interface ITabData {
  active: EShieldType;
  list: { name: string; id: EShieldType }[];
}

export default defineComponent({
  name: 'AlarmShieldConfig',
  props: {
    id: {
      type: String,
      default: '',
    },
    type: {
      type: String,
      default: '',
    },
  },
  setup() {
    const { t } = useI18n();
    const userApi = `${location.origin}${location.pathname || '/'}rest/v2/commons/user/list_users/`;
    const store = useAppStore();
    const router = useRouter();
    const route = useRoute();
    const bizList = shallowRef(store.bizList.filter(item => +item.bk_biz_id === +store.bizId));
    const scopeRef = ref<InstanceType<typeof AlarmShieldConfigScope>>(null);
    const strategyRef = ref<InstanceType<typeof AlarmShieldConfigStrategy>>(null);
    const dimensionRef = ref<InstanceType<typeof AlarmShieldConfigDimension>>(null);
    const dateRef = ref<InstanceType<typeof ScopeDateConfig>>(null);
    const isEdit = ref(false);
    const isClone = ref(false);
    const loading = ref(false);
    /* 表单数据 */
    const formData = reactive({
      bizId: store.bizId,
      desc: '',
      notificationMethod: [],
      noticeNumber: 5,
      noticeMember: [],
    });
    /* 屏蔽时间范围 */
    const noticeDate = ref<INoticeDate>({
      key: random(8),
      shieldCycle: EShieldCycle.single,
      dateRange: [],
      [EShieldCycle.single]: {
        list: [],
        range: [],
      },
      [EShieldCycle.day]: {
        list: [],
        range: ['00:00:00', '23:59:59'],
      },
      [EShieldCycle.week]: {
        list: [],
        range: ['00:00:00', '23:59:59'],
      },
      [EShieldCycle.month]: {
        list: [],
        range: ['00:00:00', '23:59:59'],
      },
    });
    const tabData = reactive<ITabData>({
      active: EShieldType.Scope,
      list: [
        { name: t('基于范围屏蔽'), id: EShieldType.Scope },
        { name: t('基于策略屏蔽'), id: EShieldType.Strategy },
        { name: t('基于告警事件屏蔽'), id: EShieldType.Event },
        { name: t('基于维度屏蔽'), id: EShieldType.Dimension },
      ],
    });
    /* 屏蔽范围数据 */
    const scopeData = ref(scopeDataParams());
    /* 策略屏蔽数据 */
    const strategyShieldData = ref(strategyDataProp());
    /* 维度屏蔽数据 */
    const dimensionShieldData = ref(dimensionPropData());
    /* 告警事件数据 */
    const eventShieldData = reactive({
      dimensions: '',
      eventMessage: '',
    });
    /* 屏蔽详情数据 */
    const shieldData = shallowRef(null);
    /* 通知设置 */
    const showNoticeConfig = ref(false);
    const noticeWays = ref([]);
    /* 用户组 */
    const defaultGroupList = ref([]);
    /* 路由 */
    const navList = ref([{ name: t('新建屏蔽'), id: '' }]);

    const errMsg = reactive({
      noticeMember: '',
      notificationMethod: '',
    });
    async function init() {
      loading.value = true;
      const ways = await getNoticeWay({ bk_biz_id: formData.bizId }).catch(() => []);
      noticeWays.value = ways.filter(item => item.channel === 'user');
      await getReceiverGroup();
      if (!!route.params?.id) {
        isEdit.value = route.name === 'alarm-shield-edit';
        isClone.value = route.name === 'alarm-shield-clone';
        let api = null;
        if (isEdit.value) {
          navList.value[0].name = `${t('route-编辑屏蔽')} #${route.params.id}`;
          api = frontendShieldDetail;
        } else if (isClone.value) {
          navList.value[0].name = `${t('route-克隆屏蔽')} #${route.params.id}`;
          api = frontendCloneInfo;
        }
        if (api) {
          api({ id: route.params.id })
            .then(data => {
              shieldData.value = data;
              setDetailData(shieldData.value);
            })
            .finally(() => {
              loading.value = false;
            });
        } else {
          loading.value = false;
        }
      } else {
        loading.value = false;
      }
    }
    init();
    /**
     * @description 回填详情数据
     * @param data
     */
    function setDetailData(data) {
      const ipv6Data = () => {
        const targetList = data.dimension_config?.[ShieldDetailTargetFieldMap[data.scope_type]] || [];
        return data.scope_type === 'instance'
          ? {
              [Ipv6FieldMap[data.scope_type]]: targetList.map(id => ({ service_instance_id: id })),
            }
          : transformMonitorToValue(targetList, ShieldDimension2NodeType[data.scope_type]);
      };
      formData.bizId = data.bk_biz_id;
      bizList.value = store.bizList.filter(item => +item.bk_biz_id === +data.bk_biz_id);
      /* 范围屏蔽（目标范围） */
      if (data.category === 'scope') {
        tabData.active = EShieldType.Scope;
        scopeData.value.biz.value = data.bk_biz_id;
        scopeData.value.bkGroup.value = data.scope_type;
        if (data.scope_type !== 'biz') {
          scopeData.value.tableData = data.dimension_config.target.map(item => ({ name: item }));
          scopeData.value.ipv6Value = ipv6Data();
          scopeData.value.originIpv6Value = deepClone(scopeData.value.ipv6Value);
        }
        scopeData.value.key = random(8);
      } else if (data.category === 'strategy') {
        // 策略屏蔽
        tabData.active = EShieldType.Strategy;
        strategyShieldData.value.id = data.dimension_config.strategies.map(item => item.id);
        strategyShieldData.value.level = data.dimension_config.level;
        strategyShieldData.value.dimension_conditions = data.dimension_config.dimension_conditions;
        if (data.dimension_config.target?.length) {
          strategyShieldData.value.scopeData.biz.value = data.bk_biz_id;
          strategyShieldData.value.scopeData.bkGroup.value = data.dimension_config.scope_type;
          strategyShieldData.value.scopeData.tableData = data.dimension_config.target.map(item => ({ name: item }));
          strategyShieldData.value.scopeData.ipv6Value = ipv6Data();
          strategyShieldData.value.scopeData.originIpv6Value = deepClone(strategyShieldData.value.scopeData.ipv6Value);
        }
        strategyShieldData.value.key = random(8);
      } else if (data.category === 'dimension') {
        // 维度屏蔽
        tabData.active = EShieldType.Dimension;
        dimensionShieldData.value.dimension_conditions = data.dimension_config.dimension_conditions;
        dimensionShieldData.value.key = random(8);
      } else if (data.category === 'alert') {
        tabData.active = EShieldType.Event;
        eventShieldData.dimensions = data.dimension_config.dimensions;
        eventShieldData.eventMessage = data.dimension_config.event_message;
      }
      /* 回填屏蔽周期数据 */
      const cycleConfig = data.cycle_config;
      const cycleMap = { 1: EShieldCycle.single, 2: EShieldCycle.day, 3: EShieldCycle.week, 4: EShieldCycle.month };
      const type = cycleMap[cycleConfig.type];
      const isSingle = cycleConfig.type === 1;
      noticeDate.value.shieldCycle = type;
      noticeDate.value[type] = {
        list: [...cycleConfig.day_list, ...cycleConfig.week_list],
        range: isSingle ? [data.begin_time, data.end_time] : [cycleConfig.begin_time, cycleConfig.end_time],
      };
      noticeDate.value.dateRange = isSingle ? [] : [data.begin_time, data.end_time];
      noticeDate.value.key = random(8);
      /* 屏蔽原因 */
      formData.desc = data.description;
      /* 通知设置 */
      if (data.shield_notice) {
        showNoticeConfig.value = true;
        formData.notificationMethod = data.notice_config.notice_way;
        formData.noticeNumber = data.notice_config.notice_time;
        formData.noticeMember = data.notice_config.notice_receiver.map(item => item.id);
      }
    }
    function handleShieldTypeChange(item) {
      tabData.active = item.id;
    }
    /**
     * @description 获取通知数据
     * @returns
     */
    async function getReceiverGroup() {
      await getReceiver().then(data => {
        const groupData = data.find(item => item.id === 'group');
        defaultGroupList.value.push(groupData);
      });
    }
    /**
     * @description 通知设置校验
     * @returns boolean
     */
    function noticeConfigValidate() {
      if (showNoticeConfig.value) {
        if (!formData.noticeMember.length) {
          errMsg.noticeMember = t('至少添加一个通知对象');
        }
        if (!formData.notificationMethod.length) {
          errMsg.notificationMethod = t('至少添加一个通知方式');
        }
      }
      return !Object.keys(errMsg).some(key => !!errMsg[key]);
    }
    /**
     * @description 校验
     * @returns
     */
    function validate() {
      return new Promise((_resolve, _reject) => {
        const v2 = tabData.active === EShieldType.Event ? true : dateRef.value.validate();
        const v3 = noticeConfigValidate();
        if (tabData.active === EShieldType.Scope) {
          const v1 = isEdit.value ? true : scopeRef.value.validate();
          _resolve(v1 && v2 && v3);
        } else if (tabData.active === EShieldType.Strategy) {
          const v1 = strategyRef.value.validate();
          _resolve(v1 && v2 && v3);
        } else if (tabData.active === EShieldType.Dimension) {
          const v1 = dimensionRef.value.validate();
          _resolve(v1 && v2 && v3);
        } else if (tabData.active === EShieldType.Event) {
          _resolve(v2 && v3);
        }
      });
    }
    /**
     * 获取新增编辑的参数
     * @returns
     */
    function getParams() {
      /* 时间范围参数 */
      const isSingle = noticeDate.value.shieldCycle === EShieldCycle.single;
      const dateRange = [];
      if (!isSingle) {
        dateRange[0] = dayjs.tz(noticeDate.value.dateRange[0]).format('YYYY-MM-DD 00:00:00');
        dateRange[1] = dayjs.tz(noticeDate.value.dateRange[1]).format('YYYY-MM-DD 23:59:59');
      }
      const cycleDate = noticeDate.value[noticeDate.value.shieldCycle];
      const cycleMap = {
        [EShieldCycle.single]: 1,
        [EShieldCycle.day]: 2,
        [EShieldCycle.week]: 3,
        [EShieldCycle.month]: 4,
      };
      const cycleParams = {
        begin_time: isSingle ? cycleDate.range[0] : dateRange[0],
        end_time: isSingle ? cycleDate.range[1] : dateRange[1],
        cycle_config: {
          begin_time: isSingle ? '' : cycleDate.range[0],
          end_time: isSingle ? '' : cycleDate.range[1],
          day_list:
            noticeDate.value.shieldCycle === EShieldCycle.month ? noticeDate.value[EShieldCycle.month].list : [],
          week_list: noticeDate.value.shieldCycle === EShieldCycle.week ? noticeDate.value[EShieldCycle.week].list : [],
          type: cycleMap[noticeDate.value.shieldCycle],
        },
      };
      // 通知设置参数
      const groupList = defaultGroupList.value.find(item => item.id === 'group')?.children || [];
      const memberParams = formData.noticeMember.map(id => {
        const isGroup = groupList.find(group => group.id === id);
        return {
          logo: '',
          display_name: '',
          type: isGroup ? 'group' : 'user',
          id,
        };
      });
      // 所有参数
      const params: any = {
        category: categoryMap[tabData.active],
        ...cycleParams,
        shield_notice: showNoticeConfig.value,
        notice_config: {},
        description: formData.desc,
      };
      // 编辑状态
      if (isEdit.value) {
        params.id = shieldData.value.id;
      }
      // 通知设置
      if (showNoticeConfig.value) {
        params.notice_config = {
          notice_time: formData.noticeNumber,
          notice_way: formData.notificationMethod,
          notice_receiver: memberParams,
        };
      }
      // 范围屏蔽
      if (tabData.active === EShieldType.Scope) {
        const dimension = scopeData.value.bkGroup.value;
        const dimensionConfig = { scope_type: dimension } as any;
        dimensionConfig.target = transformValueToMonitor(
          scopeData.value.ipv6Value,
          ShieldDimension2NodeType[dimension]
        );
        params.dimension_config = dimensionConfig;
      } else if (tabData.active === EShieldType.Strategy) {
        // 策略屏蔽
        const dimensionConfig: any = {
          id: strategyShieldData.value.id,
          level: strategyShieldData.value.level,
          dimension_conditions: strategyShieldData.value.dimension_conditions,
        };
        const target = transformValueToMonitor(
          strategyShieldData.value.scopeData.ipv6Value,
          ShieldDimension2NodeType[strategyShieldData.value.scopeData.bkGroup.value]
        );
        if (target.length) {
          dimensionConfig.scope_type = strategyShieldData.value.scopeData.bkGroup.value;
          dimensionConfig.target = target;
        }
        params.dimension_config = dimensionConfig;
        params.level = strategyShieldData.value.level;
      } else if (tabData.active === EShieldType.Dimension) {
        // 维度屏蔽
        const dimensionConfig = {
          dimension_conditions: dimensionShieldData.value.dimension_conditions,
          strategy_id: dimensionShieldData.value.strategy_id,
        };
        params.dimension_config = dimensionConfig;
      } else if (tabData.active === EShieldType.Event) {
        // 告警事件屏蔽
        params.dimension_config = {};
      }
      return params;
    }
    /**
     * @description 提交
     */
    async function handleSubmit() {
      const isValidate = await validate();
      if (!isValidate) {
        return;
      }
      const params = getParams();
      const api = isEdit.value ? editShield : addShield;
      let msg = t('创建屏蔽成功');
      if (isEdit.value) {
        msg = t('编辑屏蔽成功');
      }
      api(params).then(() => {
        router.push({
          name: 'alarm-shield',
        });
        Message({
          theme: 'success',
          message: msg,
        });
      });
    }

    /**
     * @description 通知对象
     */
    function handleUserChange(v) {
      errMsg.noticeMember = '';
      formData.noticeMember = v;
    }

    function handleNoticeNumberChange(v) {
      formData.noticeNumber = v;
    }
    function handleNotificationMethod(v) {
      errMsg.notificationMethod = '';
      formData.notificationMethod = v;
    }

    function handleNoticeDateChange(v) {
      noticeDate.value = v;
    }
    function handleBackPage() {
      router.back();
    }

    function handleCancel() {
      router.push({
        name: 'alarm-shield',
      });
    }
    function handleShowNoticeConfig(v) {
      showNoticeConfig.value = v;
      errMsg.noticeMember = '';
      errMsg.notificationMethod = '';
    }

    return {
      store,
      t,
      formData,
      defaultGroupList,
      noticeDate,
      shieldData,
      scopeData,
      strategyShieldData,
      route,
      navList,
      loading,
      bizList,
      tabData,
      isEdit,
      strategyRef,
      scopeRef,
      dateRef,
      isClone,
      dimensionRef,
      dimensionShieldData,
      eventShieldData,
      showNoticeConfig,
      errMsg,
      userApi,
      noticeWays,
      handleBackPage,
      handleShieldTypeChange,
      handleNoticeDateChange,
      handleShowNoticeConfig,
      handleUserChange,
      handleNotificationMethod,
      handleNoticeNumberChange,
      handleSubmit,
      handleCancel,
    };
  },
  render() {
    return (
      <>
        <NavBar
          callbackRouterBack={this.handleBackPage}
          needBack={true}
          routeList={this.navList}
        ></NavBar>
        <Loading loading={this.loading}>
          <div class='alarms-shield-config-page'>
            {/* <div class='alarm-shield-tip'>
        <span class='icon-monitor icon-tishi'></span>
        <span class='tip-text'>如果需要对用户提供上传附件的服务，请先在后台先行配置。</span>
      </div> */}
            <div class='shield-config-content'>
              <FormItem
                class='mt24'
                label={this.t('所属')}
                require={true}
              >
                <Select
                  class='width-413'
                  disabled={true}
                  modelValue={this.formData.bizId}
                >
                  {this.bizList.map(item => (
                    <Select.Option
                      id={item.id}
                      key={item.id}
                      name={item.text}
                    ></Select.Option>
                  ))}
                </Select>
              </FormItem>
              <FormItem
                class='mt24'
                label={this.t('屏蔽类型')}
                require={true}
              >
                <Button.ButtonGroup>
                  {this.tabData.list
                    .filter(item => (this.tabData.active !== EShieldType.Event ? item.id !== EShieldType.Event : true))
                    .map(item => (
                      <Button
                        key={item.id}
                        disabled={this.isEdit ? item.id !== this.tabData.active : false}
                        selected={item.id === this.tabData.active}
                        onClick={() => !this.isEdit && this.handleShieldTypeChange(item)}
                      >
                        {item.name}
                      </Button>
                    ))}
                </Button.ButtonGroup>
              </FormItem>
              <AlarmShieldConfigStrategy
                ref='strategyRef'
                isClone={this.isClone}
                isEdit={this.isEdit}
                show={this.tabData.active === EShieldType.Strategy}
                value={this.strategyShieldData}
                onChange={v => (this.strategyShieldData = v)}
              ></AlarmShieldConfigStrategy>
              <AlarmShieldConfigScope
                ref='scopeRef'
                isEdit={this.isEdit}
                show={this.tabData.active === EShieldType.Scope}
                value={this.scopeData}
                onChange={v => (this.scopeData = v)}
              ></AlarmShieldConfigScope>
              <AlarmShieldConfigDimension
                ref='dimensionRef'
                isEdit={this.isEdit}
                show={this.tabData.active === EShieldType.Dimension}
                value={this.dimensionShieldData}
                onChange={v => (this.dimensionShieldData = v)}
              ></AlarmShieldConfigDimension>
              {this.tabData.active === EShieldType.Event && (
                <>
                  <FormItem
                    class='mt24'
                    label={this.t('告警内容')}
                    require={true}
                  >
                    <div class='event-detail-content'>
                      <FormItem label={`${this.t('维度信息')}:`}>
                        <span class='detail-text'>{this.eventShieldData.dimensions}</span>
                      </FormItem>
                      <FormItem label={`${this.t('检测算法')}:`}>
                        <span class='detail-text'>{this.eventShieldData.eventMessage}</span>
                      </FormItem>
                    </div>
                  </FormItem>
                </>
              )}
              {this.tabData.active !== EShieldType.Event && (
                <ScopeDateConfig
                  ref='dateRef'
                  value={this.noticeDate}
                  onChange={v => this.handleNoticeDateChange(v)}
                ></ScopeDateConfig>
              )}
              <FormItem
                class='mt24'
                label={this.t('屏蔽原因')}
              >
                <Input
                  class='width-940'
                  maxlength={100}
                  modelValue={this.formData.desc}
                  rows={3}
                  type='textarea'
                  onUpdate:modelValue={v => (this.formData.desc = v)}
                ></Input>
              </FormItem>
              <FormItem
                class='mt24'
                label={this.t('通知设置')}
              >
                <Switcher
                  class='mt6'
                  modelValue={this.showNoticeConfig}
                  theme='primary'
                  onUpdate:modelValue={v => this.handleShowNoticeConfig(v)}
                ></Switcher>
              </FormItem>
              {!!this.showNoticeConfig && (
                <>
                  <FormItem
                    class='mt24'
                    errMsg={this.errMsg.noticeMember}
                    label={this.t('通知对象')}
                    require={true}
                  >
                    <MemberSelector
                      class='width-940'
                      api={this.userApi}
                      userGroups={this.defaultGroupList}
                      value={this.formData.noticeMember}
                      onChange={this.handleUserChange}
                    ></MemberSelector>
                  </FormItem>
                  <FormItem
                    class='mt24'
                    errMsg={this.errMsg.notificationMethod}
                    label={this.t('通知方式')}
                    require={true}
                  >
                    <Checkbox.Group
                      class='mt8'
                      modelValue={this.formData.notificationMethod}
                      onUpdate:modelValue={v => this.handleNotificationMethod(v)}
                    >
                      {this.noticeWays.map(item => (
                        <Checkbox
                          key={item.type}
                          label={item.type}
                        >
                          {item.label}
                        </Checkbox>
                      ))}
                    </Checkbox.Group>
                  </FormItem>
                  <FormItem
                    class='mt24'
                    label={this.t('通知时间')}
                    require={true}
                  >
                    <div>
                      <i18n-t keypath={'屏蔽开始/结束前{0}分钟发送通知'}>
                        <span class='inline-block'>
                          <Input
                            class='width-68 mlr-10'
                            max={1440}
                            min={1}
                            modelValue={this.formData.noticeNumber}
                            type='number'
                            onUpdate:modelValue={v => this.handleNoticeNumberChange(v)}
                          ></Input>
                        </span>
                      </i18n-t>
                    </div>
                  </FormItem>
                </>
              )}
              <FormItem class='mt32'>
                <Button
                  class='min-w88 mr8'
                  theme={'primary'}
                  onClick={this.handleSubmit}
                >
                  {this.t('确定')}
                </Button>
                <Button
                  class='min-w88'
                  onClick={this.handleCancel}
                >
                  {this.t('取消')}
                </Button>
              </FormItem>
            </div>
          </div>
        </Loading>
      </>
    );
  },
});
