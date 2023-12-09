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
import Vue, { defineComponent, nextTick, onMounted, PropType, reactive, ref, watch } from 'vue';
import { copyText, deepClone, transformDataKey } from '@common/utils';
import dayjs from 'dayjs';

import { getReceiver } from '../../../monitor-api/modules/notice_group';
import MemberSelector from '../../pages/alarm-group/alarm-group-add/member-selector';
// import {  } from '../../../monitor-api/modules/email_subscription';
// import { Scenario } from '../email-subscription-config';
import { Scenario } from '../../pages/my-apply/components/subscription-detail';

import './create-subscription-form.scss';

/** 按天频率 包含周末 */
const INCLUDES_WEEKEND = [1, 2, 3, 4, 5, 6, 7];
/** 按天频率 不包含周末 */
const EXCLUDES_WEEKEND = [1, 2, 3, 4, 5];

export default defineComponent({
  name: 'CreateSubscriptionForm',
  props: {
    // 新增订阅有两种模式，不同模式的表单内容也有所不同。
    mode: {
      type: String as PropType<'normal' | 'quick'>,
      default: 'normal'
    },
    detailInfo: {
      type: Object,
      default: () => {
        return {};
      }
    }
  },
  setup(props) {
    const formData = reactive({
      scenario: 'clustering',
      name: '',
      start_time: '',
      end_time: '',
      // 给他人/自己 订阅 。self, others 仅自己/给他人
      subscripber_type: 'others',
      scenario_config: {
        index_set_id: '',
        // 需要从 slider 上进行转换
        pattern_level: '01',
        log_display_count: 0,
        year_on_year_hour: 0,
        generate_attachment: true
      },
      // 这里不可以直接对组件赋值，不然最后会带上不必要的参数。
      frequency: {
        data_range: null,
        type: 5,
        hour: 0.5,
        run_time: '',
        week_list: [],
        day_list: []
      },
      content_config: {
        title: '',
        is_link_enabled: true
      },
      channels: [
        {
          is_enabled: true,
          subscribers: [],
          channel_name: 'user'
        },
        {
          is_enabled: true,
          subscribers: [],
          channel_name: 'email'
        },
        {
          is_enabled: true,
          subscribers: [],
          channel_name: 'wxbot'
        }
      ],
      timerange: [],
      // 表单的验证的 bug ，后期再考虑删掉
      scenario_config__log_display_count: 0,
      content_config__title: ''
    });
    const formDataRules = {
      frequency: [
        {
          validator: () => {
            switch (formData.frequency.type) {
              case 3:
                return frequency.week_list.length > 0;
              case 2:
                return frequency.day_list.length > 0;
              default:
                return true;
            }
          },
          message: window.i18n.t('必填项'),
          trigger: 'blur'
        }
      ],
      channels: [
        {
          validator: () => {
            console.log('channels v');

            const enabledList = formData.channels.filter(item => item.is_enabled);
            console.log('enabledList', enabledList);

            if (enabledList.length === 0) return false;
            const subscriberList = enabledList.filter(item => item.subscribers.length);
            console.log('subscriberList', subscriberList);

            if (subscriberList.length === 0) return false;
            return true;
          },
          message: window.i18n.t('必填项'),
          trigger: 'blur'
        }
      ],
      scenario_config__log_display_count: [
        {
          required: true,
          message: window.i18n.t('必填项'),
          trigger: 'change'
        },
        {
          validator: () => {
            return Number(formData.scenario_config.log_display_count) >= 0;
          },
          message: window.i18n.t('必需为正整数'),
          // 不要写成数组，会有 bug 。（validate 永远为 true）
          trigger: 'change'
        }
      ],
      content_config__title: [
        {
          required: true,
          message: window.i18n.t('必填项'),
          trigger: 'change'
        }
      ]
    };
    const pattenLevelSlider = ref(0);
    enum PatternLevelEnum {
      '01' = 0,
      '03' = 25,
      '05' = 50,
      '07' = 75,
      '09' = 100
    }
    function handleSliderChange() {
      // const sliderMapping = {
      //   0: '01',
      //   25: '03',
      //   50: '05',
      //   75: '07',
      //   100: '09'
      // };
      formData.scenario_config.pattern_level = PatternLevelEnum[pattenLevelSlider.value] || '01';
    }
    // 时间范围相关 start
    const dataRange = ref('none');
    function handleDataRangeExchange() {
      formData.frequency.data_range = getTimeRangeObj(dataRange.value);
    }
    function getTimeRangeObj(str: string) {
      if (str === 'none') return undefined;
      let res = {
        timeLevel: 'hours',
        number: 24
      };
      const isMatch = str.match(/(\d+)(minutes|hours|days)/);
      if (isMatch) {
        const [, date, level] = isMatch;
        res = {
          timeLevel: level,
          number: +date
        };
      }
      return transformDataKey(res, true);
    }
    watch(
      dataRange,
      () => {
        handleDataRangeExchange();
      },
      {
        immediate: true
      }
    );
    // 时间范围相关 end
    const subscriberInput = reactive({
      user: [],
      email: '',
      wxbot: ''
    });
    watch(
      () => subscriberInput.user,
      () => {
        const result = subscriberInput.user
          .map(item => {
            return {
              id: item,
              is_enabled: true,
              type: 'user'
            };
          })
          .filter(item => item.id);
        formData.channels[0].subscribers = result;
      },
      {
        deep: true
      }
    );
    watch(
      () => subscriberInput.email,
      () => {
        const result = subscriberInput.email
          .split(',')
          .map(item => {
            return {
              id: item,
              is_enabled: true
            };
          })
          .filter(item => item.id);
        formData.channels[1].subscribers = result;
      }
    );
    watch(
      () => subscriberInput.wxbot,
      () => {
        const result = subscriberInput.wxbot
          .split(',')
          .map(item => {
            return {
              id: item,
              is_enabled: true
            };
          })
          .filter(item => item.id);
        formData.channels[2].subscribers = result;
      }
    );

    const isIncludeWeekend = ref(true);
    // watch(
    //   isIncludeWeekend,
    //   () => {
    //     formData.frequency.week_list = isIncludeWeekend.value ? INCLUDES_WEEKEND : EXCLUDES_WEEKEND;
    //   },
    //   {
    //     immediate: true
    //   }
    // );
    // 发送频率相关
    const frequency = reactive({
      type: 5,
      hour: 0.5,
      run_time: dayjs().format('HH:mm:ss'),
      only_once_run_time: dayjs().format('YYYY-MM-DD HH:mm:ss'),
      week_list: [],
      day_list: []
    });
    // 保存时收集一次
    function collectFrequency() {
      // 先手动重置一遍
      Object.assign(formData.frequency, {
        hour: 0,
        run_time: '',
        week_list: [],
        day_list: []
      });
      switch (formData.frequency.type) {
        case 5:
          Object.assign(formData.frequency, {
            hour: frequency.hour
          });
          break;
        case 4:
          Object.assign(formData.frequency, {
            run_time: frequency.run_time,
            week_list: isIncludeWeekend.value ? INCLUDES_WEEKEND : EXCLUDES_WEEKEND
          });
          break;
        case 3:
          Object.assign(formData.frequency, {
            run_time: frequency.run_time,
            week_list: frequency.week_list
          });
          break;
        case 2:
          Object.assign(formData.frequency, {
            run_time: frequency.run_time,
            day_list: frequency.day_list
          });
          break;
        case 1:
          Object.assign(formData.frequency, {
            run_time: frequency.only_once_run_time
          });
          break;
        default:
          break;
      }
    }
    // 备用方案
    function handleTimeRangeChange(v) {
      console.log('handleTimeRangeChange', v);
      console.log(v.filter(item => !!item));

      if (v.filter(item => !!item).length < 2) {
        formData.timerange = [];
        return;
      }
      formData.timerange = deepClone(v);
      const result = v.map(date => {
        return dayjs(date).unix();
      });
      console.log(result);
      // eslint-disable-next-line @typescript-eslint/naming-convention
      const [start_time, end_time] = result;
      formData.start_time = start_time;
      formData.end_time = end_time;
    }
    const subscribeFor = ref<'self' | 'others'>('self');
    const hourOption = [
      {
        id: 0.5,
        name: window.i18n.t('0.5小时')
      },
      {
        id: 1,
        name: window.i18n.t('1小时')
      },
      {
        id: 2,
        name: window.i18n.t('2小时')
      },
      {
        id: 6,
        name: window.i18n.t('6小时')
      },
      {
        id: 12,
        name: window.i18n.t('12小时')
      }
    ];
    const customSliderContent = {
      0: {
        label: '01'
      },
      25: {
        label: '03'
      },
      50: {
        label: '05'
      },
      75: {
        label: '07'
      },
      100: {
        label: '09'
      }
    };
    const weekList = [
      { name: window.i18n.t('星期一'), id: 1 },
      { name: window.i18n.t('星期二'), id: 2 },
      { name: window.i18n.t('星期三'), id: 3 },
      { name: window.i18n.t('星期四'), id: 4 },
      { name: window.i18n.t('星期五'), id: 5 },
      { name: window.i18n.t('星期六'), id: 6 },
      { name: window.i18n.t('星期日'), id: 7 }
    ];
    const indexSetIDList = ref([]);
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const YOYList = ref([
      {
        id: 0,
        name: window.i18n.t('不比对')
      },
      {
        id: 1,
        name: window.i18n.t('1小时前')
      },
      {
        id: 2,
        name: window.i18n.t('2小时前')
      },
      {
        id: 3,
        name: window.i18n.t('3小时前')
      },
      {
        id: 6,
        name: window.i18n.t('6小时前')
      },
      {
        id: 12,
        name: window.i18n.t('12小时前')
      },
      {
        id: 24,
        name: window.i18n.t('24小时前')
      }
    ]);
    const timeRangeOption = [
      {
        id: 'none',
        name: window.i18n.t('按发送频率')
      },
      {
        id: '5minutes',
        name: window.i18n.t('近{n}分钟', { n: 5 })
      },
      {
        id: '15minutes',
        name: window.i18n.t('近{n}分钟', { n: 15 })
      },
      {
        id: '30minutes',
        name: window.i18n.t('近{n}分钟', { n: 30 })
      },
      {
        id: '1hours',
        name: window.i18n.t('近{n}小时', { n: 1 })
      },
      {
        id: '3hours',
        name: window.i18n.t('近{n}小时', { n: 3 })
      },
      {
        id: '6hours',
        name: window.i18n.t('近{n}小时', { n: 6 })
      },
      {
        id: '12hours',
        name: window.i18n.t('近{n}小时', { n: 12 })
      },
      {
        id: '24hours',
        name: window.i18n.t('近{n}小时', { n: 24 })
      },
      {
        id: '2days',
        name: window.i18n.t('近 {n} 天', { n: 2 })
      },
      {
        id: '7days',
        name: window.i18n.t('近 {n} 天', { n: 7 })
      },
      {
        id: '30days',
        name: window.i18n.t('近 {n} 天', { n: 30 })
      }
    ];
    const refOfContentForm = ref();
    const refOfEmailSubscription = ref();
    const refOfSendingConfigurationForm = ref();
    function validateAllForms() {
      return Promise.all([
        refOfContentForm.value?.validate?.(),
        refOfEmailSubscription.value?.validate?.(),
        refOfSendingConfigurationForm.value?.validate?.()
      ]).then(() => {
        return formData;
      });
    }

    const isShowAdvancedOption = ref(true);
    const isShowYOY = ref(true);

    const variableTable = reactive({
      data: [
        {
          variable: '{username}',
          description: '用户名称',
          example: 'Peter'
        },
        {
          variable: '{time}',
          description: '系统时间',
          example: '2023.10.1'
        },
        {
          variable: '{indicesname}',
          description: '索引集名称',
          example: 'apm_demo_app_8004'
        }
      ],
      columns: {
        fields: [
          {
            label: `${window.i18n.t('订阅名称')}`,
            render: ({ data }) => {
              return (
                <div>
                  {data.variable}
                  <i
                    class='icon-monitor icon-mc-copy'
                    style={{ fontSize: '16px', marginLeft: '5px', color: '#3A84FF', cursor: 'pointer' }}
                    onClick={() => {
                      handleCopy(data.variable);
                    }}
                  ></i>
                </div>
              );
            }
          },
          {
            label: `${window.i18n.t('变量说明')}`,
            field: 'description'
          },
          {
            label: `${window.i18n.t('示例')}`,
            field: 'example'
          }
        ]
      }
    });
    /**
     * @desc 拷贝操作
     * @param { * } val
     */
    function handleCopy(text) {
      copyText(text, msg => {
        Vue.prototype.$bkMessage({
          message: msg,
          theme: 'error'
        });
        return;
      });
      Vue.prototype.$bkMessage({
        message: window.i18n.t('复制成功'),
        theme: 'success'
      });
    }

    const sendingConfigurationForm = reactive({
      model: {
        a: '',
        b: '',
        c: '',
        d: '',
        e: '',
        f: '',
        g: true,
        h: '2',
        j: dayjs(new Date()).format('HH:mm:ss'),
        k: [1],
        l: [1],
        m: '',
        frequency: 5,
        time: '1',
        timerange: []
      },
      rules: {}
    });

    // 人员选择器相关
    // const users = ref([]);
    // const bkUrl = computed(() => {
    //   return `${window.site_url}rest/v2/commons/user/list_users/`;
    // });

    function setFormData() {
      Object.assign(formData, deepClone(props.detailInfo));
      // 时间范围
      // eslint-disable-next-line @typescript-eslint/naming-convention
      const { data_range } = formData.frequency;
      dataRange.value = data_range ? ((data_range.number + data_range.time_level) as string) : 'none';
      // 敏感度
      // TODO: 为什么要这么写？
      nextTick(() => {
        pattenLevelSlider.value = PatternLevelEnum[formData.scenario_config.pattern_level] || 0;
      });
      // 处理 订阅人 的数据
      subscriberInput.user = formData.channels[0].subscribers.map(item => item.id);
      subscriberInput.email = formData.channels[1].subscribers
        .map(item => {
          return item.id;
        })
        .toString();
      subscriberInput.wxbot = formData.channels[2].subscribers
        .map(item => {
          return item.id;
        })
        .toString();
      // 处理 发送频率 的数据
      switch (formData.frequency.type) {
        case 5:
          frequency.hour = formData.frequency.hour;
          break;
        case 4:
          frequency.run_time = formData.frequency.run_time;
          isIncludeWeekend.value = INCLUDES_WEEKEND.every(item => formData.frequency.week_list.includes(item));
          break;
        case 3:
          frequency.week_list = formData.frequency.week_list;
          frequency.run_time = formData.frequency.run_time;
          break;
        case 2:
          frequency.day_list = formData.frequency.day_list;
          frequency.run_time = formData.frequency.run_time;
          break;
        case 1:
          frequency.only_once_run_time = formData.frequency.run_time;
          break;

        default:
          break;
      }
    }

    const allRecerverData = ref([]);
    const defaultGroupList = ref([]);

    function getReceiverGroup() {
      getReceiver()
        .then(data => {
          allRecerverData.value = data;
          const groupData = data.find(item => item.id === 'group');
          groupData.type = 'group';
          groupData.children.map(item => (item.username = item.id));
          defaultGroupList.value.push(groupData);
          console.log(data);
          console.log(groupData);
          // 群提醒人 需要有一个固定选项。
          // const mentionList = deepClone(groupData);
          // mentionList.children.unshift(mentListDefaultItem);
          // this.mentionGroupList.push(mentionList);
        })
        .finally(() => {});
    }

    const isGenerateAttach = ref(1);

    onMounted(() => {
      if (props.mode === 'quick') setFormData();
      getReceiverGroup();
    });

    // defineExpose({
    //   validateAllForms
    // });

    return {
      formData,
      formDataRules,
      pattenLevelSlider,
      handleSliderChange,
      dataRange,
      subscriberInput,
      frequency,
      collectFrequency,
      subscribeFor,
      customSliderContent,
      weekList,
      hourOption,
      indexSetIDList,
      YOYList,
      isGenerateAttach,
      defaultGroupList,

      refOfContentForm,
      refOfEmailSubscription,
      refOfSendingConfigurationForm,
      validateAllForms,

      isShowAdvancedOption,
      isShowYOY,
      variableTable,
      handleCopy,
      sendingConfigurationForm,
      timeRangeOption,
      handleTimeRangeChange,
      isIncludeWeekend
    };
  },
  render() {
    return (
      <div class='create-subscription-form-container'>
        <div class='card-container'>
          <div class='title'>{window.i18n.t('订阅内容')}</div>
          <bk-form
            ref='refOfContentForm'
            {...{
              props: {
                model: this.formData,
                rules: this.formDataRules
              }
            }}
            label-width={200}
          >
            {/* TODO：该项可能需要从当前 URL 获取 */}
            {this.mode === 'quick' && (
              <bk-form-item label={window.i18n.t('订阅场景')}>{Scenario[this.formData.scenario]}</bk-form-item>
            )}
            {/* TODO：这是 观测对象 场景用的 */}
            {/* {this.mode === 'quick' && <bk-form-item label={window.i18n.t('观测类型')}>{'观测类型'}</bk-form-item>} */}
            {/* TODO：该项可能需要从当前 URL 获取 */}
            {/* {this.mode === 'quick' && <bk-form-item label={window.i18n.t('观测对象')}>{'观测对象'}</bk-form-item>} */}

            {this.mode === 'normal' && (
              <bk-form-item
                label={window.i18n.t('订阅场景')}
                property='scenario'
                required
              >
                <bk-radio-group v-model={this.formData.scenario}>
                  <bk-radio-button
                    value='clustering'
                    style='width: 120px;'
                  >
                    {window.i18n.t('日志聚类')}
                  </bk-radio-button>
                  {/* <bk-radio-button
                    value='dashboard'
                    style='width: 120px;'
                  >
                    {window.i18n.t('仪表盘')}
                  </bk-radio-button>
                  <bk-radio-button
                    value='scene'
                    style='width: 120px;'
                  >
                    {window.i18n.t('观测场景')}
                  </bk-radio-button> */}
                </bk-radio-group>
                {/* TODO: 跳到那里？ */}
                <bk-button
                  theme='primary'
                  text
                  style='margin-left: 24px;'
                >
                  {window.i18n.t('跳转至场景查看')}
                  <i class='icon-monitor icon-mc-link'></i>
                </bk-button>
              </bk-form-item>
            )}

            {this.mode === 'normal' && (
              <bk-form-item
                label={window.i18n.t('索引集')}
                property='scenario_config.index_set_id'
                required
              >
                <bk-select
                  v-model={this.formData.scenario_config.index_set_id}
                  style='width: 465px;'
                >
                  {this.indexSetIDList.map(item => {
                    return (
                      <bk-option
                        id={item.id}
                        name={item.name}
                      ></bk-option>
                    );
                  })}
                </bk-select>
                <div style='margin-top: 8px;width: 800px;'>
                  <bk-alert type='warning'>
                    <div slot='title'>
                      <i18n path='当前已存在相同索引集的订阅 {0} ，请确认是否要创建新订阅或是直接修改已有订阅内容？'>
                        <span style={{ color: '#3A84FF' }}>XXXX日志聚类</span>
                      </i18n>
                    </div>
                  </bk-alert>
                </div>
              </bk-form-item>
            )}

            {this.mode === 'normal' && (
              <bk-form-item
                label={window.i18n.t('时间范围')}
                required
              >
                <bk-select
                  v-model={this.dataRange}
                  clearable={false}
                  style='width: 465px;'
                >
                  {this.timeRangeOption.map(item => {
                    return (
                      <bk-option
                        id={item.id}
                        name={item.name}
                      ></bk-option>
                    );
                  })}
                </bk-select>
              </bk-form-item>
            )}

            <div>
              <bk-button
                text
                theme='primary'
                onClick={() => (this.isShowAdvancedOption = !this.isShowAdvancedOption)}
                style={{ marginLeft: '120px', marginBottom: '10px', marginTop: '20px' }}
              >
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  {this.mode === 'normal' && window.i18n.t('高级设置')}
                  {this.mode === 'quick' && window.i18n.t('内容配置')}
                  <i
                    class={['icon-monitor', this.isShowAdvancedOption ? 'icon-double-down' : 'icon-double-up']}
                    style={{ fontSize: '26px' }}
                  ></i>
                </div>
              </bk-button>
            </div>

            {/* 高级设置 */}
            {this.isShowAdvancedOption && (
              <div>
                {this.mode === 'quick' && (
                  <div>
                    {/* <bk-form-item
                      label={window.i18n.t('展示方式')}
                      property='i'
                      required
                    >
                      <bk-radio-group v-model={this.subscriptionContentForm.model.i}>
                        <bk-radio label='1'>{window.i18n.t('视图')}</bk-radio>
                        <bk-radio label='2'>{window.i18n.t('列表')}</bk-radio>
                      </bk-radio-group>
                    </bk-form-item> */}

                    {/* 这是观测场景的 */}
                    {/* <bk-form-item
                      label={window.i18n.t('数据范围')}
                      property='j'
                      required
                    >
                      <bk-select
                        v-model={this.subscriptionContentForm.model.j}
                        style='width: 465px;'
                      >
                        <bk-option
                          id='1'
                          name='label'
                        ></bk-option>
                      </bk-select>
                    </bk-form-item> */}

                    <bk-form-item
                      label={window.i18n.t('时间范围')}
                      required
                      style={{ marginTop: '20px' }}
                    >
                      <bk-select
                        v-model={this.dataRange}
                        clearable={false}
                        style='width: 465px;'
                      >
                        {this.timeRangeOption.map(item => {
                          return (
                            <bk-option
                              id={item.id}
                              name={item.name}
                            ></bk-option>
                          );
                        })}
                      </bk-select>
                    </bk-form-item>

                    {/* 这是观测场景的 */}
                    {/* <bk-form-item
                      label={window.i18n.t('排列方式')}
                      property='k'
                      required
                    >
                      <bk-radio-group v-model={this.subscriptionContentForm.model.k}>
                        <bk-radio label='1'>{window.i18n.t('一列')}</bk-radio>
                        <bk-radio label='2'>{window.i18n.t('两列')}</bk-radio>
                      </bk-radio-group>
                    </bk-form-item> */}
                  </div>
                )}

                {/* 暂不参与配置 */}
                {/* <bk-form-item
                  label={window.i18n.t('展示范围')}
                  property='d'
                  required
                  style={{ marginTop: '20px' }}
                >
                  <bk-radio-group v-model={this.subscriptionContentForm.model.d}>
                    <bk-radio label='1'>{window.i18n.t('展示全部')}</bk-radio>
                    <bk-radio label='2'>{window.i18n.t('仅展示新增')}</bk-radio>
                  </bk-radio-group>
                </bk-form-item> */}

                <bk-form-item
                  label={window.i18n.t('敏感度')}
                  property='scenario_config.pattern_level'
                  required
                  style={{ marginTop: '20px' }}
                >
                  <div class='slider-container'>
                    <span>{window.i18n.t('少')}</span>
                    <bk-slider
                      class='slider'
                      v-model={this.pattenLevelSlider}
                      step={25}
                      custom-content={this.customSliderContent}
                      onChange={this.handleSliderChange}
                    ></bk-slider>
                    <span>{window.i18n.t('多')}</span>
                  </div>
                </bk-form-item>

                <bk-form-item
                  label={window.i18n.t('最大展示数量')}
                  property='scenario_config__log_display_count'
                  required
                  error-display-type='normal'
                  // rules={[
                  //   {
                  //     required: true,
                  //     message: window.i18n.t('必填项'),
                  //     trigger: ['blur', 'change']
                  //   },
                  //   {
                  //     validator: () => {
                  //       return Number(this.formData.scenario_config.log_display_count) >= 0;
                  //     },
                  //     message: window.i18n.t('必需为正整数'),
                  //     trigger: ['blur', 'change']
                  //   }
                  // ]}
                >
                  <bk-input
                    v-model={this.formData.scenario_config.log_display_count}
                    type='number'
                    style={{ width: '160px' }}
                    onChange={() => {
                      this.formData.scenario_config__log_display_count =
                        this.formData.scenario_config.log_display_count;
                    }}
                  >
                    <div
                      class='group-text'
                      slot='append'
                    >
                      {window.i18n.t('条')}
                    </div>
                  </bk-input>
                </bk-form-item>

                <bk-form-item
                  label={window.i18n.t('展示同比')}
                  property='scenario_config.year_on_year_hour'
                  required
                >
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <bk-switcher
                      v-model={this.isShowYOY}
                      theme='primary'
                      onChange={() => {
                        if (!this.isShowYOY) this.formData.scenario_config.year_on_year_hour = 0;
                      }}
                    ></bk-switcher>
                    <bk-select
                      v-model={this.formData.scenario_config.year_on_year_hour}
                      disabled={!this.isShowYOY}
                      clearable={false}
                      style='width: 120px;margin-left: 24px;'
                    >
                      {this.YOYList.map(item => {
                        return (
                          <bk-option
                            id={item.id}
                            name={item.name}
                          ></bk-option>
                        );
                      })}
                    </bk-select>
                  </div>
                </bk-form-item>

                <bk-form-item
                  label={window.i18n.t('生成附件')}
                  property='scenario_config.generate_attachment'
                  required
                >
                  <bk-radio-group
                    v-model={this.isGenerateAttach}
                    onChange={() => {
                      this.formData.scenario_config.generate_attachment = !!this.isGenerateAttach;
                    }}
                  >
                    <bk-radio label={1}>{window.i18n.t('是')}</bk-radio>
                    <bk-radio label={0}>{window.i18n.t('否')}</bk-radio>
                  </bk-radio-group>
                </bk-form-item>
              </div>
            )}
          </bk-form>
        </div>

        {this.mode === 'normal' && (
          <div class='card-container'>
            <div class='title'>{window.i18n.t('邮件配置')}</div>

            <bk-form
              ref='refOfEmailSubscription'
              {...{
                props: {
                  model: this.formData
                }
              }}
              label-width={200}
            >
              <bk-form-item
                label={window.i18n.t('邮件标题')}
                property='content_config.title'
                required
                error-display-type='normal'
                rules={[
                  {
                    required: true,
                    message: window.i18n.t('必填项'),
                    trigger: ['blur', 'change']
                  }
                ]}
              >
                <bk-input
                  v-model={this.formData.content_config.title}
                  placeholder={window.i18n.t('请输入')}
                  style={{
                    width: '465px'
                  }}
                ></bk-input>

                <bk-popover
                  trigger='click'
                  placement='bottom-start'
                  theme='light'
                  width='420px'
                >
                  <bk-button
                    text
                    theme='primary'
                    style={{ marginLeft: '16px' }}
                  >
                    <i
                      class='icon-monitor icon-mc-detail'
                      style={{ marginRight: '7px' }}
                    ></i>
                    {window.i18n.t('变量列表')}
                  </bk-button>

                  <div slot='content'>
                    <bk-table
                      data={this.variableTable.data}
                      stripe
                    >
                      <bk-table-column
                        label={window.i18n.t('变量名')}
                        prop='variable'
                        scopedSlots={{
                          default: ({ row }) => {
                            return (
                              <div>
                                {row.variable}
                                <i
                                  class='icon-monitor icon-mc-copy'
                                  style={{ fontSize: '16px', marginLeft: '5px', color: '#3A84FF', cursor: 'pointer' }}
                                  onClick={() => {
                                    this.handleCopy(row.variable);
                                  }}
                                ></i>
                              </div>
                            );
                          }
                        }}
                      ></bk-table-column>
                      <bk-table-column
                        label={window.i18n.t('变量说明')}
                        prop='description'
                      ></bk-table-column>
                      <bk-table-column
                        label={window.i18n.t('示例')}
                        prop='example'
                      ></bk-table-column>
                    </bk-table>
                  </div>
                </bk-popover>
              </bk-form-item>

              <bk-form-item
                label={window.i18n.t('附带链接')}
                property='content_config.is_link_enabled'
                required
              >
                <bk-radio-group v-model={this.formData.content_config.is_link_enabled}>
                  <bk-radio label='1'>{window.i18n.t('是')}</bk-radio>
                  <bk-radio label='2'>{window.i18n.t('否')}</bk-radio>
                </bk-radio-group>
              </bk-form-item>
            </bk-form>
          </div>
        )}

        <div class='card-container'>
          <div class='title'>{window.i18n.t('发送配置')}</div>

          <bk-form
            ref='refOfSendingConfigurationForm'
            {...{
              props: {
                model: this.formData,
                rules: this.formDataRules
              }
            }}
            label-width={200}
          >
            {this.mode === 'quick' && (
              <bk-form-item
                label={window.i18n.t('邮件标题')}
                property='content_config__title'
                required
                error-display-type='normal'
                // rules={[
                //   {
                //     required: true,
                //     message: window.i18n.t('必填项'),
                //     trigger: ['blur', 'change']
                //   }
                // ]}
              >
                <div style={{ display: 'flex' }}>
                  <bk-input
                    v-model={this.formData.content_config.title}
                    placeholder={window.i18n.t('请输入')}
                    style={{
                      width: '465px'
                    }}
                    onChange={() => {
                      this.formData.content_config__title = this.formData.content_config.title;
                    }}
                  ></bk-input>

                  <bk-popover
                    trigger='click'
                    placement='bottom-start'
                    theme='light'
                    width='420px'
                  >
                    <bk-button
                      text
                      theme='primary'
                      style={{ marginLeft: '16px' }}
                    >
                      <i
                        class='icon-monitor icon-mc-detail'
                        style={{ marginRight: '7px' }}
                      ></i>
                      {window.i18n.t('变量列表')}
                    </bk-button>

                    <div slot='content'>
                      <bk-table
                        data={this.variableTable.data}
                        stripe
                      >
                        <bk-table-column
                          label={window.i18n.t('变量名')}
                          prop='variable'
                          scopedSlots={{
                            default: ({ row }) => {
                              return (
                                <div>
                                  {row.variable}
                                  <i
                                    class='icon-monitor icon-mc-copy'
                                    style={{ fontSize: '16px', marginLeft: '5px', color: '#3A84FF', cursor: 'pointer' }}
                                    onClick={() => {
                                      this.handleCopy(row.variable);
                                    }}
                                  ></i>
                                </div>
                              );
                            }
                          }}
                        ></bk-table-column>
                        <bk-table-column
                          label={window.i18n.t('变量说明')}
                          prop='description'
                        ></bk-table-column>
                        <bk-table-column
                          label={window.i18n.t('示例')}
                          prop='example'
                        ></bk-table-column>
                      </bk-table>
                    </div>
                  </bk-popover>
                </div>

                <bk-checkbox v-model={this.sendingConfigurationForm.model.g}>{window.i18n.t('附带链接')}</bk-checkbox>
              </bk-form-item>
            )}

            {this.mode === 'normal' && (
              <bk-form-item
                label={window.i18n.t('订阅名称')}
                property='name'
                required
              >
                <bk-input
                  v-model={this.formData.name}
                  style={{ width: '465px' }}
                ></bk-input>
              </bk-form-item>
            )}

            {/* 需要自定义校验规则 */}
            <bk-form-item
              label={window.i18n.t('订阅人')}
              property='channels'
              required
              error-display-type='normal'
            >
              {/* 先保留，不知道用不用得上 */}
              {this.mode === 'quick' && (
                <div>
                  <bk-radio-group
                    v-model={this.formData.subscripber_type}
                    style={{ display: 'inline' }}
                  >
                    <bk-radio-button value='self'>{window.i18n.t('仅自己')}</bk-radio-button>
                    <bk-radio-button value='others'>{window.i18n.t('给他人')}</bk-radio-button>
                  </bk-radio-group>
                  <span style={{ marginLeft: '10px' }}>
                    <i
                      class='icon-monitor icon-hint'
                      style={{ marginRight: '10px', color: '#EA3636', fontSize: '14px' }}
                    ></i>
                    {window.i18n.t('给他人订阅需要经过管理员审批')}
                  </span>
                </div>
              )}

              {this.formData.subscripber_type === 'others' && (
                <div>
                  <bk-checkbox v-model={this.formData.channels[0].is_enabled}>{window.i18n.t('内部邮件')}</bk-checkbox>
                  <br />
                  <div>
                    <MemberSelector
                      v-model={this.subscriberInput.user}
                      // group-list={this.defaultGroupList}
                      // on-select-user={v => {
                      //   console.log(v);
                      // }}
                      style={{ width: '465px' }}
                    ></MemberSelector>
                  </div>

                  <div style={{ marginTop: '10px' }}>
                    <bk-checkbox
                      v-model={this.formData.channels[1].is_enabled}
                      style={{ marginTop: '10px' }}
                    >
                      {window.i18n.t('外部邮件')}
                    </bk-checkbox>
                  </div>
                  <bk-popover
                    trigger='click'
                    placement='right'
                    theme='light'
                    content={window.i18n.t('多个邮箱使用逗号隔开')}
                  >
                    <bk-input
                      v-model={this.subscriberInput.email}
                      disabled={!this.formData.channels[1].is_enabled}
                      style={{ width: '465px' }}
                    >
                      <template slot='prepend'>
                        <div class='group-text'>{window.i18n.t('邮件列表')}</div>
                      </template>
                    </bk-input>
                  </bk-popover>
                  {/* 后期补上 */}
                  <bk-input
                    v-model={this.sendingConfigurationForm.model.d}
                    disabled={!this.formData.channels[1].is_enabled}
                    placeholder={window.i18n.t('请遵守公司规范，切勿泄露敏感信息，后果自负！')}
                    style={{ width: '465px', marginTop: '10px' }}
                  >
                    <template slot='prepend'>
                      <div class='group-text'>{window.i18n.t('提示文案')}</div>
                    </template>
                  </bk-input>

                  <div style={{ marginTop: '10px' }}>
                    <bk-checkbox
                      v-model={this.formData.channels[2].is_enabled}
                      style={{ marginTop: '10px' }}
                    >
                      {window.i18n.t('企业微信群')}
                    </bk-checkbox>
                  </div>
                  <bk-popover
                    trigger='click'
                    placement='bottom-start'
                    theme='light'
                  >
                    <bk-input
                      v-model={this.subscriberInput.wxbot}
                      disabled={!this.formData.channels[2].is_enabled}
                      style={{ width: '465px' }}
                    >
                      <template slot='prepend'>
                        <div class='group-text'>{window.i18n.t('群ID')}</div>
                      </template>
                    </bk-input>

                    <div slot='content'>
                      {window.i18n.t('获取会话ID方法')}: <br />
                      {window.i18n.t('1.群聊列表右键添加群机器人: BK-Monitor')}
                      <br />
                      {window.i18n.t(`2.手动 @BK-Monitor 并输入关键字'会话ID'`)}
                      <br />
                      {window.i18n.t('3.将获取到的会话ID粘贴到输入框,使用逗号分隔')}
                    </div>
                  </bk-popover>
                </div>
              )}
            </bk-form-item>

            {/* 需要自定义校验规则 */}
            <bk-form-item
              label={window.i18n.t('发送频率')}
              property='frequency'
              required
              error-display-type='normal'
            >
              <bk-radio-group v-model={this.formData.frequency.type}>
                <bk-radio label={5}>{window.i18n.t('按小时')}</bk-radio>
                <bk-radio label={4}>{window.i18n.t('按天')}</bk-radio>
                <bk-radio label={3}>{window.i18n.t('按周')}</bk-radio>
                <bk-radio label={2}>{window.i18n.t('按月')}</bk-radio>
                <bk-radio label={1}>{window.i18n.t('仅一次')}</bk-radio>
              </bk-radio-group>

              {this.formData.frequency.type === 5 && (
                <bk-select
                  v-model={this.frequency.hour}
                  clearable={false}
                  style={{ width: '240px' }}
                >
                  {this.hourOption.map(item => {
                    return (
                      <bk-option
                        id={item.id}
                        name={item.name}
                      ></bk-option>
                    );
                  })}
                </bk-select>
              )}

              {[2, 3, 4].includes(this.formData.frequency.type) && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center'
                  }}
                >
                  {this.formData.frequency.type === 3 && (
                    <bk-select
                      v-model={this.frequency.week_list}
                      multiple
                      clearable={false}
                      style={{ width: '160px', marginRight: '10px', height: '32px' }}
                    >
                      {this.weekList.map(item => {
                        return (
                          <bk-option
                            id={item.id}
                            name={item.name}
                          ></bk-option>
                        );
                      })}
                    </bk-select>
                  )}
                  {this.formData.frequency.type === 2 && (
                    <bk-select
                      v-model={this.frequency.day_list}
                      multiple
                      clearable={false}
                      style={{ width: '160px', marginRight: '10px', height: '32px' }}
                    >
                      {Array(31)
                        .fill('')
                        .map((item, index) => {
                          return (
                            <bk-option
                              id={index + 1}
                              name={index + 1 + window.i18n.t('号')}
                            ></bk-option>
                          );
                        })}
                    </bk-select>
                  )}
                  <bk-time-picker
                    v-model={this.frequency.run_time}
                    transfer
                    placeholder={this.$t('选择时间范围')}
                    clearable={false}
                    style={{ width: '130px' }}
                  />
                  {/* 该复选值不需要提交，后续在编辑的时候需要通过 INCLUDES_WEEKEND 和 weekList 去判断即可 */}
                  {this.formData.frequency.type === 4 && (
                    <bk-checkbox
                      v-model={this.isIncludeWeekend}
                      style={{
                        marginLeft: '10px'
                      }}
                    >
                      {window.i18n.t('包含周末')}
                    </bk-checkbox>
                  )}
                </div>
              )}

              {this.formData.frequency.type === 1 && (
                <div>
                  <bk-date-picker
                    v-model={this.frequency.only_once_run_time}
                    type='datetime'
                    clearable={false}
                    style={{
                      width: '168px'
                    }}
                    // onChange={v => {
                    //   this.frequency.only_once_run_time = v;
                    // }}
                  ></bk-date-picker>
                </div>
              )}
            </bk-form-item>

            {this.mode === 'normal' && (
              <bk-form-item
                label={window.i18n.t('有效时间范围')}
                property='timerange'
                required
              >
                <bk-date-picker
                  v-model={this.sendingConfigurationForm.model.timerange}
                  type='datetimerange'
                  format={'yyyy-MM-dd HH:mm:ss'}
                  clearable
                  style='width: 465px;'
                ></bk-date-picker>
              </bk-form-item>
            )}
          </bk-form>
        </div>
      </div>
    );
  }
});
