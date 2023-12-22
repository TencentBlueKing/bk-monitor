import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc, ofType } from 'vue-tsx-support';
import { copyText, deepClone, transformDataKey } from '@/components/monitor-echarts/utils';
import BkUserSelector from '@blueking/user-selector';
import dayjs from 'dayjs';

import './create-subscription-form.scss';


enum Scenario {
  clustering = window.mainComponent.$t('日志聚类'),
  dashboard = window.mainComponent.$t('仪表盘'),
  scene = window.mainComponent.$t('观测场景')
}

enum PatternLevelEnum {
  '01' = 0,
  '03' = 25,
  '05' = 50,
  '07' = 75,
  '09' = 100
}

interface IProps {
  value: boolean;
}

/** 按天频率 包含周末 */
const INCLUDES_WEEKEND = [1, 2, 3, 4, 5, 6, 7];
/** 按天频率 不包含周末 */
const EXCLUDES_WEEKEND = [1, 2, 3, 4, 5];
const hourOption = [
  {
    id: 0.5,
    name: window.mainComponent.$t('0.5小时')
  },
  {
    id: 1,
    name: window.mainComponent.$t('1小时')
  },
  {
    id: 2,
    name: window.mainComponent.$t('2小时')
  },
  {
    id: 6,
    name: window.mainComponent.$t('6小时')
  },
  {
    id: 12,
    name: window.mainComponent.$t('12小时')
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
  { name: window.mainComponent.$t('星期一'), id: 1 },
  { name: window.mainComponent.$t('星期二'), id: 2 },
  { name: window.mainComponent.$t('星期三'), id: 3 },
  { name: window.mainComponent.$t('星期四'), id: 4 },
  { name: window.mainComponent.$t('星期五'), id: 5 },
  { name: window.mainComponent.$t('星期六'), id: 6 },
  { name: window.mainComponent.$t('星期日'), id: 7 }
];
const YOYList = [
  {
    id: 0,
    name: window.mainComponent.$t('不比对')
  },
  {
    id: 1,
    name: window.mainComponent.$t('1小时前')
  },
  {
    id: 2,
    name: window.mainComponent.$t('2小时前')
  },
  {
    id: 3,
    name: window.mainComponent.$t('3小时前')
  },
  {
    id: 6,
    name: window.mainComponent.$t('6小时前')
  },
  {
    id: 12,
    name: window.mainComponent.$t('12小时前')
  },
  {
    id: 24,
    name: window.mainComponent.$t('24小时前')
  }
];
const timeRangeOption = [
  {
    id: 'none',
    name: window.mainComponent.$t('按发送频率')
  },
  {
    id: '5minutes',
    name: window.mainComponent.$t('近{n}分钟', { n: 5 })
  },
  {
    id: '15minutes',
    name: window.mainComponent.$t('近{n}分钟', { n: 15 })
  },
  {
    id: '30minutes',
    name: window.mainComponent.$t('近{n}分钟', { n: 30 })
  },
  {
    id: '1hours',
    name: window.mainComponent.$t('近{n}小时', { n: 1 })
  },
  {
    id: '3hours',
    name: window.mainComponent.$t('近{n}小时', { n: 3 })
  },
  {
    id: '6hours',
    name: window.mainComponent.$t('近{n}小时', { n: 6 })
  },
  {
    id: '12hours',
    name: window.mainComponent.$t('近{n}小时', { n: 12 })
  },
  {
    id: '24hours',
    name: window.mainComponent.$t('近{n}小时', { n: 24 })
  },
  {
    id: '2days',
    name: window.mainComponent.$t('近 {n} 天', { n: 2 })
  },
  {
    id: '7days',
    name: window.mainComponent.$t('近 {n} 天', { n: 7 })
  },
  {
    id: '30days',
    name: window.mainComponent.$t('近 {n} 天', { n: 30 })
  }
];
@Component({
  name: 'QuickCreateSubscription',
  components: {
    BkUserSelector
  }
})
class QuickCreateSubscription extends tsc<IProps> {
  @Prop({ type: String, default: 'normal' }) mode: string;
  @Prop({ type: Object, default: () => {} }) detailInfo: any;
  @Prop({ type: [Number, String], default: 0 }) indexSetId: number | string;
  @Prop({ type: String, default: 'clustering' }) scenario: string;

  formData = {
    scenario: 'clustering',
    name: '',
    start_time: '',
    end_time: '',
    // 给他人/自己 订阅 。self, others 仅自己/给他人
    subscriber_type: 'self',
    scenario_config: {
      index_set_id: '',
      // 需要从 slider 上进行转换
      pattern_level: '01',
      log_display_count: 30,
      year_on_year_hour: 1,
      generate_attachment: true,
      // 展示范围，暂不需要？
      is_show_new_pattern: true,
      // 这个同比配置也不需要前端展示，暂不开放配置入口 （不用管）
      year_on_year_change: 'all',
    },
    // 这里不可以直接对组件赋值，不然最后会带上不必要的参数。
    frequency: {
      data_range: null,
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
    content_config__title: '',
  };

  frequency = {
    type: 5,
    hour: 0.5,
    run_time: dayjs().format('HH:mm:ss'),
    only_once_run_time: dayjs().format('YYYY-MM-DD HH:mm:ss'),
    week_list: [],
    day_list: [],
  };

  pattenLevelSlider = 0;

  dataRange = 'none';

  subscriberInput = {
    user: [],
    email: '',
    wxbot: ''
  }

  isIncludeWeekend = true;

  subscribeFor = 'self';

  indexSetIDList = [];

  refOfContentForm = null;
  refOfEmailSubscription = null;
  refOfSendingConfigurationForm = null;

  isShowAdvancedOption = true;
  isShowYOY = true;

  variableTable = {
    data: [],
  };

  allRecerverData = [];
  defaultGroupList = [];

  isGenerateAttach = 1;


  formDataRules() {
    return {
      frequency: [
        {
          validator: () => {
            switch (this.formData.frequency.type) {
              case 3:
                return this.frequency.week_list.length > 0;
              case 2:
                return this.frequency.day_list.length > 0;
              default:
                return true;
            }
          },
          message: window.mainComponent.$t('必填项'),
          trigger: 'blur',
        },
      ],
      channels: [
        {
          validator: () => {
            if (this.formData.subscriber_type === 'self') return true;
            console.log('channels v');

            const enabledList = this.formData.channels.filter(item => item.is_enabled);
            console.log('enabledList', enabledList);

            if (enabledList.length === 0) return false;
            const subscriberList = enabledList.filter(item => item.subscribers.length);
            console.log('subscriberList', subscriberList);

            if (subscriberList.length === 0) return false;
            return true;
          },
          message: window.mainComponent.$t('订阅人不能为空'),
          trigger: 'blur',
        },
      ],
      scenario_config__log_display_count: [
        {
          required: true,
          message: window.mainComponent.$t('必填项'),
          trigger: 'change',
        },
        {
          validator: () => {
            return Number(this.formData.scenario_config.log_display_count) >= 0;
          },
          message: window.mainComponent.$t('必需为正整数'),
          // 不要写成数组，会有 bug 。（validate 永远为 true）
          trigger: 'change',
        },
      ],
      content_config__title: [
        {
          required: true,
          message: window.mainComponent.$t('必填项'),
          trigger: 'change',
        },
      ],
      timerange: [
        {
          validator: () => {
            return this.formData.timerange.length >= 2 && this.formData.timerange.every(item => item);
          },
          message: window.mainComponent.$t('必填项'),
          trigger: 'change',
        },
      ],
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

  collectFrequency() {
    // 先手动重置一遍
    Object.assign(this.formData.frequency, {
      hour: 0,
      run_time: '',
      week_list: [],
      day_list: []
    });
    switch (this.formData.frequency.type) {
      case 5:
        Object.assign(this.formData.frequency, {
          hour: this.frequency.hour
        });
        break;
      case 4:
        Object.assign(this.formData.frequency, {
          run_time: this.frequency.run_time,
          week_list: this.isIncludeWeekend ? INCLUDES_WEEKEND : EXCLUDES_WEEKEND
        });
        break;
      case 3:
        Object.assign(this.formData.frequency, {
          run_time: this.frequency.run_time,
          week_list: this.frequency.week_list
        });
        break;
      case 2:
        Object.assign(this.formData.frequency, {
          run_time: this.frequency.run_time,
          day_list: this.frequency.day_list
        });
        break;
      case 1:
        Object.assign(this.formData.frequency, {
          run_time: this.frequency.only_once_run_time
        });
        break;
      default:
        break;
    }
  }

  handleTimeRangeChange(v) {
    console.log('handleTimeRangeChange', v);
    console.log(v.filter(item => !!item));
    console.log('this.formData.timerange', this.formData.timerange);

    if (v.filter(item => !!item).length < 2) {
      this.formData.timerange = [];
      return;
    }
    this.formData.timerange = deepClone(v);
    const result = v.map(date => {
      return dayjs(date).unix();
    });
    console.log(result);
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const [start_time, end_time] = result;
    this.formData.start_time = start_time;
    this.formData.end_time = end_time;
  }

  validateAllForms() {
    console.log(this.$store.state.userMeta?.username);
    
    if (!this.refOfContentForm) this.refOfContentForm = this.$refs.refOfContentForm;
    if (!this.refOfEmailSubscription) this.refOfEmailSubscription = this.$refs.refOfEmailSubscription;
    if (!this.refOfSendingConfigurationForm) this.refOfSendingConfigurationForm = this.$refs.refOfSendingConfigurationForm;
    this.collectFrequency();
    return Promise.all([
      this.refOfContentForm?.validate?.(),
      this.refOfEmailSubscription?.validate?.(),
      this.refOfSendingConfigurationForm?.validate?.()
    ]).then(() => {
      const cloneFormData = deepClone(this.formData);
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
      cloneFormData.name = `${cloneFormData.content_config.title}-${this.$store.state.userMeta?.username || ''}`;
      cloneFormData.bk_biz_id = this.$route.query.bizId || '';
      cloneFormData.scenario_config.index_set_id = this.indexSetId;
      return cloneFormData;
    });
  }

  /**
     * @desc 拷贝操作
     * @param { * } val
     */
  handleCopy(text) {
    copyText(`{${text}}`, msg => {
      this.$bkMessage({
        message: msg,
        theme: 'error'
      });
      return;
    });
    this.$bkMessage({
      message: window.mainComponent.$t('复制成功'),
      theme: 'success'
    });
  }

  setFormData() {
    Object.assign(this.formData, deepClone(this.detailInfo));

    this.formData.scenario = this.scenario;
    this.formData.scenario_config.index_set_id = this.indexSetId as string;
    // 时间范围
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const { data_range } = this.formData.frequency;
    this.dataRange = data_range ? ((data_range.number + data_range.time_level) as string) : 'none';
    // 敏感度
    // TODO: 为什么要这么写？
    this.$nextTick(() => {
      this.pattenLevelSlider = PatternLevelEnum[this.formData.scenario_config.pattern_level] || 0;
    });
    // 处理 订阅人 的数据
    this.subscriberInput.user = this.formData.channels[0].subscribers.map(item => item.id);
    this.subscriberInput.email = this.formData.channels[1].subscribers
      .map(item => {
        return item.id;
      })
      .toString();
    this.subscriberInput.wxbot = this.formData.channels[2].subscribers
      .map(item => {
        return item.id;
      })
      .toString();
    // 处理 发送频率 的数据
    switch (this.formData.frequency.type) {
      case 5:
        this.frequency.hour = this.formData.frequency.hour;
        break;
      case 4:
        this.frequency.run_time = this.formData.frequency.run_time;
        this.isIncludeWeekend = INCLUDES_WEEKEND.every(item => this.formData.frequency.week_list.includes(item));
        break;
      case 3:
        this.frequency.week_list = this.formData.frequency.week_list;
        this.frequency.run_time = this.formData.frequency.run_time;
        break;
      case 2:
        this.frequency.day_list = this.formData.frequency.day_list;
        this.frequency.run_time = this.formData.frequency.run_time;
        break;
      case 1:
        this.frequency.only_once_run_time = this.formData.frequency.run_time;
        break;

      default:
        break;
    }
  }

  handleNoticeReceiver() {
    const result = [];
    const groupMap = new Map();
    // console.log(allRecerverData);
    // console.log(subscriberInput);
    this.allRecerverData.forEach(item => {
      const isGroup = item.type === 'group';
      isGroup &&
        item.children.forEach(chil => {
          groupMap.set(chil.id, chil);
        });
    });
    this.subscriberInput.user.forEach(id => {
      const isGroup = groupMap.has(id);
      result.push({
        // display_name: isGroup ? groupMap.get(id)?.display_name : id,
        // logo: '',
        id,
        type: isGroup ? 'group' : 'user',
        is_enabled: true
        // subscribers: isGroup ? groupMap.get(id)?.members : undefined
      });
    });
    console.log(result);
    const userChannel = this.formData.channels.find(item => item.channel_name === 'user');
    if (userChannel) {
      userChannel.subscribers = result;
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
    if (this.formData.frequency.type === 1) {
      this.formData.start_time = null;
      this.formData.end_time = null;
      // 点击 仅一次 时刷新一次时间。
      this.frequency.only_once_run_time = dayjs().format('YYYY-MM-DD HH:mm:ss');
    }
  }

  @Watch('formData.scenario', { immediate: true })
  watchScenario() {
    this.$http.request('newReport/getVariables/', {
      query: {
        scenario: this.formData.scenario
      }
    })
      .then(response => {
        this.variableTable.data = response.data;
      })
      .catch(console.log);
  }

  get indexSetName() {
    return this.indexSetIDList.find(item => item.index_set_id === Number(this.indexSetId || 0))?.index_set_name || '';
  }

  mounted() {
    this.$http.request('retrieve/getIndexSetList', {
      query: {
        space_uid: this.$route.query.spaceUid,
      }
    })
    .then(response => {
      console.log(response);
      this.indexSetIDList = response.data;
    })
    .catch(console.log)
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
            {this.mode === 'quick' && (
              <bk-form-item label={this.$t('订阅场景')} class='text-content'>{Scenario[this.formData?.scenario]}</bk-form-item>
            )}
            {this.mode === 'quick' && <bk-form-item label={this.$t('索引集')} class='text-content'>{this.indexSetName}</bk-form-item>}
            {/* TODO：这是 观测对象 场景用的 */}
            {/* {this.mode === 'quick' && <bk-form-item label={this.$t('观测类型')}>{'观测类型'}</bk-form-item>} */}
            {/* TODO：该项可能需要从当前 URL 获取 */}
            {/* {this.mode === 'quick' && <bk-form-item label={this.$t('观测对象')}>{'观测对象'}</bk-form-item>} */}

            {this.mode === 'normal' && (
              <bk-form-item
                label={this.$t('订阅场景')}
                property='scenario'
                required
              >
                <bk-radio-group v-model={this.formData.scenario}>
                  <bk-radio-button
                    value='clustering'
                    style='width: 120px;'
                  >
                    {this.$t('日志聚类')}
                  </bk-radio-button>
                  {/* <bk-radio-button
                    value='dashboard'
                    style='width: 120px;'
                  >
                    {this.$t('仪表盘')}
                  </bk-radio-button>
                  <bk-radio-button
                    value='scene'
                    style='width: 120px;'
                  >
                    {this.$t('观测场景')}
                  </bk-radio-button> */}
                </bk-radio-group>
                {/* TODO: 跳到那里？ */}
                <bk-button
                  theme='primary'
                  text
                  style='margin-left: 24px;'
                >
                  {this.$t('跳转至场景查看')}
                  <i class='icon-monitor icon-mc-link'></i>
                </bk-button>
              </bk-form-item>
            )}

            {this.mode === 'normal' && (
              <bk-form-item
                label={this.$t('索引集')}
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
                label={this.$t('时间范围')}
                required
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
                  {this.mode === 'normal' && this.$t('高级设置')}
                  {this.mode === 'quick' && this.$t('内容配置')}
                  <i
                    class={['icon-monitor', this.isShowAdvancedOption ? 'log-icon icon-zhankai' : 'log-icon icon-zhedie']}
                    style={{ fontSize: '16px' }}
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
                      label={this.$t('展示方式')}
                      property='i'
                      required
                    >
                      <bk-radio-group v-model={this.subscriptionContentForm.model.i}>
                        <bk-radio label='1'>{this.$t('视图')}</bk-radio>
                        <bk-radio label='2'>{this.$t('列表')}</bk-radio>
                      </bk-radio-group>
                    </bk-form-item> */}

                    {/* 这是观测场景的 */}
                    {/* <bk-form-item
                      label={this.$t('数据范围')}
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
                      label={this.$t('时间范围')}
                      required
                      style={{ marginTop: '20px' }}
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
                    </bk-form-item>

                    {/* 这是观测场景的 */}
                    {/* <bk-form-item
                      label={this.$t('排列方式')}
                      property='k'
                      required
                    >
                      <bk-radio-group v-model={this.subscriptionContentForm.model.k}>
                        <bk-radio label='1'>{this.$t('一列')}</bk-radio>
                        <bk-radio label='2'>{this.$t('两列')}</bk-radio>
                      </bk-radio-group>
                    </bk-form-item> */}
                  </div>
                )}

                {/* 暂不参与配置 */}
                {/* <bk-form-item
                  label={this.$t('展示范围')}
                  property='d'
                  required
                  style={{ marginTop: '20px' }}
                >
                  <bk-radio-group v-model={this.subscriptionContentForm.model.d}>
                    <bk-radio label='1'>{this.$t('展示全部')}</bk-radio>
                    <bk-radio label='2'>{this.$t('仅展示新增')}</bk-radio>
                  </bk-radio-group>
                </bk-form-item> */}

                <bk-form-item
                  label={this.$t('敏感度')}
                  property='scenario_config.pattern_level'
                  required
                  style={{ marginTop: '20px' }}
                >
                  <div class='slider-container'>
                    <span class='text-content'>{this.$t('少')}</span>
                    <bk-slider
                      class='slider'
                      v-model={this.pattenLevelSlider}
                      step={25}
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
                  // rules={[
                  //   {
                  //     required: true,
                  //     message: this.$t('必填项'),
                  //     trigger: ['blur', 'change']
                  //   },
                  //   {
                  //     validator: () => {
                  //       return Number(this.formData.scenario_config.log_display_count) >= 0;
                  //     },
                  //     message: this.$t('必需为正整数'),
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
                      {this.$t('条')}
                    </div>
                  </bk-input>
                </bk-form-item>

                <bk-form-item
                  label={this.$t('展示同比')}
                  property='scenario_config.year_on_year_hour'
                  required
                >
                  <div style={{ display: 'flex', alignItems: 'center' }}>
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
              </div>
            )}
          </bk-form>
        </div>

        {this.mode === 'normal' && (
          <div class='card-container'>
            <div class='title'>{this.$t('邮件配置')}</div>

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
                label={this.$t('邮件标题')}
                property='content_config.title'
                required
                error-display-type='normal'
                rules={[
                  {
                    required: true,
                    message: this.$t('必填项'),
                    trigger: ['blur', 'change']
                  }
                ]}
              >
                <bk-input
                  v-model={this.formData.content_config.title}
                  placeholder={this.$t('请输入')}
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
                    {this.$t('变量列表')}
                  </bk-button>

                  <div slot='content'>
                    <bk-table
                      data={this.variableTable.data}
                      stripe
                    >
                      <bk-table-column
                        label={this.$t('变量名')}
                        prop='name'
                        scopedSlots={{
                          default: ({ row }) => {
                            return (
                              <div>
                                {row.variable}
                                <i
                                  class='log-icon icon-info-fill'
                                  style={{ fontSize: '16px', marginLeft: '5px', color: '#3A84FF', cursor: 'pointer' }}
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
                        prop='description'
                      ></bk-table-column>
                      <bk-table-column
                        label={this.$t('示例')}
                        prop='example'
                      ></bk-table-column>
                    </bk-table>
                  </div>
                </bk-popover>
              </bk-form-item>

              <bk-form-item
                label={this.$t('附带链接')}
                property='content_config.is_link_enabled'
                required
              >
                <bk-radio-group v-model={this.formData.content_config.is_link_enabled}>
                  <bk-radio label='1'>{this.$t('是')}</bk-radio>
                  <bk-radio label='2'>{this.$t('否')}</bk-radio>
                </bk-radio-group>
              </bk-form-item>
            </bk-form>
          </div>
        )}

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
            {this.mode === 'quick' && (
              <bk-form-item
                label={this.$t('邮件标题')}
                property='content_config__title'
                required
                error-display-type='normal'
                // rules={[
                //   {
                //     required: true,
                //     message: this.$t('必填项'),
                //     trigger: ['blur', 'change']
                //   }
                // ]}
              >
                <div style={{ display: 'flex' }}>
                  <bk-input
                    v-model={this.formData.content_config.title}
                    placeholder={this.$t('请输入')}
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
                          scopedSlots={{
                            default: ({ row }) => {
                              return (
                                <div>
                                  {row.name}
                                  <i
                                    class='log-icon icon-copy'
                                    style={{ fontSize: '16px', marginLeft: '5px', color: '#3A84FF', cursor: 'pointer' }}
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
                          prop='description'
                        ></bk-table-column>
                        <bk-table-column
                          label={this.$t('示例')}
                          prop='example'
                        ></bk-table-column>
                      </bk-table>
                    </div>
                  </bk-popover>
                </div>

                {/* <bk-checkbox v-model={this.sendingConfigurationForm.model.g}>{this.$t('附带链接')}</bk-checkbox> */}
              </bk-form-item>
            )}

            {this.mode === 'normal' && (
              <bk-form-item
                label={this.$t('订阅名称')}
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
              label={this.$t('订阅人')}
              property='channels'
              required
              error-display-type='normal'
            >
              {/* 先保留，不知道用不用得上 */}
              {this.mode === 'quick' && (
                <div>
                  <bk-radio-group
                    v-model={this.formData.subscriber_type}
                    style={{ display: 'inline' }}
                  >
                    <bk-radio-button value='self'>{this.$t('仅自己')}</bk-radio-button>
                    <bk-radio-button value='others'>{this.$t('给他人')}</bk-radio-button>
                  </bk-radio-group>
                  {this.formData.subscriber_type === 'others' && <span style={{ marginLeft: '10px' }}>
                    <i
                      class='icon-monitor log-icon icon-info-fill'
                      style={{ marginRight: '10px', color: '#EA3636', fontSize: '14px' }}
                    ></i>
                    <span style={{
                      color: '#63656E',
                      fontSize: '12px'
                    }}>
                      {this.$t('给他人订阅需要经过管理员审批')}
                    </span>
                  </span>}
                </div>
              )}

              {this.formData.subscriber_type === 'others' && (
                <div>
                  <bk-checkbox v-model={this.formData.channels[0].is_enabled}>{this.$t('内部邮件')}</bk-checkbox>
                  <br />
                  <div>
                    {/* <MemberSelector
                      v-model={this.subscriberInput.user}
                      group-list={this.defaultGroupList}
                      on-select-user={v => {
                        console.log(v);
                        this.handleNoticeReceiver();
                      }}
                      style={{ width: '465px' }}
                    ></MemberSelector> */}
                    <bk-user-selector
                      v-model={this.subscriberInput.user}
                      api={window.BK_LOGIN_URL}
                      placeholder={this.$t('选择通知对象')}
                      empty-text={this.$t('无匹配人员')}
                      tag-type='avatar'
                      style={{ width: '465px' }}
                      on-change={v => {
                        console.log('on-change', v);
                        const userChannel = this.formData.channels.find(item => item.channel_name === 'user');
                        userChannel.subscribers = v.map(item => {
                          return {
                            id: item.username,
                            type: 'user',
                            is_enabled: true
                          }
                        });
                      }}
                      on-remove-selected={v => {
                        console.log('on-remove-selected', v);
                      }}
                      on-select-user={v => {
                        console.log('on-select-user', v);
                      }}
                    >
                    </bk-user-selector>
                  </div>

                  <div style={{ marginTop: '10px' }}>
                    <bk-checkbox
                      v-model={this.formData.channels[1].is_enabled}
                      style={{ marginTop: '10px' }}
                    >
                      {this.$t('外部邮件')}
                    </bk-checkbox>
                  </div>
                  <bk-popover
                    trigger='click'
                    placement='right'
                    theme='light'
                    content={this.$t('多个邮箱使用逗号隔开')}
                  >
                    <bk-input
                      v-model={this.subscriberInput.email}
                      disabled={!this.formData.channels[1].is_enabled}
                      style={{ width: '465px' }}
                    >
                      <template slot='prepend'>
                        <div class='group-text'>{this.$t('邮件列表')}</div>
                      </template>
                    </bk-input>
                  </bk-popover>
                  {/* 后期补上 */}
                  <bk-input
                    v-model={this.formData.channels[1].send_text}
                    disabled={!this.formData.channels[1].is_enabled}
                    placeholder={this.$t('请遵守公司规范，切勿泄露敏感信息，后果自负！')}
                    style={{ width: '465px', marginTop: '10px' }}
                  >
                    <template slot='prepend'>
                      <div class='group-text'>{this.$t('提示文案')}</div>
                    </template>
                  </bk-input>

                  <div style={{ marginTop: '10px' }}>
                    <bk-checkbox
                      v-model={this.formData.channels[2].is_enabled}
                      style={{ marginTop: '10px' }}
                    >
                      {this.$t('企业微信群')}
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
                        <div class='group-text'>{this.$t('群ID')}</div>
                      </template>
                    </bk-input>

                    <div slot='content'>
                      {this.$t('获取会话ID方法')}: <br />
                      {this.$t('1.群聊列表右键添加群机器人: BK-Monitor')}
                      <br />
                      {this.$t(`2.手动 @BK-Monitor 并输入关键字'会话ID'`)}
                      <br />
                      {this.$t('3.将获取到的会话ID粘贴到输入框,使用逗号分隔')}
                    </div>
                  </bk-popover>
                </div>
              )}
            </bk-form-item>

            {/* 需要自定义校验规则 */}
            <bk-form-item
              label={this.$t('发送频率')}
              property='frequency'
              required
              error-display-type='normal'
            >
              <bk-radio-group v-model={this.formData.frequency.type}>
                <bk-radio label={5}>{this.$t('按小时')}</bk-radio>
                <bk-radio label={4}>{this.$t('按天')}</bk-radio>
                <bk-radio label={3}>{this.$t('按周')}</bk-radio>
                <bk-radio label={2}>{this.$t('按月')}</bk-radio>
                <bk-radio label={1}>{this.$t('仅一次')}</bk-radio>
              </bk-radio-group>

              {this.formData.frequency.type === 5 && (
                <bk-select
                  v-model={this.frequency.hour}
                  clearable={false}
                  style={{ width: '240px' }}
                >
                  {hourOption.map(item => {
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
                      {this.$t('包含周末')}
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
                    onChange={v => {
                      console.log('only_once_run_time', v);
                      
                      // this.frequency.only_once_run_time = v;
                    }}
                  ></bk-date-picker>
                </div>
              )}
            </bk-form-item>

            {this.formData.frequency.type !== 1 && (
              <bk-form-item
                label={this.$t('有效时间范围')}
                property='timerange'
                required
                error-display-type='normal'
              >
                <bk-date-picker
                  v-model={this.formData.timerange}
                  type='datetimerange'
                  format={'yyyy-MM-dd HH:mm:ss'}
                  clearable={false}
                  style='width: 465px;'
                  onChange={this.handleTimeRangeChange}
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
