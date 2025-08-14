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
import { type PropType, defineComponent, nextTick, reactive, ref, watch } from 'vue';

import { Button, DatePicker, Dialog, Input, Loading, Message } from 'bkui-vue';
import dayjs from 'dayjs';
import { incidentRecordOperation } from 'monitor-api/modules/incident';
import { bulkAddAlertShield } from 'monitor-api/modules/shield';
import { useI18n } from 'vue-i18n';

import VerifyInput from './verify-input/verify-input';

import type { IDetail } from '../types';

import './quick-shield.scss';

export default defineComponent({
  props: {
    show: { type: Boolean, default: false },
    details: { type: Array as PropType<IDetail[]>, default: () => [] },
    ids: { type: Array, default: () => [] },
    bizIds: { type: Array, default: () => [] },
    data: {
      type: Object,
      default: () => ({}),
    },
  },
  emits: ['success', 'change', 'time-change', 'refresh'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const loading = ref<boolean>(false);
    const rule = ref({ customTime: false });
    const timeList = ref([
      { name: `0.5${t('小时')}`, id: 18 },
      { name: `1${t('小时')}`, id: 36 },
      { name: `12${t('小时')}`, id: 432 },
      { name: `1${t('天')}`, id: 864 },
      { name: `7${t('天')}`, id: 6048 },
    ]);
    const timeRef = ref<HTMLDivElement>();
    const timeValue = ref<number>(18);
    const customTime = ref<string[]>(['', '']);
    const options = ref({
      disabledDate(date) {
        return date.getTime() < Date.now() - 8.64e7 || date.getTime() > Date.now() + 8.64e7 * 181; // 限制用户只能选择半年以内的日期
      },
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
        S: time.getMilliseconds(), // 毫秒
      };
      if (/(y+)/.test(fmt)) fmt = fmt.replace(RegExp.$1, `${time.getFullYear()}`.substr(4 - RegExp.$1.length));

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
            end_time: '',
          },
        };
        dayjs.locale('en');
        let toTime = `${dayjs(time.begin).to(dayjs(time.end), true)}`;
        const tims = [
          ['day', 'd'],
          ['days', 'd'],
          ['hours', 'h'],
          ['hour', 'h'],
          ['minutes', 'm'],
          ['minute', 'm'],
          ['years', 'y'],
          ['year', 'y'],
        ];
        tims.forEach(item => {
          toTime = toTime.replace(item[0], item[1]);
        });
        bulkAddAlertShield(params)
          .then(() => {
            handleSucces(true);
            handleTimeChange(toTime);
            handleShowChange(false);
            Message({ theme: 'success', message: t('创建告警屏蔽成功') });
            const { alert_name, id, incident_id } = props.data;
            incidentRecordOperation({
              id,
              incident_id,
              operation_type: 'alert_shield',
              extra_info: {
                alert_name,
                alert_id: id,
              },
            }).then(res => {
              res && setTimeout(() => emit('refresh'), 2000);
            });
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

    const getInfoCompnent = () => {
      return props.details.map((detail, index) => (
        <div
          key={index}
          class='item-content'
        >
          {!!detail.strategy?.id && (
            <div class='column-item'>
              <div class='column-label'> {`${t('策略名称')}：`} </div>
              <div class='column-content'>
                {detail.strategy.name}
                <i
                  class='icon-monitor icon-mc-wailian'
                  onClick={() => handleToStrategy(detail.strategy.id as number)}
                />
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
            style='margin-bottom: 18px'
            class='column-item'
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
                        class={['width-item', { 'is-selected': timeValue.value === item.id }]}
                        onClick={e => handleScopeChange(e, item.id)}
                      >
                        {item.name}
                      </Button>
                    ))}
                    {timeValue.value !== 0 ? (
                      <Button
                        class={['custom-width', { 'is-selected': timeValue.value === 0 }]}
                        onClick={e => handleScopeChange(e, 0)}
                      >
                        {t('button-自定义')}
                      </Button>
                    ) : (
                      <DatePicker
                        ref='timeRef'
                        v-model={customTime.value}
                        appendToBody={true}
                        options={options.value}
                        placeholder={t('选择日期时间范围')}
                        type={'datetimerange'}
                      />
                    )}
                  </div>
                </VerifyInput>
              </div>
            ) : undefined}
            <div class='stratrgy-item m0'>
              <div class='item-label'> {t('告警内容')} </div>
              <div class='item-tips'>
                <i class='icon-monitor icon-hint' />{' '}
                {t('屏蔽的是告警内容的这类事件，不仅仅当前的事件还包括后续屏蔽时间内产生的事件。')}{' '}
              </div>
              {getInfoCompnent()}
            </div>
            <div class='stratrgy-item'>
              <div class='item-label'> {t('屏蔽原因')} </div>
              <div class='item-desc'>
                <Input
                  style='width: 625px'
                  v-model={desc.value}
                  maxlength={100}
                  placeholder={t('请输入')}
                  rows={3}
                  type='textarea'
                />
              </div>
            </div>
          </div>
        </Loading>
      );
    };

    return {
      loading,
      timeRef,
      handleSubmit,
      getAuthority,
      getContentComponent,
      handleShowChange,
      t,
    };
  },
  render() {
    return (
      <Dialog
        width={'804'}
        class='quick-shield-dialog'
        v-slots={{
          default: this.getContentComponent(),
          footer: [
            <Button
              // v-authority={{ active: !this.getAuthority()?.ALARM_SHIELD_MANAGE_AUTH }}
              key='submit'
              style='margin-right: 10px'
              disabled={this.loading}
              theme='primary'
              onClick={this.handleSubmit}
            >
              {this.t('确定')}
            </Button>,
            <Button
              key='change'
              onClick={() => this.handleShowChange(false)}
            >
              {this.t('取消')}
            </Button>,
          ],
        }}
        header-position={'left'}
        is-show={this.show}
        title={this.t('快捷屏蔽告警')}
        onClosed={this.handleShowChange}
        onValue-change={this.handleShowChange}
      />
    );
  },
});
