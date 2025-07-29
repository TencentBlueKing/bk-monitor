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
import { type PropType, defineComponent, nextTick, onMounted, reactive, ref, watch } from 'vue';

import { PrimaryTable } from '@blueking/tdesign-ui';
import {
  Alert,
  Button,
  Checkbox,
  DatePicker,
  Form,
  Input,
  Message,
  Popover,
  Radio,
  Select,
  Slider,
  Switcher,
  TimePicker,
} from 'bkui-vue';
import dayjs from 'dayjs';
import { logServiceRelationBkLogIndexSet } from 'monitor-api/modules/apm_service';
import { getExistReports, getVariables } from 'monitor-api/modules/new_report';
import { copyText, deepClone, transformDataKey } from 'monitor-common/utils';
import { useI18n } from 'vue-i18n';

import MemberSelect from '../../../components/member-select/member-select';
import { Scenario } from '../mapping';
import { type Report, FrequencyType } from '../types';
import { getDefaultReportData, switchReportDataForCreate, switchReportDataForUpdate } from '../utils';
import ExistedReportAlert from './existed-report-alert';

import './create-subscription-form.scss';

/** Pattern 枚举。这里做成枚举是方便反向映射。即：通过 value 转成 key 。 */
enum PatternLevelEnum {
  '01' = 100,
  '03' = 75,
  '05' = 50,
  '07' = 25,
  '09' = 0,
}
/** 按天频率 包含周末 */
const INCLUDES_WEEKEND = [1, 2, 3, 4, 5, 6, 7];
/** 按天频率 不包含周末 */
const EXCLUDES_WEEKEND = [1, 2, 3, 4, 5];

export default defineComponent({
  name: 'CreateSubscriptionForm',
  props: {
    /**
     * 新增订阅有两种模式，不同模式的表单内容也有所不同。以及 onMounted 方法中对应初始化的执行。
        还要搭配 formData.scenario 去判断该显示什么表单内容。
     */
    mode: {
      type: String as PropType<'create' | 'edit'>,
      default: 'create',
    },
    /** 编辑 模式的时候需要用到这个，作为初始化值 */
    detailInfo: {
      type: Object as PropType<Report>,
      default: () => {
        return getDefaultReportData();
      },
    },
  },
  emits: ['SelectExistedReport'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const formData = reactive(getDefaultReportData());
    const emailRegex =
      /^(([^<>()[\]\\.,;:\s@"]+(\.[^<>()[\]\\.,;:\s@"]+)*)|.(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
    /** 表单验证规则 */
    const formDataRules = {
      frequency: [
        {
          validator: () => {
            switch (formData.frequency.type) {
              case FrequencyType.weekly:
                return frequency.week_list.length > 0;
              case FrequencyType.monthly:
                return frequency.day_list.length > 0;
              default:
                return true;
            }
          },
          message: t('必填项'),
          trigger: 'blur',
        },
      ],
      channels: [
        // 这个数组顺序不要改
        {
          validator: () => {
            const enabledList = formData.channels.filter(item => item.is_enabled);
            if (enabledList.length === 0) {
              // 提醒用户，三个输入框都没有选中，必须选中一个。
              for (const key of Object.keys(errorTips)) {
                errorTips[key].message = t('请至少选择一种订阅方式');
                errorTips[key].isShow = true;
              }
              return false;
            }
            for (const key of Object.keys(errorTips)) {
              errorTips[key].isShow = false;
            }
            const subscriberList = enabledList.filter(item => item.subscribers.length);
            let isInvalid = false;
            // 选中了，但是输入框没有添加任何订阅内容，将选中的输入框都显示提示。
            for (const item of enabledList) {
              if (!item.subscribers.length) {
                errorTips[item.channel_name].message = errorTips[item.channel_name].defaultMessage;
                errorTips[item.channel_name].isShow = true;
                isInvalid = true;
              } else {
                if (item.channel_name === 'email') {
                  // 需要对邮箱格式校验
                  for (const subscriber of item.subscribers) {
                    // 校验邮箱格式
                    const result = String(subscriber.id || '')
                      .toLowerCase()
                      .match(emailRegex);
                    if (!result) {
                      isInvalid = true;
                      errorTips[item.channel_name].isShow = true;
                      errorTips[item.channel_name].message = t('邮件格式有误');
                    }
                  }
                } else {
                  errorTips[item.channel_name].isShow = false;
                }
              }
            }
            if (isInvalid) return false;

            if (subscriberList.length === 0) return false;
            return true;
          },
          // 给个空格，
          message: ' ',
          trigger: 'blur',
        },
      ],
      timerange: [
        {
          validator: () => {
            return formData.timerange.length === 2 && !!formData.timerange[0];
          },
          message: t('生效起始时间必填'),
          trigger: 'change',
        },
        {
          validator: () => {
            const [start, end] = formData.timerange;
            // end 为空串时说明是无期限。不需要再做后续计算。
            if (!end) return true;
            const result = dayjs(start).diff(end);
            return result < 0;
          },
          message: t('生效结束时间不能小于生效起始时间'),
          trigger: 'change',
        },
      ],
    };
    /** 针对 订阅人 一项进行特殊的校验异常提醒。因为该项内容有三个输入框要分别处理。 */
    const errorTips = reactive({
      user: {
        message: '',
        defaultMessage: t('内部邮件不可为空'),
        isShow: false,
      },
      email: {
        message: '',
        defaultMessage: t('外部邮件不可为空'),
        isShow: false,
      },
      wxbot: {
        message: '',
        defaultMessage: t('企业微信群不可为空'),
        isShow: false,
      },
    });
    /** Pattern 选择器 */
    const pattenLevelSlider = ref(0);
    /** 任务有效期 相关 */
    const dataRange = ref('5minutes');
    /** 订阅人 项相关变量。这里会监听该变量变化动态修改 formData 中 channels 。 */
    const subscriberInput = reactive({
      user: [],
      email: '',
      wxbot: '',
    });
    const isIncludeWeekend = ref(true);
    /** 发送频率相关。该对象最后会把该对象数据copy到 formData 上，因为其中 run_time 的日期格式不同导致 日期组件 报异常，所以这里单独抽出整个对象。 */
    const frequency = reactive({
      type: 5,
      hour: 0.5,
      run_time: dayjs().format('HH:mm:ss'),
      only_once_run_time: dayjs().format('YYYY-MM-DD HH:mm:ss'),
      week_list: [],
      day_list: [],
    });
    const subscribeFor = ref<'others' | 'self'>('self');
    /** 发送频率 中 按小时 的小时选项。 */
    const hourOption = [0.5, 1, 2, 6, 12].map(id => {
      return { id, name: t('{0}小时', [id]) };
    });
    /** 敏感度的 间隙 值。 */
    const customSliderContent = [0, 25, 50, 75, 100].reduce((acc, cur) => {
      // label 为空串为的是不显示 tips
      acc[cur] = { label: '' };
      return acc;
    }, {});
    const daysOfWeek = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日'];
    const weekList = daysOfWeek.map((day, index) => ({ name: t(day), id: index + 1 }));
    /** 索引集 列表 */
    const indexSetIDList = ref([]);
    /** 展示同比 的选项。 */
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const YOYList = [
      { id: 0, name: t('不比对') },
      ...[1, 2, 3, 6, 12, 24].map(id => ({ id, name: t('{0}小时前', [id]) })),
    ];
    /** 时间范围选项 */
    const timeRangeOption = [
      // 20240308 该选项暂时不需要。
      // { id: 'none', name: t('按发送频率') },
      ...[5, 15, 30].map(n => ({ id: `${n}minutes`, name: t('近{n}分钟', { n }) })),
      ...[1, 3, 6, 12, 24].map(n => ({ id: `${n}hours`, name: t('近{n}小时', { n }) })),
      ...[2, 7, 30].map(n => ({ id: `${n}days`, name: t('近 {n} 天', { n }) })),
    ];
    /** 订阅内容 表单实例 */
    const refOfContentForm = ref();
    /** 邮件订阅 表单实例 */
    const refOfEmailSubscription = ref();
    /** 发送配置 表单实例 */
    const refOfSendingConfigurationForm = ref();
    const isShowAdvancedOption = ref(true);
    /** 展示同比 的 switcher */
    const isShowYOY = ref(true);
    const variableTable = reactive({
      data: [],
    });

    /** 当选择已创建过订阅的索引集时，显示该警告 */
    const isShowExistSubscriptionTips = ref(false);
    const existedReportList = ref([]);
    const customHourInput = ref('');
    const refOfFrequencyHour = ref(null);
    // 任务有效期，视图绑定用。
    const timerange = reactive({
      start: '',
      end: '',
    });
    const effectiveEndRef = ref();
    /** 当选择 发送频率 为 仅一次 要保留当前所生成或选择的时间。否则就看起来是 bug 。 */
    let isNotChooseOnlyOnce = true;
    function handleSliderChange() {
      formData.scenario_config.pattern_level = PatternLevelEnum[pattenLevelSlider.value] || '09';
    }
    function handleDataRangeExchange() {
      formData.frequency.data_range = getTimeRangeObj(dataRange.value);
    }
    /**
     * 时间范围 转成 api 所需要格式。
     */
    function getTimeRangeObj(str: string) {
      if (str === 'none') return undefined;
      let res = {
        timeLevel: 'hours',
        number: 24,
      };
      const isMatch = str.match(/(\d+)(minutes|hours|days)/);
      if (isMatch) {
        const [, date, level] = isMatch;
        res = {
          timeLevel: level,
          number: +date,
        };
      }
      return transformDataKey(res, true);
    }
    /** 当通过所有表单验证时收集一次 frequency 对象。（后端对这个格式有要求，已体现在代码中） */
    function collectFrequency() {
      // 先手动重置一遍
      Object.assign(formData.frequency, {
        hour: 0,
        run_time: '',
        week_list: [],
        day_list: [],
      });
      switch (formData.frequency.type) {
        case FrequencyType.hourly:
          Object.assign(formData.frequency, {
            hour: frequency.hour,
          });
          break;
        case FrequencyType.daily:
          Object.assign(formData.frequency, {
            run_time: frequency.run_time,
            week_list: isIncludeWeekend.value ? INCLUDES_WEEKEND : EXCLUDES_WEEKEND,
          });
          break;
        case FrequencyType.weekly:
          Object.assign(formData.frequency, {
            run_time: frequency.run_time,
            week_list: frequency.week_list,
          });
          break;
        case FrequencyType.monthly:
          Object.assign(formData.frequency, {
            run_time: frequency.run_time,
            day_list: frequency.day_list,
          });
          break;
        case FrequencyType.onlyOnce:
          Object.assign(formData.frequency, {
            run_time: frequency.only_once_run_time,
          });
          break;
        default:
          break;
      }
    }

    /** 有效时间范围切换一次就要对 formData */
    function handleTimeRangeChange(v: string[]) {
      formData.timerange = deepClone(v);
      const result = v.map(date => {
        // 结束时间可能是空串（代表 无期限），这里用 undefined 代替，即不需要提交。
        return date ? dayjs(date).unix() : undefined;
      });
      // eslint-disable-next-line @typescript-eslint/naming-convention
      const [start_time, end_time] = result;
      formData.start_time = start_time;
      formData.end_time = end_time;
    }

    function validateAllForms() {
      collectFrequency();
      return Promise.all([
        refOfContentForm.value?.validate?.(),
        refOfEmailSubscription.value?.validate?.(),
        refOfSendingConfigurationForm.value?.validate?.(),
      ])
        .then(() => {
          const clonedFormData = deepClone(formData);
          const deletedKeyFormData =
            props.mode === 'create'
              ? switchReportDataForCreate(clonedFormData)
              : switchReportDataForUpdate(clonedFormData);

          // const {
          //   timerange,
          //   ...deletedKeyFormData
          // } = clonedFormData;

          return deletedKeyFormData;
        })
        .catch(error => {
          // 表单验证失败后，聚焦到对应的元素。
          const targetFormItemEle = document.querySelector('.bk-form-item.is-error');
          if (targetFormItemEle.attributes?.['data-property']?.value === 'channels') {
            // 订阅人栏需要特殊处理，如果有选中特定类型的发送人。就要再检查一次对应的输入框
            const targetChannel = formData.channels.find(
              item =>
                item.is_enabled &&
                (item.channel_name !== 'email'
                  ? !item.subscribers.length
                  : // 检查订阅邮箱格式是否正确。
                    !item.subscribers.every(email => String(email.id).toLowerCase().match(emailRegex)) ||
                    !item.subscribers.length)
            )?.channel_name;
            // @ts-ignore
            if (targetChannel) targetFormItemEle.querySelector(`#${targetChannel}-input`)?.focus();
            else {
              // 如果订阅人未选择任何类型，应该把焦点定位在 订阅人 一栏
              // @ts-ignore
              document.querySelector('#subscriptor-item')?.focus?.();
            }
          } else {
            // 这里去匹配除 订阅人 栏之外的输入框。并使之自动聚焦
            // @ts-ignore
            targetFormItemEle.querySelector('input.bk-input--text,.bk-date-picker-editor')?.focus();
          }
          return Promise.reject(error);
        });
    }
    /**
     * @desc 拷贝操作
     * @param { * } val
     */
    function handleCopy(text) {
      copyText(`{{${text}}}`, msg => {
        Message({
          message: msg,
          theme: 'error',
        });
        return;
      });
      Message({
        message: t('复制成功'),
        theme: 'success',
      });
    }

    /**
     * 编辑模式 需要将详情数据回填到组件中。
     */
    function setFormData() {
      // 这里要保证 channels 的顺序是正确的
      const clonedDetailInfo = deepClone(props.detailInfo);
      formData.channels.map(item => {
        const target = clonedDetailInfo.channels.find(clonedItem => {
          return item.channel_name === clonedItem.channel_name;
        });
        if (target) {
          Object.assign(item, target);
        }
        return item;
      });
      // biome-ignore lint/performance/noDelete: <explanation>
      delete clonedDetailInfo.channels;
      if (clonedDetailInfo.frequency.type === FrequencyType.onlyOnce) isNotChooseOnlyOnce = false;
      Object.assign(formData, clonedDetailInfo);
      // 时间范围
      // eslint-disable-next-line @typescript-eslint/naming-convention
      const { data_range } = formData.frequency;
      dataRange.value = data_range ? ((data_range.number + data_range.time_level) as string) : 'none';
      // Pattern
      // TODO: 为什么要这么写？
      nextTick(() => {
        pattenLevelSlider.value = PatternLevelEnum[formData.scenario_config.pattern_level] || 0;
      });
      // 处理 订阅人 的数据
      subscriberInput.user = formData.channels.find(item => item.channel_name === 'user')?.subscribers || [];
      subscriberInput.email = (formData.channels.find(item => item.channel_name === 'email')?.subscribers || [])
        .map(item => {
          return item.id;
        })
        .toString();
      subscriberInput.wxbot = (formData.channels.find(item => item.channel_name === 'wxbot')?.subscribers || [])
        .map(item => {
          return item.id;
        })
        .toString();
      // 处理 发送频率 的数据
      switch (formData.frequency.type) {
        case FrequencyType.hourly:
          // 由于 hourOption 可以自定义输入添加，这里需要判断一次是否有其它未被收录的选项，如果没有则增加一个选项，以免无法显示。
          if (hourOption.every(item => Number(item.id) !== formData.frequency.hour)) {
            hourOption.push({
              id: Number(formData.frequency.hour),
              name: t('{0}小时', [Number(formData.frequency.hour)]),
            });
          }
          frequency.hour = formData.frequency.hour;
          break;
        case FrequencyType.daily:
          frequency.run_time = formData.frequency.run_time;
          isIncludeWeekend.value = INCLUDES_WEEKEND.every(item => formData.frequency.week_list.includes(item));
          break;
        case FrequencyType.weekly:
          frequency.week_list = formData.frequency.week_list;
          frequency.run_time = formData.frequency.run_time;
          break;
        case FrequencyType.monthly:
          frequency.day_list = formData.frequency.day_list;
          frequency.run_time = formData.frequency.run_time;
          break;
        case FrequencyType.onlyOnce:
          frequency.only_once_run_time = formData.frequency.run_time;
          break;

        default:
          break;
      }
      formData.timerange = [
        formData.start_time ? dayjs.unix(formData.start_time).format('YYYY-MM-DD HH:mm:ss') : null,
        // 服务端返回 null 时代表永久，前端用 空串 或 null 可以代表永久。
        formData.end_time ? dayjs.unix(formData.end_time).format('YYYY-MM-DD HH:mm:ss') : null,
      ];
      // 给 任务有效期 添加数据
      const [start, end] = formData.timerange;
      timerange.start = start;
      timerange.end = end;
      // 展示同比 的 switcher 开关。
      isShowYOY.value = Boolean(formData.scenario_config.year_on_year_hour);
    }

    /** 选择一次 索引集 就要查询一次是否重复选择 */
    function checkExistSubscriptions() {
      getExistReports({
        scenario: formData.scenario,
        index_set_id: formData.scenario_config.index_set_id,
      }).then((response: []) => {
        existedReportList.value = response;
        isShowExistSubscriptionTips.value = !!response.length;
      });
    }

    /** 根据当前的 订阅场景 跳转到相应的能创建订阅的页面。
     * 比如：日志聚类 跳转到 日志平台 => 日志聚类 => 数据指纹
     * */
    function goToTargetScene() {
      if (formData.scenario === 'clustering') {
        if (!formData.scenario_config.index_set_id) {
          Message({
            theme: 'warning',
            message: t('请选择索引集'),
          });
          return;
        }
        // URL参数补齐再跳转即可。需要: spaceUid、bizId, activeTableTab, clusterRouteParams (一个配置对象)
        // 日志平台的 URL: window.bk_log_search_url
        const query = {
          spaceUid: window.space_list.find(item => item.bk_biz_id === window.bk_biz_id).space_uid || '',
          bizId: window.bk_biz_id,
          // 固定写
          activeTableTab: 'clustering',
          clusterRouteParams: JSON.stringify({
            // 固定写
            activeNav: 'dataFingerprint',
            requestData: {
              pattern_level: formData.scenario_config.pattern_level,
              year_on_year_hour: formData.scenario_config.year_on_year_hour,
              show_new_pattern: formData.scenario_config.is_show_new_pattern,
              group_by: [],
              size: 10000,
            },
          }),
        };
        // 根据 时间范围 添加相对应的表达式，日志平台的时间选择会用得上。
        const rangeObj = getTimeRangeObj(dataRange.value);
        if (rangeObj) {
          const unit = String(rangeObj.time_level || 'minutes').at(0);
          // @ts-ignore
          query.start_time = `now-${rangeObj.number || 15}${unit}`;
          // @ts-ignore
          query.end_time = 'now';
        }
        const qs = new URLSearchParams(query as any).toString();
        window.open(`${window.bk_log_search_url}#/retrieve/${formData.scenario_config.index_set_id}?${qs}`);
      }
    }

    /** 当该组件在 订阅列表 页面使用时。即：编辑态下才会使用到，通知父组件更换当前整个表单内容 */
    function handleExistedReportNameClick(reportId: number) {
      // TODO: 类型补上
      emit('SelectExistedReport', reportId);
    }

    /** 取消按钮文本设置为永久 */
    function handleDatePickerOpen(state: boolean) {
      if (state) {
        const ele = effectiveEndRef.value.$el.querySelector('.bk-picker-confirm-action a');
        ele.innerText = t('永久');
        ele.setAttribute('class', 'confirm');
      }
    }

    watch(
      dataRange,
      () => {
        handleDataRangeExchange();
      },
      {
        immediate: true,
      }
    );
    watch(
      () => subscriberInput.user,
      () => {
        formData.channels[0].subscribers = deepClone(subscriberInput.user).map(item => {
          item.is_enabled = true;
          return item;
        });
      },
      {
        deep: true,
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
              is_enabled: true,
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
              is_enabled: true,
            };
          })
          .filter(item => item.id);
        formData.channels[2].subscribers = result;
      }
    );
    watch(
      () => formData.scenario,
      () => {
        getVariables({
          scenario: formData.scenario,
        }).then(response => {
          variableTable.data = response;
        });
      },
      { immediate: true }
    );
    watch(
      () => formData.frequency.type,
      () => {
        if (formData.frequency.type === FrequencyType.onlyOnce) {
          formData.start_time = null;
          formData.end_time = null;
          // 点击 仅一次 时刷新一次时间。
          if (isNotChooseOnlyOnce) frequency.only_once_run_time = dayjs().format('YYYY-MM-DD HH:mm:ss');
        } else {
          // 把丢掉的 start_time 和 end_time 补回去
          // eslint-disable-next-line @typescript-eslint/naming-convention
          const [start_time, end_time] = formData.timerange;
          formData.start_time = dayjs(start_time).unix();
          formData.end_time = dayjs(end_time).unix();
        }
      }
    );

    onMounted(() => {
      if (props.mode === 'edit') setFormData();
      logServiceRelationBkLogIndexSet({
        clustering_only: true,
      }).then(response => {
        indexSetIDList.value = response;
      });
    });

    return {
      t,
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
      checkExistSubscriptions,
      isShowExistSubscriptionTips,

      refOfContentForm,
      refOfEmailSubscription,
      refOfSendingConfigurationForm,
      validateAllForms,

      isShowAdvancedOption,
      isShowYOY,
      variableTable,
      handleCopy,
      timeRangeOption,
      handleTimeRangeChange,
      isIncludeWeekend,
      goToTargetScene,
      errorTips,
      existedReportList,
      handleExistedReportNameClick,
      setFormData,
      customHourInput,
      refOfFrequencyHour,
      timerange,
      handleDatePickerOpen,
      effectiveEndRef,
    };
  },
  render() {
    return (
      <div class='create-subscription-form-container'>
        <div class='card-container'>
          <div class='title'>{this.t('订阅内容')}</div>
          <Form
            ref='refOfContentForm'
            label-width='200'
            model={this.formData}
          >
            {this.mode === 'edit' && (
              <Form.FormItem label={this.t('订阅场景')}>{this.t(Scenario[this.formData.scenario])}</Form.FormItem>
            )}
            {this.mode === 'edit' && (
              <Form.FormItem
                label={this.t('索引集')}
                property='scenario_config.index_set_id'
                required
              >
                <Select
                  style='width: 465px;'
                  v-model={this.formData.scenario_config.index_set_id}
                  clearable={false}
                  filterable
                  onChange={this.checkExistSubscriptions}
                >
                  {this.indexSetIDList.map(item => {
                    return (
                      <Select.Option
                        id={item.id}
                        key={item.id}
                        name={item.name}
                      />
                    );
                  })}
                </Select>
                {this.isShowExistSubscriptionTips && (
                  <div style='margin-top: 8px;width: 100%;'>
                    <ExistedReportAlert
                      style='width: 465px;'
                      existedReportList={this.existedReportList}
                      onReportNameClick={this.handleExistedReportNameClick}
                    />
                  </div>
                )}
              </Form.FormItem>
            )}
            {/* TODO：这是 观测对象 场景用的*/}
            {/* {this.mode === 'edit' && <Form.FormItem label={this.t('观测类型')}>{'观测类型'}</Form.FormItem>} */}
            {/* TODO：该项可能需要从当前 URL 获取 */}
            {/* {this.mode === 'edit' && <Form.FormItem label={this.t('观测对象')}>{'观测对象'}</Form.FormItem>} */}

            {this.mode === 'create' && (
              <Form.FormItem
                label={this.t('订阅场景')}
                property='scenario'
                required
              >
                <Radio.Group v-model={this.formData.scenario}>
                  <Radio.Button
                    style='width: 120px;'
                    label='clustering'
                  >
                    {this.t('日志聚类')}
                  </Radio.Button>
                  {/* 以下两个暂时不做 */}
                  {/* <Radio.Button
                    label='dashboard'
                    style='width: 120px;'
                  >
                    {this.t('仪表盘')}
                  </Radio.Button>
                  <Radio.Button
                    label='scene'
                    style='width: 120px;'
                  >
                    {this.t('观测场景')}
                  </Radio.Button> */}
                </Radio.Group>
                <Button
                  style='margin-left: 24px;'
                  theme='primary'
                  text
                  onClick={this.goToTargetScene}
                >
                  {this.t('跳转至场景查看')}
                  <i class='icon-monitor icon-mc-link' />
                </Button>
              </Form.FormItem>
            )}

            {this.mode === 'create' && (
              <Form.FormItem
                label={this.t('索引集')}
                property='scenario_config.index_set_id'
                required
              >
                <Select
                  style='width: 465px;'
                  v-model={this.formData.scenario_config.index_set_id}
                  clearable={false}
                  filterable
                  onChange={this.checkExistSubscriptions}
                >
                  {this.indexSetIDList.map(item => {
                    return (
                      <Select.Option
                        id={item.id}
                        key={item.id}
                        name={item.name}
                      />
                    );
                  })}
                </Select>
                {this.isShowExistSubscriptionTips && (
                  <div style='margin-top: 8px;width: 100%;'>
                    <ExistedReportAlert
                      style='width: 465px;'
                      existedReportList={this.existedReportList}
                      onReportNameClick={this.handleExistedReportNameClick}
                    />
                  </div>
                )}
              </Form.FormItem>
            )}

            {this.mode === 'create' && (
              <Form.FormItem
                label={this.t('时间范围')}
                required
              >
                <Select
                  style='width: 465px;'
                  v-model={this.dataRange}
                  clearable={false}
                >
                  {this.timeRangeOption.map(item => {
                    return (
                      <Select.Option
                        id={item.id}
                        key={item.id}
                        name={item.name}
                      />
                    );
                  })}
                </Select>

                <div style='margin-top: 8px;width: 100%;'>
                  <Alert
                    style='width: 465px;'
                    v-slots={{
                      title: () => {
                        return this.t('当前日志查询时间范围不支持静态区间');
                      },
                    }}
                    theme='warning'
                  />
                </div>
              </Form.FormItem>
            )}

            <div>
              <Button
                style='margin-left: 144px;margin-bottom: 10px;'
                theme='primary'
                text
                onClick={() => (this.isShowAdvancedOption = !this.isShowAdvancedOption)}
              >
                {this.mode === 'create' && this.t('高级设置')}
                {this.mode === 'edit' && this.t('内容配置')}
                <i
                  style='font-size: 26px;'
                  class={['icon-monitor', this.isShowAdvancedOption ? 'icon-double-down' : 'icon-double-up']}
                />
              </Button>
            </div>

            {/* 高级设置 */}
            {this.isShowAdvancedOption && (
              <div>
                {this.mode === 'edit' && (
                  <div>
                    <Form.FormItem
                      label={this.t('时间范围')}
                      required
                    >
                      <Select
                        style='width: 465px;'
                        v-model={this.dataRange}
                        clearable={false}
                      >
                        {this.timeRangeOption.map(item => {
                          return (
                            <Select.Option
                              id={item.id}
                              key={item.id}
                              name={item.name}
                            />
                          );
                        })}
                      </Select>
                      <div style='margin-top: 8px;width: 100%;'>
                        <Alert
                          style='width: 465px;'
                          v-slots={{
                            title: () => {
                              return this.t('当前日志查询时间范围不支持静态区间');
                            },
                          }}
                          theme='warning'
                        />
                      </div>
                    </Form.FormItem>
                  </div>
                )}

                <Form.FormItem
                  label='Pattern'
                  property='scenario_config.pattern_level'
                  required
                >
                  <div class='slider-container'>
                    <span>{this.t('少')}</span>
                    <Slider
                      class='slider'
                      v-model={this.pattenLevelSlider}
                      custom-content={this.customSliderContent}
                      step={25}
                      onChange={this.handleSliderChange}
                    />
                    <span>{this.t('多')}</span>
                  </div>
                </Form.FormItem>

                <Form.FormItem
                  label={this.t('最大展示数量')}
                  property='scenario_config.log_display_count'
                  required
                >
                  <Input
                    style='width: 160px;'
                    v-model={this.formData.scenario_config.log_display_count}
                    max={500}
                    min={0}
                    suffix={this.t('条')}
                    type='number'
                  />
                </Form.FormItem>

                <Form.FormItem
                  label={this.t('展示同比')}
                  property='scenario_config.year_on_year_hour'
                  required
                >
                  <div style='display: flex;align-items: center;'>
                    <Switcher
                      v-model={this.isShowYOY}
                      theme='primary'
                      onChange={() => {
                        this.formData.scenario_config.year_on_year_hour = this.isShowYOY ? 1 : 0;
                      }}
                    />
                    <Select
                      style='width: 120px;margin-left: 24px;'
                      v-model={this.formData.scenario_config.year_on_year_hour}
                      clearable={false}
                      disabled={!this.isShowYOY}
                    >
                      {this.YOYList.map(item => {
                        return (
                          <Select.Option
                            id={item.id}
                            key={item.id}
                            v-show={this.isShowYOY && item.id !== 0}
                            name={item.name}
                          />
                        );
                      })}
                    </Select>
                  </div>
                </Form.FormItem>

                <Form.FormItem
                  label={this.t('生成附件')}
                  property='scenario_config.generate_attachment'
                  required
                >
                  <Radio.Group v-model={this.formData.scenario_config.generate_attachment}>
                    <Radio label={true}>{this.t('是')}</Radio>
                    <Radio label={false}>{this.t('否')}</Radio>
                  </Radio.Group>
                </Form.FormItem>

                <Form.FormItem
                  label={this.t('只展示新类')}
                  property='scenario_config.is_show_new_pattern'
                  required
                >
                  <Radio.Group v-model={this.formData.scenario_config.is_show_new_pattern}>
                    <Radio label={true}>{this.t('是')}</Radio>
                    <Radio label={false}>{this.t('否')}</Radio>
                  </Radio.Group>
                </Form.FormItem>
              </div>
            )}
          </Form>
        </div>

        <div class='card-container'>
          <div class='title'>{this.t('邮件配置')}</div>

          <Form
            ref='refOfEmailSubscription'
            label-width='200'
            model={this.formData}
          >
            <Form.FormItem
              label={this.t('邮件标题')}
              property='content_config.title'
              required
            >
              <Input
                style='width: 465px;'
                v-model={this.formData.content_config.title}
                placeholder={this.t('请输入')}
              />

              <Popover
                width='420px'
                v-slots={{
                  content: () => {
                    return (
                      <div>
                        <PrimaryTable
                          columns={[
                            {
                              width: '140px',
                              title: `${this.t('订阅名称')}`,
                              ellipsis: {
                                popperOptions: {
                                  strategy: 'fixed',
                                },
                              },
                              cell: (_, { row: data }) => {
                                return (
                                  <div style='display: flex;align-items: center;'>
                                    <span style='width: calc(100% - 20px);word-break: break-all;white-space: normal;line-height: 14px;'>
                                      {data.name}
                                    </span>
                                    <i
                                      style='font-size: 16px;margin-left: 5px;color: #3A84FF;cursor: pointer;'
                                      class='icon-monitor icon-mc-copy'
                                      onClick={() => {
                                        this.handleCopy(data.name);
                                      }}
                                    />
                                  </div>
                                );
                              },
                            },
                            {
                              width: '80px',
                              ellipsis: {
                                popperOptions: {
                                  strategy: 'fixed',
                                },
                              },
                              title: `${this.t('变量说明')}`,
                              colKey: 'description',
                            },
                            {
                              width: '160px',
                              ellipsis: {
                                popperOptions: {
                                  strategy: 'fixed',
                                },
                              },
                              title: `${this.t('示例')}`,
                              colKey: 'example',
                            },
                          ]}
                          data={this.variableTable.data}
                          maxHeight={400}
                          rowKey='id'
                          stripe
                        />
                      </div>
                    );
                  },
                }}
                componentEventDelay={300}
                placement='bottom-start'
                popoverDelay={0}
                theme='light'
                trigger='click'
              >
                <Button
                  style='margin-left: 16px'
                  theme='primary'
                  text
                >
                  <i
                    style='margin-right: 7px;'
                    class='icon-monitor icon-mc-detail'
                  />
                  {this.t('变量列表')}
                </Button>
              </Popover>
            </Form.FormItem>

            <Form.FormItem
              label={this.t('附带链接')}
              property='content_config.is_link_enabled'
              required
            >
              <Radio.Group v-model={this.formData.content_config.is_link_enabled}>
                <Radio label={true}>{this.t('是')}</Radio>
                <Radio label={false}>{this.t('否')}</Radio>
              </Radio.Group>
            </Form.FormItem>
          </Form>
        </div>

        <div class='card-container'>
          <div class='title'>{this.t('发送配置')}</div>

          <Form
            ref='refOfSendingConfigurationForm'
            label-width='200'
            model={this.formData}
            rules={this.formDataRules}
          >
            <Form.FormItem
              label={this.t('订阅名称')}
              property='name'
              required
            >
              <Input
                style='width: 465px;'
                v-model={this.formData.name}
              />
            </Form.FormItem>

            {/* 需要自定义校验规则 */}
            <Form.FormItem
              id='subscriptor-item'
              data-property='channels'
              label={this.t('订阅人')}
              property='channels'
              tabindex='1'
              required
            >
              {this.subscribeFor === 'self' && (
                <div>
                  <Checkbox v-model={this.formData.channels[0].is_enabled}>{this.t('内部邮件')}</Checkbox>
                  <br />
                  {/* 该自定义属性是用来避免正确的输入框显示警告颜色 */}
                  <div data-is-show-error-msg={this.errorTips.user.isShow}>
                    <MemberSelect
                      id='user-input'
                      style='width: 465px;'
                      v-model={this.subscriberInput.user}
                      tabindex='1'
                      onChange={() => {
                        nextTick(() => {
                          this.formDataRules.channels[0].validator();
                        });
                      }}
                    />
                    {this.errorTips.user.isShow && <div class='bk-form-error'>{this.errorTips.user.message}</div>}
                  </div>

                  <div style='margin-top: 10px;'>
                    <Checkbox
                      style='margin-top: 10px;'
                      v-model={this.formData.channels[1].is_enabled}
                    >
                      {this.t('外部邮件')}
                    </Checkbox>
                  </div>
                  <div data-is-show-error-msg={this.errorTips.email.isShow}>
                    <Popover
                      content={this.t('多个邮箱使用逗号隔开')}
                      placement='right'
                      theme='light'
                      trigger='click'
                    >
                      <Input
                        id='email-input'
                        style='width: 465px;'
                        v-model={this.subscriberInput.email}
                        data-is-show-error-msg={this.errorTips.email.isShow}
                        disabled={!this.formData.channels[1].is_enabled}
                        prefix={this.t('邮件列表')}
                      />
                    </Popover>
                  </div>
                  <div data-is-show-error-msg='false'>
                    <Input
                      style='width: 465px;margin-top: 10px;'
                      v-model={this.formData.channels[1].send_text}
                      disabled={!this.formData.channels[1].is_enabled}
                      placeholder={this.t('请遵守公司规范，切勿泄露敏感信息，后果自负！')}
                      prefix={this.t('提示文案')}
                    />
                  </div>
                  {this.errorTips.email.isShow && <div class='bk-form-error'>{this.errorTips.email.message}</div>}

                  <div style='margin-top: 10px;'>
                    <Checkbox
                      style='margin-top: 10px;'
                      v-model={this.formData.channels[2].is_enabled}
                    >
                      {this.t('企业微信群')}
                    </Checkbox>
                  </div>
                  <div data-is-show-error-msg={this.errorTips.wxbot.isShow}>
                    <Popover
                      v-slots={{
                        content: () => {
                          return (
                            <div>
                              {this.t('获取会话ID方法')}: <br />
                              {this.t('1.群聊列表右键添加群机器人: 蓝鲸监控上云')}
                              <br />
                              {this.t(`2.手动 @蓝鲸监控上云 并输入关键字'会话ID'`)}
                              <br />
                              {this.t('3.将获取到的会话ID粘贴到输入框,使用逗号分隔')}
                            </div>
                          );
                        },
                      }}
                      placement='right'
                      theme='light'
                      trigger='click'
                    >
                      <Input
                        id='wxbot-input'
                        style='width: 465px;'
                        v-model={this.subscriberInput.wxbot}
                        disabled={!this.formData.channels[2].is_enabled}
                        prefix={this.t('群ID')}
                      />
                    </Popover>
                  </div>
                  {this.errorTips.wxbot.isShow && <div class='bk-form-error'>{this.errorTips.wxbot.message}</div>}
                </div>
              )}
            </Form.FormItem>

            {/* 需要自定义校验规则 */}
            <Form.FormItem
              label={this.t('发送频率')}
              property='frequency'
              required
            >
              <Radio.Group v-model={this.formData.frequency.type}>
                <Radio label={FrequencyType.hourly}>{this.t('按小时')}</Radio>
                <Radio label={FrequencyType.daily}>{this.t('按天')}</Radio>
                <Radio label={FrequencyType.weekly}>{this.t('按周')}</Radio>
                <Radio label={FrequencyType.monthly}>{this.t('按月')}</Radio>
                <Radio label={FrequencyType.onlyOnce}>{this.t('仅一次')}</Radio>
              </Radio.Group>

              {this.formData.frequency.type === FrequencyType.hourly && (
                <Select
                  ref='refOfFrequencyHour'
                  style='width: 240px;'
                  v-model={this.frequency.hour}
                  v-slots={{
                    extension: () => {
                      return (
                        <div style='width: 100%;padding: 10px 16px;'>
                          <Input
                            v-model={this.customHourInput}
                            max={24}
                            min={1}
                            placeholder={this.t('输入自定义小时，按 Enter 确认')}
                            size='small'
                            type='number'
                            onEnter={() => {
                              // 添加自定义 发送频率 ，如果输入有重复要直接选中。
                              let inputNumber = Number(this.customHourInput);
                              if (!inputNumber) {
                                return Message({
                                  theme: 'warning',
                                  message: this.t('请输入有效数值'),
                                });
                              }
                              const minNum = 0.5;
                              const maxNum = 24;
                              if (inputNumber > maxNum) {
                                inputNumber = maxNum;
                                this.customHourInput = String(inputNumber);
                              }
                              if (inputNumber < minNum) {
                                inputNumber = minNum;
                                this.customHourInput = String(inputNumber);
                              }
                              const isHasDuplicatedNum = this.hourOption.find(item => item.id === inputNumber);
                              if (!isHasDuplicatedNum) {
                                this.hourOption.push({ id: inputNumber, name: this.t('{0}小时', [inputNumber]) });
                              }
                              this.frequency.hour = inputNumber;
                              this.customHourInput = '';
                              this.refOfFrequencyHour.hidePopover();
                            }}
                            // @ts-ignore 只允许输入正整数
                            oninput="value=value.replace(/^(0+)|[^\d]+/g,'')"
                          />
                        </div>
                      );
                    },
                  }}
                  clearable={false}
                >
                  {this.hourOption.map(item => {
                    return (
                      <Select.Option
                        id={item.id}
                        key={item.id}
                        name={item.name}
                      />
                    );
                  })}
                  {/* {this.hourOption.find(item => Number(item.id) !== this.frequency.hour) && (
                    <Select.Option
                      id={Number(this.frequency.hour)}
                      name={this.t('{0}小时', [Number(this.frequency.hour)])}
                    />
                  )} */}
                </Select>
              )}

              {[FrequencyType.monthly, FrequencyType.weekly, FrequencyType.daily].includes(
                this.formData.frequency.type
              ) && (
                <div style='display: flex;align-items: center;'>
                  {this.formData.frequency.type === FrequencyType.weekly && (
                    <Select
                      style='width: 160px;margin-right: 10px;height: 32px;'
                      v-model={this.frequency.week_list}
                      clearable={false}
                      multiple
                    >
                      {this.weekList.map(item => {
                        return (
                          <Select.Option
                            id={item.id}
                            key={item.id}
                            name={item.name}
                          />
                        );
                      })}
                    </Select>
                  )}
                  {this.formData.frequency.type === FrequencyType.monthly && (
                    <Select
                      style='width: 160px;margin-right: 10px;height: 32px;'
                      v-model={this.frequency.day_list}
                      clearable={false}
                      multiple
                    >
                      {Array(31)
                        .fill('')
                        .map((item, index) => {
                          return (
                            <Select.Option
                              id={index + 1}
                              key={index}
                              name={index + 1 + this.t('号')}
                            />
                          );
                        })}
                    </Select>
                  )}
                  <TimePicker
                    style='width: 130px;'
                    v-model={this.frequency.run_time}
                    clearable={false}
                    placeholder={this.t('选择时间范围')}
                    appendToBody
                  />
                  {/* 该复选值不需要提交，后续在编辑的时候需要通过 INCLUDES_WEEKEND 和 weekList 去判断即可 */}
                  {this.formData.frequency.type === FrequencyType.daily && (
                    <Checkbox
                      style='margin-left: 10px;font-size: 12px;'
                      v-model={this.isIncludeWeekend}
                    >
                      {this.t('包含周末')}
                    </Checkbox>
                  )}
                </div>
              )}

              {this.formData.frequency.type === FrequencyType.onlyOnce && (
                <div>
                  <DatePicker
                    style='width: 168px;'
                    appendToBody={true}
                    clearable={false}
                    modelValue={this.frequency.only_once_run_time}
                    type='datetime'
                    onChange={v => {
                      this.frequency.only_once_run_time = v;
                    }}
                  />
                </div>
              )}
            </Form.FormItem>

            {this.formData.frequency.type !== FrequencyType.onlyOnce && (
              <Form.FormItem
                description={this.t('有效期内，订阅任务将正常发送；超出有效期，则任务失效，停止发送。')}
                label={this.t('任务有效期')}
                property='timerange'
                required
              >
                <DatePicker
                  style='width: 220px;'
                  appendToBody={true}
                  clearable={false}
                  modelValue={this.timerange.start}
                  placeholder={`${this.t('如')}: 2019-01-30 12:12:21`}
                  type='datetime'
                  onChange={v => {
                    this.timerange.start = v;
                    this.handleTimeRangeChange([this.timerange.start, this.timerange.end]);
                  }}
                />
                <span style='padding: 0 10px;'>-</span>
                <DatePicker
                  ref='effectiveEndRef'
                  style='width: 220px;'
                  class='effective-end'
                  appendToBody={true}
                  modelValue={this.timerange.end}
                  placeholder={this.t('永久')}
                  type='datetime'
                  clearable
                  onChange={v => {
                    this.timerange.end = v;
                    this.handleTimeRangeChange([this.timerange.start, this.timerange.end]);
                  }}
                  onOpen-change={this.handleDatePickerOpen}
                />
              </Form.FormItem>
            )}
          </Form>
        </div>
      </div>
    );
  },
});
