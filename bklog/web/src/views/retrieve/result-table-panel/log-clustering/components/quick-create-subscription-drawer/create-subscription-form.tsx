import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc, ofType } from 'vue-tsx-support';
import { copyText, deepClone, transformDataKey } from '../../../../../../components/monitor-echarts/utils';
import BkUserSelector from '@blueking/user-selector';
import dayjs from 'dayjs';

import { FrequencyType, Report } from './types';

import './create-subscription-form.scss';

enum PatternLevelEnum {
  '01' = 100,
  '03' = 75,
  '05' = 50,
  '07' = 25,
  '09' = 0
}

interface IProps {
  value: boolean;
}

/** 按天频率 包含周末 */
const INCLUDES_WEEKEND = [1, 2, 3, 4, 5, 6, 7];
/** 按天频率 不包含周末 */
const EXCLUDES_WEEKEND = [1, 2, 3, 4, 5];
const Scenario = {
  clustering: window.mainComponent.$t('日志聚类'),
  dashboard: window.mainComponent.$t('仪表盘'),
  scene: window.mainComponent.$t('观测场景')
}
const hours = [0.5, 1, 2, 6, 12];
/** 发送频率 中 按小时 的小时选项。 */
const hourOption = hours.map(hour => ({
  id: hour,
  name: window.mainComponent.$t('{0}小时', [hour])
}));
/** 敏感度的 间隙 值。 */
const customSliderContent = [0, 25, 50, 75, 100].reduce((acc, value) => {
  // label 为空串为的是不显示 tips
  acc[value] = { label: '' };
  return acc;
}, {});
const daysOfWeek = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日'];
const weekList = daysOfWeek.map((day, index) => ({
  name: window.mainComponent.$t(day),
  id: index + 1
}));
/** 展示同比 的选项。 */
const YOYList = [
  { id: 0, name: window.mainComponent.$t('不比对') },
  ...[1, 2, 3, 6, 12, 24].map(hour => ({
    id: hour,
    name: window.mainComponent.$t('{0}小时前', [hour])
  }))
];
const timeOptions = [
  // 20240308 暂时不需要该选项。
  // { id: 'none', label: '按发送频率', unit: '' },
  { id: '5minutes', n: 5, unit: '分钟' },
  { id: '15minutes', n: 15, unit: '分钟' },
  { id: '30minutes', n: 30, unit: '分钟' },
  { id: '1hours', n: 1, unit: '小时' },
  { id: '3hours', n: 3, unit: '小时' },
  { id: '6hours', n: 6, unit: '小时' },
  { id: '12hours', n: 12, unit: '小时' },
  { id: '24hours', n: 24, unit: '小时' },
  { id: '2days', n: 2, unit: '天' },
  { id: '7days', n: 7, unit: '天' },
  { id: '30days', n: 30, unit: '天' },
];
/** 时间范围选项 */
const timeRangeOption = timeOptions.map(({ id, label, n, unit }) => ({
  id,
  name: label || window.mainComponent.$t(`近{n}${unit}`, { n })
}));
@Component({
  name: 'QuickCreateSubscription',
  components: {
    BkUserSelector
  }
})
class QuickCreateSubscription extends tsc<IProps> {
  /**
    日志仅有 创建 create 模式
  */
  @Prop({ type: String, default: 'edit' }) mode: string;
  /** 当前页面所对应的 索引集ID */
  @Prop({ type: [Number, String], default: 0 }) indexSetId: number | string;
  /** 当前页面所对应的 场景 类型。现在是 日志。所以固定写成 日志聚类 */
  @Prop({ type: String, default: 'clustering' }) scenario: string;

  formData: Report = {
    scenario: 'clustering',
    name: '',
    start_time: 0,
    end_time: 0,
    // 给他人/自己 订阅 。self, others 仅自己/给他人
    subscriber_type: 'self',
    scenario_config: {
      index_set_id: 0,
      // 需要从 slider 上进行转换
      pattern_level: '09',
      log_display_count: 30,
      year_on_year_hour: 1,
      generate_attachment: true,
      // 是否只展示新类
      is_show_new_pattern: false,
      // 这个同比配置也不需要前端展示，暂不开放配置入口 （不用管）
      year_on_year_change: 'all',
    },
    // 这里不可以直接对组件赋值，不然最后会带上不必要的参数。
    frequency: {
      data_range: null,
      // TODO: 补上枚举值
      type: 5,
      hour: 0.5,
      run_time: '',
      week_list: [],
      day_list: [],
    },
    content_config: {
      title: '',
      is_link_enabled: true,
    },
    channels: [
      {
        is_enabled: true,
        subscribers: [],
        channel_name: 'user',
      },
      {
        is_enabled: false,
        subscribers: [],
        send_text: '',
        channel_name: 'email',
      },
      {
        is_enabled: false,
        subscribers: [],
        channel_name: 'wxbot',
      },
    ],
    timerange: [],
    // 表单的验证的 bug ，后期再考虑删掉
    scenario_config__log_display_count: 0,
    // 同上一个道理
    content_config__title: '',
    bk_biz_id: 0,
  };

  /** 发送频率相关。该对象最后会把该对象数据copy到 formData 上，因为其中 run_time 的日期格式不同导致 日期组件 报异常，所以这里单独抽出整个对象。 */
  frequency = {
    type: 5,
    hour: 0.5,
    run_time: dayjs().format('HH:mm:ss'),
    only_once_run_time: dayjs().format('YYYY-MM-DD HH:mm:ss'),
    week_list: [],
    day_list: [],
  };

  /** Pattern 选择器 */
  pattenLevelSlider = 0;

  /** 任务有效期 相关 */
  dataRange = '5minutes';

  /** 订阅人 项相关变量。这里会监听该变量变化动态修改 formData 中 channels 。 */
  subscriberInput = {
    user: [],
    email: '',
    wxbot: ''
  }

  isIncludeWeekend = true;

  subscribeFor: 'self' | 'others' = 'self';

  /** 索引集 列表 */
  indexSetIDList = [];

  /** 订阅内容 表单实例 */
  refOfContentForm = null;
  /** 邮件订阅 表单实例 */
  refOfEmailSubscription = null;
  /** 发送配置 表单实例 */
  refOfSendingConfigurationForm = null;

  isShowAdvancedOption = false;
  /** 展示同比 的 switcher */
  isShowYOY = true;

  variableTable = {
    data: [],
  };

  /** 是否 生成附件 */
  isGenerateAttach = 1;
  /** 是否 只展示新类 */
  isShowNewPattern = 0;

  /** 针对 订阅人 一项进行特殊的校验异常提醒。因为该项内容有三个输入框要分别处理。 */
  errorTips = {
    user: {
      message: '',
      defaultMessage: window.mainComponent.$t('内部邮件不可为空'),
      isShow: false
    },
    email: {
      message: '',
      defaultMessage: window.mainComponent.$t('外部邮件不可为空'),
      isShow: false
    },
    wxbot: {
      message: '',
      defaultMessage: window.mainComponent.$t('企业微信群不可为空'),
      isShow: false
    }
  }

  /** 是否 附带链接 */
  isLinkEnabled = 1;

  /** 当前页 业务名 */
  bizName = '';

  emailRegex = /^(([^<>()[\]\\.,;:\s@"]+(\.[^<>()[\]\\.,;:\s@"]+)*)|.(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;

  customHourInput = '';

  /** 任务有效期，视图绑定用。 */
  timerange = {
    start: '',
    end: ''
  };

  /** 表单验证规则，因为这里需要大量引用 this 指向本组件，所以要使用函数去返回配置对象 */
  formDataRules() {
    return {
      frequency: [
        {
          validator: () => {
            switch (this.formData.frequency.type) {
              case FrequencyType.weekly:
                return this.frequency.week_list.length > 0;
              case FrequencyType.monthly:
                return this.frequency.day_list.length > 0;
              default:
                return true;
            }
          },
          message: this.$t('必填项'),
          trigger: 'change',
        },
      ],
      channels: [
        {
          validator: () => {
            if (this.formData.subscriber_type === 'self') return true;
            const enabledList = this.formData.channels.filter(item => item.is_enabled);
            if (enabledList.length === 0) {
              // 提醒用户，三个输入框都没有选中，必须选中一个。
              Object.keys(this.errorTips).forEach(key => {
                this.errorTips[key].message = this.$t('请至少选择一种订阅方式');
                this.errorTips[key].isShow = true;
              });
              return false;
            }
            Object.keys(this.errorTips).forEach(key => {
              this.errorTips[key].isShow = false;
            });

            if (enabledList.length === 0) return false;
            const subscriberList = enabledList.filter(item => item.subscribers.length);

            let isInvalid = false;
            // 选中了，但是输入框没有添加任何订阅内容，将选中的输入框都显示提示。
            enabledList.forEach(item => {
              if (!item.subscribers.length) {
                this.errorTips[item.channel_name].message = this.errorTips[item.channel_name].defaultMessage;
                this.errorTips[item.channel_name].isShow = true;
                isInvalid = true;
              } else {
                if (item.channel_name === 'email') {
                  // 需要对邮箱格式校验
                  item.subscribers.forEach(subscriber => {
                    const result = String(subscriber.id || '')
                      .toLowerCase()
                      .match(
                        this.emailRegex
                      );
                    if (!result) {
                      isInvalid = true;
                      this.errorTips[item.channel_name].isShow = true;
                      this.errorTips[item.channel_name].message = this.$t('邮件格式有误').toString();
                    }
                  });
                } else {
                  this.errorTips[item.channel_name].isShow = false;
                }
              }
            });
            if (isInvalid) return false;

            if (subscriberList.length === 0) return false;
            return true;
          },
          message: ' ',
          trigger: 'blur',
        },
      ],
      scenario_config__log_display_count: [
        {
          required: true,
          message: this.$t('必填项'),
          trigger: 'change',
        },
        {
          validator: () => {
            return Number(this.formData.scenario_config.log_display_count) >= 0;
          },
          message: this.$t('必需为正整数'),
          // 不要写成数组，会有 bug 。（validate 永远为 true）
          trigger: 'change',
        },
      ],
      content_config__title: [
        {
          required: true,
          message: this.$t('必填项'),
          trigger: 'change',
        },
      ],
      timerange: [
        {
          validator: () => {
            return this.formData.timerange.length === 2 && !!this.formData.timerange[0];
          },
          message: this.$t('生效起始时间必填'),
          trigger: 'change'
        },
        {
          validator: () => {
            const [start, end] = this.formData.timerange;
            // end 为空串时说明是无期限。不需要再做后续计算。
            if (!end) return true;
            const result = dayjs(start).diff(end);
            return result < 0;
          },
          message: this.$t('生效结束时间不能小于生效起始时间'),
          trigger: 'change'
        }
      ],
      name: [
        {
          required: true,
          message: this.$t('必填项'),
          trigger: 'change',
        },
      ]
    };
  }

  handleSliderChange() {
    this.formData.scenario_config.pattern_level = PatternLevelEnum[this.pattenLevelSlider] || '01';
  }

  handleDataRangeExchange() {
    this.formData.frequency.data_range = this.getTimeRangeObj(this.dataRange);
  }

  getTimeRangeObj(str: string) {
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

  /** 当通过所有表单验证时收集一次 frequency 对象。（后端对这个格式有要求，已体现在代码中） */
  collectFrequency() {
    // 先手动重置一遍
    Object.assign(this.formData.frequency, {
      hour: 0,
      run_time: '',
      week_list: [],
      day_list: []
    });
    switch (this.formData.frequency.type) {
      case FrequencyType.hourly:
        Object.assign(this.formData.frequency, {
          hour: this.frequency.hour
        });
        break;
      case FrequencyType.dayly:
        Object.assign(this.formData.frequency, {
          run_time: this.frequency.run_time,
          week_list: this.isIncludeWeekend ? INCLUDES_WEEKEND : EXCLUDES_WEEKEND
        });
        break;
      case FrequencyType.weekly:
        Object.assign(this.formData.frequency, {
          run_time: this.frequency.run_time,
          week_list: this.frequency.week_list
        });
        break;
      case FrequencyType.monthly:
        Object.assign(this.formData.frequency, {
          run_time: this.frequency.run_time,
          day_list: this.frequency.day_list
        });
        break;
      case FrequencyType.onlyOnce:
        Object.assign(this.formData.frequency, {
          run_time: dayjs(this.frequency.only_once_run_time).format('YYYY-MM-DD HH:mm:ss')
        });
        break;
      default:
        break;
    }
  }

  /** 任务有效期 调整时间格式 */
  handleTimeRangeChange(v) {
    this.formData.timerange = deepClone(v);
    const result = v.map(date => {
      // 结束时间可能是空串（代表 无期限），这里用 undefined 代替，即不需要提交。
      return date ? dayjs(date).unix() : undefined;
    });
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const [start_time, end_time] = result;
    this.formData.start_time = start_time;
    this.formData.end_time = end_time;
  }

  /** 校验所有表单，若通过则返回 formData 值 */
  validateAllForms() {
    if (!this.refOfContentForm) this.refOfContentForm = this.$refs.refOfContentForm;
    if (!this.refOfEmailSubscription) this.refOfEmailSubscription = this.$refs.refOfEmailSubscription;
    if (!this.refOfSendingConfigurationForm) this.refOfSendingConfigurationForm = this.$refs.refOfSendingConfigurationForm;
    this.collectFrequency();
    return Promise.all([
      this.refOfContentForm?.validate?.(),
      this.refOfEmailSubscription?.validate?.(),
      this.refOfSendingConfigurationForm?.validate?.()
    ]).then(() => {
      const cloneFormData: Report = deepClone(this.formData);
      // scenario_config__log_display_count content_config__title
      delete cloneFormData.scenario_config__log_display_count;
      delete cloneFormData.content_config__title;
      delete cloneFormData.timerange;
      if (cloneFormData.subscriber_type === 'self') {
        cloneFormData.channels = [
          {
            is_enabled: true,
            subscribers: [
              {
                id: this.$store.state.userMeta?.username || '',
                type: 'user',
                is_enabled: true
              }
            ],
            channel_name: 'user'
          }
        ];
      }
      // 调整 订阅名称 ，这里 订阅名称 由于没有录入的地方将是用默认方式组合。
      // cloneFormData.name = `${cloneFormData.content_config.title}-${this.$store.state.userMeta?.username || ''}`;
      cloneFormData.bk_biz_id = Number(this.$route.query.bizId || 0);
      cloneFormData.scenario_config.index_set_id = Number(this.indexSetId || 0);
      return cloneFormData;
    })
    .catch((error) => {
      // 表单验证失败后，聚焦到对应的元素。
      const property = error.field;
      // 订阅内容 表单若有某个内容验证有误将尽可能的聚焦到该元素上。
      this.refOfContentForm?.formItems?.find(item => item.property === property)?.$children?.find?.(item => item.focus)?.focus?.()
      // 邮件配置 表单若有某个内容验证有误将尽可能的聚焦到该元素上。
      this.refOfEmailSubscription?.formItems?.find(item => item.property === property)?.$children?.find?.(item => item.focus)?.focus?.()
      if (property !== 'channels') {
        this.refOfSendingConfigurationForm?.formItems?.find(item => item.property === property)?.$children?.find?.(item => item.focus)?.focus?.()
      } else {
        if (this.formData.subscriber_type === 'others') {
          const targetChannel = this.formData.channels.find(
            item =>
              item.is_enabled &&
              (item.channel_name !== 'email'
                ? !item.subscribers.length
                : // 检查订阅邮箱格式是否正确。
                  !item.subscribers.every(email => String(email.id).toLowerCase().match(this.emailRegex)) ||
                  !item.subscribers.length)
          )?.channel_name;
          if (targetChannel) this.$refs?.[`${targetChannel}-input`]?.focus?.();
          else {
            // 如果订阅人未选择任何类型，应该把焦点定位在 订阅人 一栏
            document.querySelector('#subscriptor-item')?.focus?.();
          }
        }
      }
      return Promise.reject(error);
    })
  }

  /**
     * @desc 拷贝操作
     * @param { * } val
     */
  handleCopy(text) {
    let switchedText = '';
    switch (text) {
      case 'time':
        switchedText = dayjs(new Date()).format('YYYY-MM-DD HH:mm');
        break;
      case 'index_set_name':
        switchedText = this.indexSetName;
        break;
      case 'business_name':
        switchedText = this.bizName;
        break;
      default:
        switchedText = `{{${text}}}`;
        break;
    }
    copyText(switchedText, msg => {
      this.$bkMessage({
        message: msg,
        theme: 'error'
      });
      return;
    });
    this.$bkMessage({
      message: this.$t('复制成功'),
      theme: 'success'
    });
  }

  /**
   * 给 邮件标题 和 订阅名称 添加默认变量
   * 以及从 url 中提取并赋值 展示同比 和 Pattern 。
   */
  setDefaultValue() {
    const spaceList = this.$store.state.mySpaceList;
    const bizId = this.$store.state.bkBizId;
    this.bizName = spaceList.find(item => item.bk_biz_id === bizId)?.space_name || '';
    const currentDate = dayjs(new Date()).format('YYYY-MM-DD HH:mm');
    const titleMapping = {
      clustering: this.$t('{0}-日志聚类统计报表-{1}', [this.bizName, currentDate])
    };
    const nameMapping = {
      clustering: this.$t('{0}-日志聚类统计报表-{1}', ['{{business_name}}', '{{time}}'])
    };
    const targetTitle = titleMapping[this.scenario] || '';
    const targetName = nameMapping[this.scenario] || '';
    this.formData.content_config.title = targetName;
    this.formData.content_config__title = targetName;
    this.formData.name = `${targetTitle}-${this.$store.state.userMeta?.username || ''}`

    const clusterRouteParams = JSON.parse(this.$route.query.clusterRouteParams || '{}');
    this.pattenLevelSlider = PatternLevelEnum[clusterRouteParams?.requestData?.pattern_level || '09'];
    this.handleSliderChange();
    if (clusterRouteParams?.requestData?.year_on_year_hour) {
      this.formData.scenario_config.year_on_year_hour = clusterRouteParams?.requestData?.year_on_year_hour;
    } else {
      this.isShowYOY = false;
      this.formData.scenario_config.year_on_year_hour = 0;
    }
  }

  /** 获取索引集 列表，需要取其中的 name */
  getIndexSetList() {
    this.$http.request('retrieve/getIndexSetList', {
      query: {
        space_uid: this.$route.query.spaceUid,
      }
    })
    .then(response => {
      this.indexSetIDList = response.data;
    })
  }

  /** 获取变量列表 */
  getVariablesList() {
    this.$http.request('newReport/getVariables', {
      query: {
        scenario: this.scenario
      }
    })
      .then(response => {
        this.variableTable.data = response.data;
      })
  }

  /** 取消按钮文本设置为永久 */
  handleDatePickerOpen(state: boolean) {
    if (state) {
      // @ts-ignore
      const ele = this.$refs['effectiveEndRef'].$el.querySelector('.bk-picker-confirm a:nth-child(2)');
      ele.innerText = this.$t('永久');
      ele.setAttribute('class', 'confirm');
    }
  }

  @Watch('dataRange', { immediate: true})
  watchDataRange() {
    this.handleDataRangeExchange()
  }

  @Watch('subscriberInput.email')
  watchEmail() {
    const result = this.subscriberInput.email
          .split(',')
          .map(item => {
            return {
              id: item,
              is_enabled: true
            };
          })
          .filter(item => item.id);
        this.formData.channels[1].subscribers = result;
  }

  @Watch('subscriberInput.wxbot')
  watchWxbot() {
    const result = this.subscriberInput.wxbot
          .split(',')
          .map(item => {
            return {
              id: item,
              is_enabled: true
            };
          })
          .filter(item => item.id);
        this.formData.channels[2].subscribers = result;
  }

  @Watch('formData.frequency.type')
  watchFrequencyType() {
    if (this.formData.frequency.type === FrequencyType.onlyOnce) {
      this.formData.start_time = null;
      this.formData.end_time = null;
      // 点击 仅一次 时刷新一次时间。
      this.frequency.only_once_run_time = dayjs().format('YYYY-MM-DD HH:mm:ss');
    } else {
      // 把丢掉的 start_time 和 end_time 补回去
      // eslint-disable-next-line @typescript-eslint/naming-convention
      const [start_time, end_time] = this.formData.timerange;
      this.formData.start_time = dayjs(start_time).unix();
      this.formData.end_time = dayjs(end_time).unix();
    }
  }

  get indexSetName() {
    return this.indexSetIDList.find(item => item.index_set_id === Number(this.indexSetId || 0))?.index_set_name || '';
  }

  mounted() {
    this.setDefaultValue();
    this.getIndexSetList();
    this.getVariablesList();
    this.formData.scenario = this.scenario;
  }

  render() {
    return (
      <div class='create-subscription-form-container'>
        <div class='card-container'>
          <div class='title'>{this.$t('订阅内容')}</div>
          <bk-form
            ref='refOfContentForm'
            {...{
              props: {
                model: this.formData,
                rules: this.formDataRules()
              }
            }}
            label-width={200}
          >
            {this.mode === 'create' && (
              <bk-form-item label={this.$t('订阅场景')} class='text-content'>{Scenario[this.scenario]}</bk-form-item>
            )}
            {this.mode === 'create' && <bk-form-item label={this.$t('索引集')} class='text-content'>{this.indexSetName}</bk-form-item>}

            <div>
              <bk-button
                text
                theme='primary'
                onClick={() => (this.isShowAdvancedOption = !this.isShowAdvancedOption)}
                style="margin-left: 120px; margin-bottom: 10px; margin-top: 20px;font-size: 12px;"
              >
                <div style="display: flex; align-items: center;">
                  {this.mode === 'create' && this.$t('内容配置')}
                  <i
                    class={['icon-monitor', this.isShowAdvancedOption ? 'log-icon icon-expand-small' : 'log-icon icon-collapse-small']}
                    style="font-size: 26px;"
                  ></i>
                </div>
              </bk-button>
            </div>

            {/* 高级设置 */}
            {this.isShowAdvancedOption && (
              <div>
                {this.mode === 'create' && (
                  <div>
                    <bk-form-item
                      label={this.$t('时间范围')}
                      required
                      style="margin-top: 20px;"
                    >
                      <bk-select
                        v-model={this.dataRange}
                        clearable={false}
                        style='width: 465px;'
                      >
                        {timeRangeOption.map(item => {
                          return (
                            <bk-option
                              id={item.id}
                              name={item.name}
                            ></bk-option>
                          );
                        })}
                      </bk-select>
                      <div style='margin-top: 8px;width: 100%;'>
                        <bk-alert
                          type='warning'
                          style='width: 465px;'
                          title={this.$t('当前日志查询时间范围不支持静态区间')}
                        ></bk-alert>
                      </div>
                    </bk-form-item>
                  </div>
                )}

                <bk-form-item
                  label='Pattern'
                  property='scenario_config.pattern_level'
                  required
                  style="margin-top: 20px;"
                >
                  <div class='slider-container'>
                    <span class='text-content'>{this.$t('少')}</span>
                    <bk-slider
                      class='slider'
                      v-model={this.pattenLevelSlider}
                      step={25}
                      show-tip={false}
                      custom-content={customSliderContent}
                      onChange={this.handleSliderChange}
                    ></bk-slider>
                    <span class='text-content'>{this.$t('多')}</span>
                  </div>
                </bk-form-item>

                <bk-form-item
                  label={this.$t('最大展示数量')}
                  property='scenario_config__log_display_count'
                  required
                  error-display-type='normal'
                >
                  <bk-input
                    v-model={this.formData.scenario_config.log_display_count}
                    type='number'
                    min={0}
                    max={500}
                    style="width: 160px;"
                    onChange={() => {
                      this.formData.scenario_config__log_display_count =
                        this.formData.scenario_config.log_display_count;
                    }}
                  >
                    <div
                      class='group-text'
                      slot='append'
                    >
                      {this.$t('条')}
                    </div>
                  </bk-input>
                </bk-form-item>

                <bk-form-item
                  label={this.$t('展示同比')}
                  property='scenario_config.year_on_year_hour'
                  required
                >
                  <div style="display: flex; align-items: center;">
                    <bk-switcher
                      v-model={this.isShowYOY}
                      theme='primary'
                      onChange={() => {
                        this.formData.scenario_config.year_on_year_hour = this.isShowYOY ? 1 : 0;
                      }}
                    ></bk-switcher>
                    <bk-select
                      v-model={this.formData.scenario_config.year_on_year_hour}
                      disabled={!this.isShowYOY}
                      clearable={false}
                      style='width: 120px;margin-left: 24px;'
                    >
                      {YOYList.map(item => {
                        return (
                          <bk-option
                            v-show={this.isShowYOY && item.id !== 0}
                            id={item.id}
                            name={item.name}
                          ></bk-option>
                        );
                      })}
                    </bk-select>
                  </div>
                </bk-form-item>

                <bk-form-item
                  label={this.$t('生成附件')}
                  property='scenario_config.generate_attachment'
                  required
                >
                  <bk-radio-group
                    v-model={this.isGenerateAttach}
                    onChange={() => {
                      this.formData.scenario_config.generate_attachment = !!this.isGenerateAttach;
                    }}
                  >
                    <bk-radio label={1}>{this.$t('是')}</bk-radio>
                    <bk-radio label={0}>{this.$t('否')}</bk-radio>
                  </bk-radio-group>
                </bk-form-item>

                <bk-form-item
                  label={this.$t('只展示新类')}
                  property='scenario_config.generate_attachment'
                  required
                >
                  <bk-radio-group
                    v-model={this.isShowNewPattern}
                    onChange={() => {
                      this.formData.scenario_config.is_show_new_pattern = !!this.isShowNewPattern;
                    }}
                  >
                    <bk-radio label={1}>{this.$t('是')}</bk-radio>
                    <bk-radio label={0}>{this.$t('否')}</bk-radio>
                  </bk-radio-group>
                </bk-form-item>
              </div>
            )}
          </bk-form>
        </div>

        <div class='card-container'>
            <div class='title'>{this.$t('邮件配置')}</div>
            <bk-form
              ref='refOfEmailSubscription'
              {...{
                props: {
                  model: this.formData,
                  rules: this.formDataRules()
                }
              }}
              label-width={200}
            >
              <bk-form-item
                label={this.$t('邮件标题')}
                property='content_config__title'
                required
                error-display-type='normal'
              >
                <div style="display: flex;">
                  <bk-input
                    v-model={this.formData.content_config.title}
                    placeholder={this.$t('请输入')}
                    style="width: 465px;"
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
                      style="margin-left: 16px;font-size: 12px;"
                    >
                      <i
                        class='icon-monitor icon-mc-detail'
                        style="margin-right: 7px;"
                      ></i>
                      {this.$t('变量列表')}
                    </bk-button>

                    <div slot='content'>
                    <bk-table
                        data={this.variableTable.data}
                        stripe
                      >
                        <bk-table-column
                          label={this.$t('变量名')}
                          prop='variable'
                          width='160px'
                          scopedSlots={{
                            default: ({ row }) => {
                              return (
                                <div style="display: flex; align-items: center;">
                                  <span style="width: calc(100% - 20px);">{row.name}</span>
                                  <i
                                    class='log-icon icon-copy-2'
                                    style="font-size: 16px; margin-left: 5px; color: #3A84FF; cursor: pointer;"
                                    onClick={() => {
                                      this.handleCopy(row.name);
                                    }}
                                  ></i>
                                </div>
                              );
                            }
                          }}
                        ></bk-table-column>
                        <bk-table-column
                          label={this.$t('变量说明')}
                          width='90px'
                          prop='description'
                        ></bk-table-column>
                        <bk-table-column
                          label={this.$t('示例')}
                          width='160px'
                          prop='example'
                        ></bk-table-column>
                      </bk-table>
                    </div>
                  </bk-popover>
                </div>
              </bk-form-item>

              <bk-form-item
                label={this.$t('附带链接')}
                property='content_config.is_link_enabled'
                required
              >
                <bk-radio-group
                  v-model={this.isLinkEnabled}
                  onChange={() => {
                    this.formData.content_config.is_link_enabled = !!this.isLinkEnabled;
                  }}
                >
                  <bk-radio label={1}>{this.$t('是')}</bk-radio>
                  <bk-radio label={0}>{this.$t('否')}</bk-radio>
                </bk-radio-group>
              </bk-form-item>
            </bk-form>
        </div>

        <div class='card-container'>
          <div class='title'>{this.$t('发送配置')}</div>

          <bk-form
            ref='refOfSendingConfigurationForm'
            {...{
              props: {
                model: this.formData,
                rules: this.formDataRules()
              }
            }}
            label-width={200}
          >
            <bk-form-item
              label={this.$t('订阅名称')}
              property='name'
              required
              error-display-type='normal'
            >
              <bk-input
                v-model={this.formData.name}
                style="width: 465px;"
              ></bk-input>
            </bk-form-item>

            {/* 需要自定义校验规则 */}
            <bk-form-item
              id='subscriptor-item'
              tabindex='1'
              label={this.$t('订阅人')}
              property='channels'
              required
              error-display-type='normal'
            >
              {this.mode === 'create' && (
                <div>
                  <bk-radio-group
                    v-model={this.formData.subscriber_type}
                    style="display: inline;"
                  >
                    <bk-radio-button value='self'>{this.$t('仅自己')}</bk-radio-button>
                    <bk-radio-button value='others'>{this.$t('给他人')}</bk-radio-button>
                  </bk-radio-group>
                  {this.formData.subscriber_type === 'others' && <span style="margin-left: 10px;">
                    <i
                      class='log-icon icon-info-fill'
                      style="margin-right: 10px; color: #EA3636; font-size: 14px;"
                    ></i>
                    <span style="color: #63656E; font-size: 12px;">
                      {this.$t('给他人订阅需要经过管理员审批')}
                    </span>
                  </span>}
                </div>
              )}

              {this.formData.subscriber_type === 'others' && (
                <div>
                  <bk-checkbox v-model={this.formData.channels[0].is_enabled}>{this.$t('内部邮件')}</bk-checkbox>
                  <br />
                  <div data-is-show-error-msg={String(this.errorTips.user.isShow)}>
                    <bk-user-selector
                      ref='user-input'
                      v-model={this.subscriberInput.user}
                      api={window.BK_LOGIN_URL}
                      placeholder={this.$t('选择通知对象')}
                      empty-text={this.$t('无匹配人员')}
                      tag-type='avatar'
                      style="width: 465px; display: block;"
                      on-change={v => {
                        const userChannel = this.formData.channels.find(item => item.channel_name === 'user');
                        userChannel.subscribers = v.map(username => {
                          return {
                            id: username,
                            type: 'user',
                            is_enabled: true
                          }
                        });
                        this.$nextTick(() => {
                          this.formDataRules().channels[0].validator();
                        });
                      }}
                      on-remove-selected={v => {}}
                      on-select-user={v => {}}
                    >
                    </bk-user-selector>
                    {this.errorTips.user.isShow && <div class='form-error-tip'>{this.errorTips.user.message}</div>}
                  </div>

                  <div style="margin-top: 10px;">
                    <bk-checkbox
                      v-model={this.formData.channels[1].is_enabled}
                      style="margin-top: 10px;"
                    >
                      {this.$t('外部邮件')}
                    </bk-checkbox>
                  </div>
                  <div>
                    <bk-popover
                      trigger='click'
                      placement='right'
                      theme='light'
                      content={this.$t('多个邮箱使用逗号隔开')}
                    >
                      <div data-is-show-error-msg={String(this.errorTips.email.isShow)}>
                        <bk-input
                          ref='email-input'
                          v-model={this.subscriberInput.email}
                          disabled={!this.formData.channels[1].is_enabled}
                          style="width: 465px;"
                        >
                          <template slot='prepend'>
                            <div class='group-text'>{this.$t('邮件列表')}</div>
                          </template>
                        </bk-input>
                      </div>
                    </bk-popover>

                    <div data-is-show-error-msg='false'>
                      <bk-input
                        v-model={this.formData.channels[1].send_text}
                        disabled={!this.formData.channels[1].is_enabled}
                        placeholder={this.$t('请遵守公司规范，切勿泄露敏感信息，后果自负！')}
                        style="width: 465px; margin-top: 10px;"
                      >
                        <template slot='prepend'>
                          <div class='group-text'>{this.$t('提示文案')}</div>
                        </template>
                      </bk-input>
                    </div>
                  </div>
                  {this.errorTips.email.isShow && <div class='form-error-tip'>{this.errorTips.email.message}</div>}

                  <div style="margin-top: 10px;">
                    <bk-checkbox
                      v-model={this.formData.channels[2].is_enabled}
                      style="margin-top: 10px;"
                    >
                      {this.$t('企业微信群')}
                    </bk-checkbox>
                  </div>

                  <div data-is-show-error-msg={String(this.errorTips.wxbot.isShow)}>
                    <bk-popover
                      trigger='click'
                      placement='bottom-start'
                      theme='light'
                    >
                      <bk-input
                        ref='wxbot-input'
                        v-model={this.subscriberInput.wxbot}
                        disabled={!this.formData.channels[2].is_enabled}
                        style="width: 465px;"
                      >
                        <template slot='prepend'>
                          <div class='group-text'>{this.$t('群ID')}</div>
                        </template>
                      </bk-input>

                      <div slot='content'>
                        {this.$t('获取会话ID方法')}: <br />
                        {this.$t('1.群聊列表右键添加群机器人: 蓝鲸监控上云')}
                        <br />
                        {this.$t(`2.手动 @蓝鲸监控上云 并输入关键字'会话ID'`)}
                        <br />
                        {this.$t('3.将获取到的会话ID粘贴到输入框,使用逗号分隔')}
                      </div>
                    </bk-popover>
                  </div>
                  {this.errorTips.wxbot.isShow && <div class='form-error-tip'>{this.errorTips.wxbot.message}</div>}
                </div>
              )}
            </bk-form-item>

            {/* 需要自定义校验规则 */}
            <bk-form-item
              label={this.$t('发送频率')}
              property='frequency'
              required
              error-display-type='normal'
              class='no-relative'
            >
              <bk-radio-group v-model={this.formData.frequency.type}>
                <bk-radio label={FrequencyType.hourly}>{this.$t('按小时')}</bk-radio>
                <bk-radio label={FrequencyType.dayly}>{this.$t('按天')}</bk-radio>
                <bk-radio label={FrequencyType.weekly}>{this.$t('按周')}</bk-radio>
                <bk-radio label={FrequencyType.monthly}>{this.$t('按月')}</bk-radio>
                <bk-radio label={FrequencyType.onlyOnce}>{this.$t('仅一次')}</bk-radio>
              </bk-radio-group>

              {this.formData.frequency.type === FrequencyType.hourly && (
                <bk-select
                  ref='refOfFrequencyHour'
                  v-model={this.frequency.hour}
                  clearable={false}
                  style="width: 240px;"
                  onToggle={() => {
                    // 强行将 input 的type设置为number（组件库不允许直接设置）将操作逻辑改成和监控一样。
                    const targetEle = document.querySelector('#customHourInput input');
                    console.log(targetEle);
                    targetEle.attributes['type'].value = 'number';
                  }}
                >
                  {hourOption.map(item => {
                    return (
                      <bk-option
                        id={item.id}
                        name={item.name}
                      ></bk-option>
                    );
                  })}
                  <div slot='extension' style='padding: 10px 0;'>
                    <bk-input
                      id='customHourInput'
                      v-model={this.customHourInput}
                      type='number'
                      size='small'
                      placeholder={this.$t('输入自定义小时，按 Enter 确认')}
                      min={1}
                      max={24}
                      precision={0}
                      // @ts-ignore 只允许输入正整数
                      oninput={() => {
                        this.customHourInput = this.customHourInput.replace(/^(0+)|[^\d]+/g,'');
                      }}
                      onEnter={() => {
                        // 添加自定义 发送频率 ，如果输入有重复要直接选中。
                        let inputNumber = Number(this.customHourInput);
                        if (!inputNumber) {
                          // @ts-ignore
                          return this.$bkMessage({
                            theme: 'warning',
                            message: this.$t('请输入有效数值')
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
                        const isHasDuplicatedNum = hourOption.find(item => item.id === inputNumber);
                        if (!isHasDuplicatedNum) {
                          hourOption.push({ id: inputNumber, name: this.$t('{0}小时', [inputNumber]) });
                        }
                        this.frequency.hour = inputNumber;
                        this.customHourInput = '';
                        // @ts-ignore
                        this.$refs['refOfFrequencyHour']?.close?.();
                      }}
                    ></bk-input>
                  </div>
                </bk-select>
              )}

              {[FrequencyType.monthly, FrequencyType.weekly, FrequencyType.dayly].includes(this.formData.frequency.type) && (
                <div style="display: flex; align-items: center;">
                  {this.formData.frequency.type === 3 && (
                    <bk-select
                      v-model={this.frequency.week_list}
                      multiple
                      clearable={false}
                      style="width: 160px; margin-right: 10px; height: 32px;"
                    >
                      {weekList.map(item => {
                        return (
                          <bk-option
                            id={item.id}
                            name={item.name}
                          ></bk-option>
                        );
                      })}
                    </bk-select>
                  )}
                  {this.formData.frequency.type === FrequencyType.monthly && (
                    <bk-select
                      v-model={this.frequency.day_list}
                      multiple
                      clearable={false}
                      style="width: 160px; margin-right: 10px; height: 32px;"
                    >
                      {Array(31)
                        .fill('')
                        .map((item, index) => {
                          return (
                            <bk-option
                              id={index + 1}
                              name={index + 1 + this.$t('号').toString()}
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
                    style="width: 130px;"
                  />
                  {/* 该复选值不需要提交，后续在编辑的时候需要通过 INCLUDES_WEEKEND 和 weekList 去判断即可 */}
                  {this.formData.frequency.type === FrequencyType.dayly && (
                    <bk-checkbox
                      v-model={this.isIncludeWeekend}
                      style="margin-left: 10px;"
                    >
                      {this.$t('包含周末')}
                    </bk-checkbox>
                  )}
                </div>
              )}

              {this.formData.frequency.type === FrequencyType.onlyOnce && (
                <div>
                  <bk-date-picker
                    v-model={this.frequency.only_once_run_time}
                    type='datetime'
                    clearable={false}
                    style="width: 168px;"
                  ></bk-date-picker>
                </div>
              )}
            </bk-form-item>

            {this.formData.frequency.type !== FrequencyType.onlyOnce && (
              <bk-form-item
                label={this.$t('任务有效期')}
                property='timerange'
                required
                error-display-type='normal'
                class='no-relative'
                desc={this.$t('有效期内，订阅任务将正常发送；超出有效期，则任务失效，停止发送。')}
              >
                {/* <bk-date-picker
                  v-model={this.formData.timerange}
                  type='datetimerange'
                  format={'yyyy-MM-dd HH:mm:ss'}
                  clearable={false}
                  style='width: 465px;'
                  onChange={this.handleTimeRangeChange}
                ></bk-date-picker> */}
                <bk-date-picker
                  v-model={this.timerange.start}
                  type='datetime'
                  placeholder={`${this.$t('如')}: 2019-01-30 12:12:21`}
                  clearable={false}
                  style='width: 220px;'
                  onChange={v => {
                    this.handleTimeRangeChange([this.timerange.start, this.timerange.end]);
                  }}
                ></bk-date-picker>
                <span style='padding: 0 10px;'>-</span>
                <bk-date-picker
                  v-model={this.timerange.end}
                  ref='effectiveEndRef'
                  class='effective-end'
                  clearable
                  type='datetime'
                  placeholder={this.$t('永久')}
                  style='width: 220px;'
                  onChange={v => {
                    this.handleTimeRangeChange([this.timerange.start, this.timerange.end]);
                  }}
                  onOpen-change={this.handleDatePickerOpen}
                ></bk-date-picker>
              </bk-form-item>
            )}
          </bk-form>
        </div>
      </div>
    );
  }
}
export default ofType().convert(QuickCreateSubscription);
