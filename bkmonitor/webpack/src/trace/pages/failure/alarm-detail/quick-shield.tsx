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
import { defineComponent, nextTick, PropType, reactive, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Button, DatePicker, Dialog, Input, Loading, Message } from 'bkui-vue';
import moment from 'moment';

import { bulkAddAlertShield } from '../../../../monitor-api/modules/shield';

import VerifyInput from './verify-input/verify-input';

import './quick-shield.scss';

export interface IDetail {
  severity: number;
  dimension?: string;
  trigger?: string;
  strategy?: {
    name?: string;
    id?: number;
  };
}

export default defineComponent({
  // @Inject('authority') authority;
  // @Inject('authorityFromEventDetail') authorityFromEventDetail;
  // @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;
  // @Inject('handleShowAuthorityDetailFromEventDetail') handleShowAuthorityDetailFromEventDetail;
  props: {
    show: { type: Boolean, default: false },
    details: { type: Array as PropType<IDetail[]>, default: () => [] },
    ids: { type: Array, default: () => [] },
    bizIds: { type: Array, default: () => [] }
  },
  emits: ['success', 'change', 'time-change'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const loading = ref(false);
    const rule = ref({ customTime: false });
    const timeList = ref([
      { name: `0.5${t('小时')}`, id: 18 },
      { name: `1${t('小时')}`, id: 36 },
      { name: `12${t('小时')}`, id: 432 },
      { name: `1${t('天')}`, id: 864 },
      { name: `7${t('天')}`, id: 6048 }
    ]);
    const timeRef = ref(null);
    const timeValue = ref(18);
    const customTime = ref(['', '']);
    const options = ref({
      disabledDate(date) {
        return date.getTime() < Date.now() - 8.64e7 || date.getTime() > Date.now() + 8.64e7 * 181; // 限制用户只能选择半年以内的日期
      }
    });
    const levelMap = reactive(['', t('致命'), t('提醒'), t('预警')]);
    const desc = ref('');

    const handleDialogShow = () => {
      // this.loading = true
      timeValue.value = 18;
      desc.value = '';
      customTime.value = ['', ''];
    };
    const handleformat = (time, fmte) => {
      let fmt = fmte;
      const obj = {
        'M+': time.getMonth() + 1, // 月份
        'd+': time.getDate(), // 日
        'h+': time.getHours(), // 小时
        'm+': time.getMinutes(), // 分
        's+': time.getSeconds(), // 秒
        'q+': Math.floor((time.getMonth() + 3) / 3), // 季度
        S: time.getMilliseconds() // 毫秒
      };
      if (/(y+)/.test(fmt)) fmt = fmt.replace(RegExp.$1, `${time.getFullYear()}`.substr(4 - RegExp.$1.length));
      // eslint-disable-next-line no-restricted-syntax
      for (const key in obj) {
        if (new RegExp(`(${key})`).test(fmt)) {
          fmt = fmt.replace(
            RegExp.$1,
            RegExp.$1.length === 1 ? obj[key] : `00${obj[key]}`.substr(`${obj[key]}`.length)
          );
        }
      }
      return fmt;
    };
    const getTime = () => {
      let begin: Date = null;
      let end: Date = null;
      if (timeValue.value === 0) {
        const [beginTime, endTime] = customTime.value;
        if (beginTime === '' || endTime === '') {
          rule.value.customTime = true;
          return false;
        }
        begin = handleformat(beginTime, 'yyyy-MM-dd hh:mm:ss');
        end = handleformat(endTime, 'yyyy-MM-dd hh:mm:ss');
      } else {
        begin = new Date();
        const nowS = begin.getTime();
        end = new Date(nowS + timeValue.value * 100000);
        begin = handleformat(begin, 'yyyy-MM-dd hh:mm:ss');
        end = handleformat(end, 'yyyy-MM-dd hh:mm:ss');
      }
      return { begin, end };
    };
    const handleSubmit = () => {
      const time = getTime();
      if (time) {
        loading.value = true;
        const params = {
          bk_biz_id: props.bizIds?.[0], // this.$store.getters.bizId,
          category: 'alert',
          begin_time: time.begin,
          end_time: time.end,
          dimension_config: { alert_ids: props.ids },
          shield_notice: false,
          description: desc.value,
          cycle_config: {
            begin_time: '',
            type: 1,
            day_list: [],
            week_list: [],
            end_time: ''
          }
        };
        moment.locale('en');
        let toTime = `${moment(time.begin).to(moment(time.end), true)}`;
        const tims = [
          ['day', 'd'],
          ['days', 'd'],
          ['hours', 'h'],
          ['hour', 'h'],
          ['minutes', 'm'],
          ['minute', 'm'],
          ['years', 'y'],
          ['year', 'y']
        ];
        tims.forEach(item => {
          toTime = toTime.replace(item[0], item[1]);
        });
        bulkAddAlertShield(params)
          .then(() => {
            handleSucces(true);
            handleTimeChange(toTime);
            handleShowChange(false);
            Message({ theme: 'success', message: t('恭喜，创建告警屏蔽成功') });
          })
          .finally(() => {
            loading.value = false;
          });
      }
    };

    const handleSucces = v => {
      emit('success', v);
    };

    const handleShowChange = v => {
      emit('change', v);
    };
    const handleTimeChange = (val: string) => {
      emit('time-change', val);
    };

    const handleScopeChange = (e, type) => {
      e.stopPropagation();
      timeValue.value = type;
      if (type === 0) {
        nextTick(() => {
          const refTime: any = timeRef.value;
          refTime.visible = true;
        });
      } else {
        customTime.value = ['', ''];
      }
    };
    watch(
      () => props.ids,
      (newIds, oldIds) => {
        if (`${JSON.stringify(newIds)}` !== `${JSON.stringify(oldIds)}`) {
          handleDialogShow();
        }
      },
      { immediate: true }
    );
    const handleToStrategy = (id: number) => {
      const url = location.href.replace(location.hash, `#/strategy-config/detail/${id}`);
      window.open(url);
    };

    const getAuthority = (): any => {
      // return props.authority
    };

    const getHandleShowAuthorityDetail = (action: any) => {
      // handleShowAuthorityDetail(action);
    };

    const getInfoCompnent = () => {
      return props.details.map(detail => (
        <div class='item-content'>
          {!!detail.strategy?.id && (
            <div class='column-item'>
              <div class='column-label'> {`${t('策略名称')}：`} </div>
              <div class='column-content'>
                {detail.strategy.name}
                <i
                  class='icon-monitor icon-mc-wailian'
                  onClick={() => handleToStrategy(detail.strategy.id)}
                ></i>
              </div>
            </div>
          )}
          <div class='column-item'>
            <div class='column-label'> {`${t('告警级别')}：`} </div>
            <div class='column-content'>{levelMap[detail.severity]}</div>
          </div>
          <div class='column-item'>
            <div class='column-label'> {`${t('维度信息')}：`} </div>
            <div class='column-content'>{detail.dimension}</div>
          </div>
          <div
            class='column-item'
            style='margin-bottom: 18px'
          >
            <div class='column-label'> {`${t('触发条件')}：`} </div>
            <div class='column-content'>{detail.trigger}</div>
          </div>
        </div>
      ));
    };

    const getContentComponent = () => {
      return (
        <Loading loading={loading.value}>
          <div class='quick-alarm-shield-event'>
            {!loading.value ? (
              <div class='stratrgy-item'>
                <div class='item-label item-before'> {t('屏蔽时间')} </div>
                <VerifyInput
                  show-validate={rule.value.customTime}
                  {...{ on: { 'update: show-validate': val => (rule.value.customTime = val) } }}
                  validator={{ content: t('至少选择一种时间') }}
                >
                  <div class='item-time'>
                    {timeList.value.map((item, index) => (
                      <Button
                        key={index}
                        onClick={e => handleScopeChange(e, item.id)}
                        class={['width-item', { 'is-selected': timeValue.value === item.id }]}
                      >
                        {item.name}
                      </Button>
                    ))}
                    {timeValue.value !== 0 ? (
                      <Button
                        onClick={e => handleScopeChange(e, 0)}
                        class={['custom-width', { 'is-selected': timeValue.value === 0 }]}
                      >
                        {t('button-自定义')}
                      </Button>
                    ) : (
                      <DatePicker
                        ref='timeRef'
                        type={'datetimerange'}
                        placeholder={t('选择日期时间范围')}
                        options={options.value}
                        v-model={customTime.value}
                      ></DatePicker>
                    )}
                  </div>
                </VerifyInput>
              </div>
            ) : undefined}
            <div class='stratrgy-item m0'>
              <div class='item-label'> {t('告警内容')} </div>
              <div class='item-tips'>
                <i class='icon-monitor icon-hint'></i>{' '}
                {t('屏蔽的是告警内容的这类事件，不仅仅当前的事件还包括后续屏蔽时间内产生的事件。')}{' '}
              </div>
              {getInfoCompnent()}
            </div>
            <div class='stratrgy-item'>
              <div class='item-label'> {t('屏蔽原因')} </div>
              <div class='item-desc'>
                <Input
                  placeholder={t('请输入')}
                  type='textarea'
                  v-model={desc.value}
                  width={625}
                  rows={3}
                  maxlength={100}
                ></Input>
              </div>
            </div>
          </div>
        </Loading>
      );
    };

    return {
      loading,
      timeRef,
      getHandleShowAuthorityDetail,
      handleSubmit,
      getAuthority,
      getContentComponent,
      handleShowChange
    };
  },
  render() {
    return (
      <Dialog
        class='quick-shield-dialog'
        is-show={this.show}
        onClosed={this.handleShowChange}
        onValueChange={this.handleShowChange}
        title={this.$t('快捷屏蔽告警')}
        header-position={'left'}
        width={'804'}
        v-slots={{
          default: this.getContentComponent(),
          footer: [
            <Button
              onClick={() =>
                this.getAuthority()?.ALARM_SHIELD_MANAGE_AUTH
                  ? this.handleSubmit()
                  : this.getHandleShowAuthorityDetail(this.getAuthority()?.ALARM_SHIELD_MANAGE_AUTH)
              }
              theme='primary'
              style='margin-right: 10px'
              disabled={this.loading}
              // v-authority={{ active: !this.getAuthority()?.ALARM_SHIELD_MANAGE_AUTH }}
            >
              {this.$t('确定')}
            </Button>,
            <Button onClick={() => this.handleShowChange(false)}>{this.$t('取消')}</Button>
          ]
        }}
      ></Dialog>
    );
  }
});
