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
import { type PropType, computed, defineComponent } from 'vue';

import dayjs from 'dayjs';
import { toBcsDetail, toPerformanceDetail } from 'fta-solutions/common/go-link';
import { ETagsType } from 'monitor-common/utils/biz';
import { TabEnum as CollectorTabEnum } from 'monitor-pc/pages/collector-config/collector-detail/typings/detail';
import { useI18n } from 'vue-i18n';

import { useAppStore } from '@/store/modules/app';

import type { IAlert } from '../typeing';

import './alarm-info.scss';

export default defineComponent({
  name: 'AlarmInfo',
  props: {
    data: Object as PropType<IAlert>,
    readonly: Boolean,
  },
  emits: ['manualProcess', 'alarmDispatch'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const appStore = useAppStore();
    const bizItem = computed(() => appStore.bizList.find(item => item.id === props.data.bk_biz_id));
    const bizIdName = computed(() =>
      bizItem.value?.space_type_id === ETagsType.BKCC
        ? `#${bizItem.value?.id}`
        : bizItem.value?.space_id || bizItem.value?.space_code || ''
    );
    const cloudIdMap = ['bk_target_cloud_id', 'bk_cloud_id'];
    const ipMap = ['bk_target_ip', 'ip', 'bk_host_id', 'tags.bcs_cluster_id'];

    /** 维度列表 */
    const filterDimensions = computed(() => {
      return props.data.dimensions?.filter(item => !(cloudIdMap.includes(item.key) && item.value === 0));
    });

    /* bk_collect_config_id */
    const bkCollectConfigId = computed(() => {
      const labels = props.data?.extra_info?.strategy?.labels || [];
      const need = labels.some(item => ['集成内置', 'Datalink BuiltIn'].includes(item));
      return need
        ? props.data.dimensions?.find(
            item => item.key === 'bk_collect_config_id' || item.key === 'tags.bk_collect_config_id'
          )?.value
        : '';
    });

    /** 渲染维度信息列表 */
    const renderDimensionsInfo = () => {
      return filterDimensions.value?.length
        ? filterDimensions.value?.map(item => [
            <span
              key={item.display_key}
              style={{
                cursor: ipMap.includes(item.key) ? 'pointer' : 'auto',
              }}
              class='dimensions-item'
              onClick={() => handleToPerformance(item)}
            >
              <span class='name'>{item.display_key}</span>
              <span class='eq'>=</span>
              <span
                style='margin-left: 0; display: block'
                class={['content', { 'info-check': ipMap.includes(item.key) }]}
              >
                {item.display_value}
              </span>
            </span>,
          ])
        : '--';
    };

    /** 不同情况下的跳转逻辑 */
    const handleToPerformance = item => {
      const isKeyInIpMap = ipMap.includes(item.key);
      if (!isKeyInIpMap) {
        return;
      }
      switch (item.key) {
        /** 增加集群跳转到BCS */
        case 'tags.bcs_cluster_id':
          toBcsDetail(item.project_name, item.value);
          break;

        /** 跳转到主机监控 */
        case 'bk_host_id':
          toPerformanceDetail(props.data.bk_biz_id, item.value);
          break;

        default: {
          const cloudIdItem = props.data.dimensions.find(dim => cloudIdMap.includes(dim.key));
          if (!cloudIdItem) {
            return;
          }
          const cloudId = cloudIdItem.value;
          toPerformanceDetail(props.data.bk_biz_id, `${item.value}-${cloudId}`);
          break;
        }
      }
    };

    /** 基础信息 */
    const basicInfoForm = computed(() => [
      [
        { title: t('所属空间'), text: bizItem.value ? `${bizItem.value?.text} (${bizIdName.value})` : '--' },
        {
          title: t('告警状态'),
          content: renderAlarmStatus,
        },
      ],
      [
        {
          title: t('异常时间'),
          text: dayjs.tz(props.data.first_anomaly_time * 1000).format('YYYY-MM-DD HH:mm:ss'),
          timeZone: dayjs.tz(props.data.first_anomaly_time * 1000).format('Z'),
        },
        { title: t('处理阶段'), content: renderCurrentStage },
      ],
      [
        {
          title: t('告警产生'),
          text: dayjs.tz(props.data.create_time * 1000).format('YYYY-MM-DD HH:mm:ss'),
          timeZone: dayjs.tz(props.data.create_time * 1000).format('Z'),
        },
        {
          title: t('负责人'),
          extCls: 'flex-wrap',
          content: () =>
            props.data.appointee?.length
              ? props.data.appointee.map((v, index, arr) => [
                  <bk-user-display-name
                    key={v}
                    user-id={v}
                  />,
                  index !== arr.length - 1 ? <span key={`${v}-${index}`}>{','}</span> : null,
                ])
              : '--',
        },
      ],
      [
        { title: t('持续时间'), text: props.data.duration },
        { title: t('关注人'), content: getFollowerInfo },
      ],
    ]);

    /** 告警状态 */
    function renderAlarmStatus() {
      return (
        <div class='alarm-status'>
          <span class='total'>7 次(7次失败)</span>
          <span class='icon-monitor icon-xiangqing1'>{t('详情')}</span>
        </div>
      );
    }

    /** 处理阶段 */
    function renderCurrentStage() {
      return (
        <span>
          {props.data.stage_display || '--'}
          {!props.readonly && [
            <span
              key='manual-process'
              onClick={() => emit('manualProcess')}
            >
              <span class='icon-monitor icon-chuli'>{t('手动处理')}</span>
            </span>,
            <span
              key='manual-dispatch'
              onClick={() => emit('alarmDispatch')}
            >
              <span class='alarm-dispatch'>
                <span class='icon-monitor icon-fenpai'>{t('告警分派')}</span>
              </span>
            </span>,
          ]}
        </span>
      );
    }

    /* 关注人 */
    function getFollowerInfo() {
      return (
        <span class='follower-info'>
          {props.data?.follower?.length
            ? props.data?.follower.map((v, index, arr) => [
                <bk-user-display-name
                  key={v}
                  user-id={v}
                />,
                index !== arr.length - 1 ? <span key={`${v}-${index}`}>{','}</span> : null,
              ])
            : '--'}
          {!!props.data?.follower?.length && !!bkCollectConfigId.value && (
            <span
              class='fenxiang-btn'
              onClick={handleToCollectDetail}
            >
              <span>{t('变更')}</span>
              <span class='icon-monitor icon-fenxiang' />
            </span>
          )}
        </span>
      );
    }

    function handleToCollectDetail() {
      window.open(
        `${location.origin}${location.pathname}?bizId=${props.data.bk_biz_id}#/collect-config/detail/${bkCollectConfigId.value}?tab=${CollectorTabEnum.TargetDetail}`
      );
    }

    return {
      renderDimensionsInfo,
      basicInfoForm,
    };
  },
  render() {
    return (
      <div class='alarm-center-detail-alarm-info'>
        <div class='block-title'>维度信息</div>
        <div class='dimension-info'>{this.renderDimensionsInfo()}</div>
        <div class='block-title mt-18'>基础信息</div>
        <div class='basic-info'>
          {this.basicInfoForm.map((item, index) => (
            <div
              key={index}
              class='basic-info-form-item'
            >
              {item.map((item, ind) => (
                <div
                  key={ind}
                  class={['item-col', item.extCls]}
                >
                  <div
                    class='item-label'
                    v-en-class='fb-146'
                  >
                    {item.title}：
                  </div>
                  {item.content ? (
                    <div class='item-content'>{item.content()}</div>
                  ) : (
                    <div class='item-content'>
                      {item.text}
                      {item.timeZone ? <span class='item-time-zone'>{item.timeZone}</span> : undefined}
                      {item.icon ? (
                        <span
                          class={['icon-monitor', item.icon]}
                          v-bk-tooltips={{ content: item.iconTip, allowHTML: false }}
                          on-click={item.click ? item.click : false}
                        >
                          <span class='icon-title'>{item?.iconText || ''}</span>
                        </span>
                      ) : undefined}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    );
  },
});
