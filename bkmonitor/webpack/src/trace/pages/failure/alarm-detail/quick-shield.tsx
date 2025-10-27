/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { type PropType, computed, defineComponent, reactive, ref, watch } from 'vue';

import { Button, DatePicker, Dialog, Input, Loading, Message, Tag } from 'bkui-vue';
import dayjs from 'dayjs';
import { incidentRecordOperation } from 'monitor-api/modules/incident';
import { bulkAddAlertShield } from 'monitor-api/modules/shield';
import { deepClone } from 'monitor-common/utils';
import { useI18n } from 'vue-i18n';

import DimensionTransfer from './dimension-transfer';
import VerifyInput from './verify-input/verify-input';

import type { IDetail, IDimensionConfig, IDimensionItem } from '../types';

import './quick-shield.scss';

export default defineComponent({
  name: 'QuickShield',
  props: {
    authority: {
      type: Object,
      default: () => ({}),
    },
    handleShowAuthorityDetail: {
      type: Function,
      default: null,
    },
    show: {
      type: Boolean,
      default: false,
    },
    details: {
      type: Array as PropType<IDetail[]>,
      default: () => [],
    },
    ids: {
      type: Array,
      default: () => [],
    },
    bizIds: {
      type: Array,
      default: () => [],
    },
    data: {
      type: Object,
      default: () => ({}),
    },
  },
  emits: ['success', 'change', 'time-change', 'refresh'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const loading = ref(false);
    const rule = reactive({ customTime: false });
    const timeValue = ref(18);
    const nextDayTime = ref<number | string>(10);
    const customTime = ref<any[]>(['', '']);
    const desc = ref('');
    const backupDetails = ref<IDetail[]>([]);
    const dimensionSelectShow = ref(false);
    const transferDimensionList = ref<IDimensionItem[]>([]);
    const transferTargetList = ref<string[]>([]);
    const transferEditIndex = ref(-1);

    const timeList = computed(() => [
      { name: `0.5${t('小时')}`, id: 18 },
      { name: `1${t('小时')}`, id: 36 },
      { name: `3${t('小时')}`, id: 108 },
      { name: `12${t('小时')}`, id: 432 },
      { name: `1${t('天')}`, id: 864 },
      { name: `7${t('天')}`, id: 6048 },
    ]);

    const options = reactive({
      disabledDate(date) {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        if (Array.isArray(date)) {
          return date.some(item => item.getTime() < today.getTime() || item.getTime() > today.getTime() + 8.64e7 * 181);
        }
        return date.getTime() < today.getTime() || date.getTime() > today.getTime() + 8.64e7 * 181; // 限制用户只能选择半年以内的日期
      },
    });

    const handleDialogShow = () => {
      timeValue.value = 18;
      nextDayTime.value = 10;
      desc.value = '';
      customTime.value = ['', ''];
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

    watch(
      () => props.details,
      () => {
        const data = deepClone(props.details || []);
        backupDetails.value = data.map(detail => ({
          ...detail,
          modified: false,
        }));
      },
      { immediate: true }
    );

    const handleformat = (time, fmt) => {
      const obj = {
        'M+': time.getMonth() + 1, // 月份
        'd+': time.getDate(), // 日
        'h+': time.getHours(), // 小时
        'm+': time.getMinutes(), // 分
        's+': time.getSeconds(), // 秒
        'q+': Math.floor((time.getMonth() + 3) / 3), // 季度
        S: time.getMilliseconds(), // 毫秒
      };
      if (/(y+)/.test(fmt)) {
        // fmt = fmt.replace(/(y+)/.exec(fmt)[0], `${time.getFullYear()}`.slice(-RegExp.$1.length));
        fmt = fmt.replace(RegExp.$1, `${time.getFullYear()}`.substr(4 - RegExp.$1.length));
      }
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
          rule.customTime = true;
          return false;
        }
        begin = handleformat(beginTime, 'yyyy-MM-dd hh:mm:ss');
        end = handleformat(endTime, 'yyyy-MM-dd hh:mm:ss');
      } else {
        begin = new Date();
        const nowS = begin.getTime();
        end = new Date(nowS + timeValue.value * 100000);
        if (timeValue.value === -1) {
          // 次日时间点
          if (nextDayTime.value === '') {
            rule.customTime = true;
            return false;
          }
          end = new Date();
          end.setDate(end.getDate() + 1);
          end.setHours(nextDayTime.value as number, 0, 0, 0);
        }
        begin = handleformat(begin, 'yyyy-MM-dd hh:mm:ss');
        end = handleformat(end, 'yyyy-MM-dd hh:mm:ss');
      }
      return { begin, end };
    };

    const handleSubmit = async () => {
      const time = getTime();
      if (!time) return;

      loading.value = true;
      const params = {
        bk_biz_id: props.bizIds?.[0], // this.$store.getters.bizId,
        category: 'alert',
        begin_time: time.begin,
        end_time: time.end,
        dimension_config: { alert_ids: props.ids?.map(id => id.toString()) },
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
      let toTime = dayjs(time.begin).to(dayjs(time.end), true);
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
      // 当修改维度信息时，调整入参
      const changedDetails = backupDetails.value.filter(item => item.isModified);
      if (changedDetails.length) {
        (params.dimension_config as IDimensionConfig).dimensions = changedDetails.reduce((pre, item) => {
          if (item.isModified) {
            pre[item.alertId.toString()] = item.dimension
              .filter(dim => dim.key && (dim.display_value || dim.value))
              .map(dim => dim.key);
          }
          return pre;
        }, {});
      }

      bulkAddAlertShield(params)
        .then(() => {
          emit('success', true);
          emit('time-change', toTime);
          emit('change', false);
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
    };

    const handleScopeChange = (e: Event, type: number) => {
      e.stopPropagation();
      timeValue.value = type;
      const [beginTime, endTime] = customTime.value;
      // 自定义时间异常状态
      if (type === 0 && (beginTime === '' || endTime === '')) return;
      // 至次日时间异常状态
      if (type === -1 && nextDayTime.value === '') return;
      // 校验状态通过
      rule.customTime = false;
    };

    const handleToStrategy = (id: number | string) => {
      const url = location.href.replace(location.hash, `#/strategy-config/detail/${id}`);
      window.open(url);
    };

    const handleDimensionSelect = (detail: IDetail, idx: number) => {
      transferDimensionList.value = props.details[idx].dimension;
      transferTargetList.value = detail.dimension.map(dimension => dimension.key);
      transferEditIndex.value = idx;
      dimensionSelectShow.value = true;
    };

    const handleTransferConfirm = (selectedDimensionArr: IDimensionItem[]) => {
      const idx = transferEditIndex.value;
      backupDetails.value[idx].dimension = props.details[idx].dimension.filter(dimensionItem =>
        selectedDimensionArr.some(targetItem => targetItem.key === dimensionItem.key)
      );
      backupDetails.value[idx].isModified = false;
      if (props.details[idx].dimension.length !== selectedDimensionArr.length) {
        backupDetails.value[idx].isModified = true;
      }
      dimensionSelectShow.value = false;
      handleResetTransferData();
    };

    const handleTransferCancel = () => {
      dimensionSelectShow.value = false;
      handleResetTransferData();
    };

    const handleResetTransferData = () => {
      transferDimensionList.value = [];
      transferTargetList.value = [];
      transferEditIndex.value = -1;
    };

    const getInfoComponent = () => {
      return backupDetails.value.map((detail, idx) => (
        <div
          key={idx}
          class='item-content'
        >
          {!!detail.strategy?.id && (
            <div class='column-item'>
              <div class='column-label'> {`${t('策略名称')}：`} </div>
              <div class='column-content'>
                {detail.strategy.name}
                <i
                  class='icon-monitor icon-mc-wailian'
                  onClick={() => handleToStrategy(detail.strategy.id)}
                />
              </div>
            </div>
          )}
          <div class='column-item'>
            <div class='column-label is-special'> {`${t('维度信息')}：`} </div>
            <div class='column-content'>
              {detail.dimension?.map((dem, dimensionIndex) => (
                <Tag
                  key={dem.key + dimensionIndex}
                  class='tag-theme'
                  type='stroke'
                >
                  {`${dem.display_key || dem.key}(${dem.display_value || dem.value})`}
                </Tag>
              )) || '--'}
              {props.details[idx].dimension.length > 0 && (
                <span
                  class='dimension-edit'
                  v-bk-tooltips={{ content: `${t('编辑')}` }}
                  onClick={() => handleDimensionSelect(detail, idx)}
                >
                  <i class='icon-monitor icon-bianji' />
                </span>
              )}
            </div>
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

    const getContentComponent = () => (
      <Loading loading={loading.value}>
        <div class='quick-alarm-shield-event'>
          {!loading.value ? (
            <div class='stratrgy-item'>
              <div class='item-label item-before'> {t('屏蔽时间')} </div>
              <VerifyInput
                show-validate={rule.customTime}
                {...{ on: { 'update: show-validate': val => (rule.customTime = val) } }}
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
                  <Button
                    class={['width-item', { 'is-selected': timeValue.value === -1 }]}
                    onClick={e => handleScopeChange(e, -1)}
                  >
                    {t('至次日')}
                  </Button>
                  <Button
                    class={['width-item', { 'is-selected': timeValue.value === 0 }]}
                    onClick={e => handleScopeChange(e, 0)}
                  >
                    {t('button-自定义')}
                  </Button>
                </div>
              </VerifyInput>
            </div>
          ) : undefined}
          {timeValue.value <= 0 && (
            <div class={['stratrgy-item', 'custom-time', !timeValue.value ? 'left-custom' : 'left-next-day']}>
              {timeValue.value === -1 && [
                t('至次日'),
                <Input
                  key='nextDayInput'
                  class='custom-input-time'
                  v-model={nextDayTime.value}
                  behavior='simplicity'
                  max={23}
                  min={0}
                  placeholder='0~23'
                  precision={0}
                  show-controls={false}
                  type='number'
                />,
                t('点'),
              ]}
              {timeValue.value === 0 && [
                t('自定义'),
                <DatePicker
                  key='customTime'
                  class='custom-select-time'
                  v-model={customTime.value}
                  behavior='simplicity'
                  disabledDate={options.disabledDate}
                  placeholder={t('选择日期时间范围')}
                  type='datetimerange'
                />,
              ]}
            </div>
          )}
          <div class='stratrgy-item m0'>
            <div class='item-label'> {t('屏蔽内容')} </div>
            <div class='item-tips'>
              <i class='icon-monitor icon-hint' />{' '}
              {t('屏蔽的是告警内容的这类事件，不仅仅当前的事件还包括后续屏蔽时间内产生的事件。')}{' '}
            </div>
            {getInfoComponent()}
          </div>
          <div class='stratrgy-item'>
            <div class='item-label'> {t('屏蔽原因')} </div>
            <div class='item-desc'>
              <Input
                class='stratrgy-item_textarea'
                v-model={desc.value}
                maxlength={100}
                placeholder={t('请输入')}
                resize={false}
                type='textarea'
                autosize
              />
            </div>
          </div>
        </div>
      </Loading>
    );

    return () => (
      <>
        <Dialog
          width={'804'}
          class='quick-shield-dialog'
          v-slots={{
            default: getContentComponent(),
            footer: [
              <Button
                key='submit'
                style='margin-right: 10px'
                disabled={loading.value}
                theme='primary'
                onClick={handleSubmit}
              >
                {t('确定')}
              </Button>,
              <Button
                key='change'
                onClick={() => emit('change', false)}
              >
                {t('取消')}
              </Button>,
            ],
          }}
          header-position={'left'}
          is-show={props.show}
          title={t('快捷屏蔽告警')}
          onClosed={() => emit('change', false)}
          onValue-change={val => emit('change', val)}
        />
        <Dialog
          width={640}
          class='dimension-select-dialog-wrap'
          is-show={dimensionSelectShow.value}
          quick-close={false}
          title={t('选择维度信息')}
        >
          <DimensionTransfer
            fields={transferDimensionList.value}
            show={dimensionSelectShow.value}
            value={transferTargetList.value}
            onCancel={handleTransferCancel}
            onConfirm={handleTransferConfirm}
          />
        </Dialog>
      </>
    );
  },
});
