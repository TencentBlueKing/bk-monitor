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
import { type PropType, defineComponent, shallowReactive, shallowRef, watch } from 'vue';

import { Checkbox } from 'bkui-vue';
import { listAlertLog } from 'monitor-api/modules/alert';
import EmptyStatus from 'trace/components/empty-status/empty-status';
import { useI18n } from 'vue-i18n';

import type { AlarmDetail } from '../../../typings/detail';

import './alarm-records.scss';

const OperateMap = {
  CREATE: `【${window.i18n.t('告警产生')}】`,
  CONVERGE: `【${window.i18n.t('告警收敛')}】`,
  RECOVER: `【${window.i18n.t('告警恢复')}】`,
  CLOSE: `【${window.i18n.t('告警失效')}】`,
  RECOVERING: `【${window.i18n.t('告警恢复中')}】`,
  DELAY_RECOVER: `【${window.i18n.t('延迟恢复')}】`,
  ABORT_RECOVER: `【${window.i18n.t('中断恢复')}】`,
  SYSTEM_RECOVER: `【${window.i18n.t('告警恢复')}】`,
  SYSTEM_CLOSE: `【${window.i18n.t('告警关闭')}】`,
  ACK: `【${window.i18n.t('告警确认')}】`,
  SEVERITY_UP: `【${window.i18n.t('告警级别调整')}】`,
  ACTION: `【${window.i18n.t('告警处理')}】`,
  ALERT_QOS: `【${window.i18n.t('告警流控')}】`,
  EVENT_DROP: `【${window.i18n.t('事件忽略')}】`,
};

const getListEventLog = async params => {
  const data = await listAlertLog(params);
  for (const item of data) {
    item.logIcon = `icon-mc-alarm-${item.operate.toLocaleLowerCase()}`;
    if (item.operate === 'RECOVER' || item.operate === 'RECOVERING') {
      item.logIcon = 'icon-mc-alarm-recovered';
    }
    if (item.operate === 'ABORT_RECOVER') {
      item.logIcon = 'icon-mc-alarm-notice';
    }
    if (item.operate === 'ANOMALY_NOTICE') {
      item.logIcon = 'icon-mc-alarm-notice';
    }
    if (item.operate === 'ACTION' || item.operate === 'ALERT_QOS') {
      item.logIcon = 'icon-mc-alarm-converge';
    }

    if (item.operate === 'CLOSE' || item.operate === 'SYSTEM_CLOSE' || item.operate === 'EVENT_DROP') {
      item.logIcon = 'icon-mc-alarm-closed';
    }

    if (item.is_multiple) {
      item.collapse = true;
      item.expandTime = `${item.begin_time} 至 ${item.time}`;
      item.expand = false;
    } else {
      item.collapse = false;
      item.expand = true;
    }
    item.border = false;
    item.show = true;
    item.expandDate = '';
  }
  return data;
};

export default defineComponent({
  name: 'AlarmRecords',
  props: {
    detail: {
      type: Object as PropType<AlarmDetail>,
      default: () => null,
    },
  },
  setup(props) {
    const { t } = useI18n();

    const circulationFilter = shallowRef([
      {
        id: 'CREATE',
        name: t('告警产生'),
      },
      {
        id: 'CONVERGE',
        name: t('告警收敛'),
      },
      {
        id: 'RECOVER',
        name: t('告警恢复'),
      },
      {
        id: 'RECOVERING',
        name: t('告警恢复中'),
      },
      {
        id: 'CLOSE',
        name: t('告警关闭'),
      },
      {
        id: 'DELAY_RECOVER',
        name: t('延迟恢复'),
      },
      {
        id: 'ABORT_RECOVER',
        name: t('中断恢复'),
      },
      {
        id: 'SYSTEM_RECOVER',
        name: t('系统恢复'),
      },
      {
        id: 'SYSTEM_CLOSE',
        name: t('系统关闭'),
      },
      {
        id: 'ACK',
        name: t('告警确认'),
      },
      {
        id: 'SEVERITY_UP',
        name: t('告警级别调整'),
      },
      {
        id: 'ACTION',
        name: t('处理动作'),
      },
      {
        id: 'ALERT_QOS',
        name: t('告警流控'),
      },
      {
        id: 'EVENT_DROP',
        name: t('事件忽略'),
      },
    ]);
    const checked = shallowRef(circulationFilter.value.map(item => item.id));

    const recordData = shallowReactive({
      list: [],
      offset: 0,
      limit: 20,
      loading: false,
      scrollLoading: false,
      defaultClickCollapseIndex: -1,
      isEnd: false,
    });
    const lastLogOffset = shallowRef(-1);

    const emptyType = shallowRef('empty');

    const listLinkCompatibility = list => {
      return list.map(item => {
        if (item?.router_info) {
          const routerName = item.router_info?.router_name;
          const params = item.router_info?.params;
          if (routerName === 'alarm-shield-detail') {
            return {
              ...item,
              url: `${location.origin}${location.pathname}?bizId=${params?.bizId}/#/trace/alarm-shield/edit/${params?.shieldId}`,
            };
          }
          if (routerName === 'alarm-dispatch') {
            return {
              ...item,
              url: `${location.origin}${location.pathname}?bizId=${params?.bizId}/#/alarm-dispatch?group_id=${params?.groupId}`,
            };
          }
        } else if (item?.url) {
          if (typeof item.url === 'string') {
            const match = item.url.match(/\/alarm-shield-detail\/(\d+)/);
            const id = match?.[1];
            if (id) {
              return {
                ...item,
                url: `${location.origin}${location.pathname}?bizId=${props.detail.bk_biz_id}/#/trace/alarm-shield/edit/${id}`,
              };
            }
          }
        }
        return item;
      });
    };

    const handleGetLogList = async () => {
      if (lastLogOffset.value === recordData.offset) {
        return;
      }
      if (recordData.list.length) {
        recordData.scrollLoading = true;
      } else {
        recordData.loading = true;
      }
      const list = await getListEventLog({
        bk_biz_id: props.detail.bk_biz_id,
        id: props.detail.id,
        offset: recordData.offset,
        limit: recordData.limit,
        operate: checked.value,
      }).catch(() => {
        recordData.loading = false;
        emptyType.value = '500';
        return [];
      });
      recordData.list = [...recordData.list, ...listLinkCompatibility(list)];
      // 保留上一次的ID
      lastLogOffset.value = recordData.offset;
      // 记录最后一位ID
      recordData.offset = list[list.length - 1].offset;
      if (list.length < recordData.limit) {
        recordData.isEnd = true;
      }
      recordData.scrollLoading = false;
      recordData.loading = false;
    };

    watch(
      () => props.detail,
      val => {
        if (val) {
          handleGetLogList();
        }
      },
      { immediate: true }
    );

    return {
      circulationFilter,
      checked,
      recordData,
      emptyType,
      t,
    };
  },
  render() {
    const getTitleComponent = item => {
      return (
        <div class='item-title'>
          {/* {
          item.collapse
            ? <span class={['item-title-set', 'icon-monitor', item.expand ? 'icon-mc-minus-plus' : 'icon-mc-plus-fill']}
              on-click={ () => this.beforeCollapseChange(item)}></span> : undefined
        } */}
          <span class='item-title-icon'>
            <i class={['icon-monitor', item.logIcon]} />
          </span>
          <span class='item-title-date'>{item.expand ? item.time : item.expandTime}</span>
        </div>
      );
    };
    const getContentComponent = item => {
      let dom = null;
      const convergeDom = () => {
        return item.contents.map((content, i) => {
          const showTip =
            i === item.index &&
            item.source_time &&
            (item.operate === 'CREATE' || item.operate === 'CONVERGE' || item.operate === 'EVENT_DROP');
          return (
            <span
              key={i}
              class={{
                'tip-dashed': showTip,
              }}
              v-bk-tooltips={{
                placement: 'top',
                content: showTip ? `${this.$t('数据时间')}：${item.source_time}` : '',
                disabled: !showTip,
                allowHTML: false,
              }}
            >
              {content || '--'}
            </span>
          );
        });
      };
      if (item.contents.length === 1) {
        let child = null;
        if (item.operate === 'ANOMALY_NOTICE' && item.shield_type === 'saas_config') {
          child = (
            <span
              class='can-click'
              // on-click={this.handleGotoShieldStrategy(item.shieldSnapshotId)}
            >
              {this.$t('查看屏蔽策略')}
            </span>
          );
        }
        dom = (
          <span>
            <span
              class={{ 'tip-dashed': item.operate === 'CREATE' || item.operate === 'CONVERGE' }}
              v-bk-tooltips={{
                placement: 'top',
                content: item.source_time ? `${this.$t('数据时间')}：${item.source_time}` : '',
                disabled: !item.source_time,
                allowHTML: false,
              }}
              // on-click={() => item.isMultiple && this.beforeCollapseChange(item)}
            >
              {item.count > 1
                ? `${this.$t('当前事件流水过多，收敛{count}条。', { count: item.count })}`
                : item.contents[0] || '--'}
            </span>
            {child}
          </span>
        );
        if (item.operate === 'ACTION') {
          const textList = item.contents[0].split('$');
          let link = null;
          if (item.action_plugin_type === 'notice') {
            link = (
              <span
                class='can-click m0'
                // on-click={() => this.handleNoticeDetail(item.action_id)}
              >
                {' '}
                {this.$t('点击查看明细')}{' '}
              </span>
            );
          } else {
            link = (
              <span
                class='can-click m0'
                // on-click={() => this.openLink(item.url)}
              >
                {' '}
                {textList[1]}{' '}
              </span>
            );
          }
          dom = [
            // text,
            textList[0],
            link,
            textList[2],
          ];
        }
      } else if (item.operate === 'ANOMALY_NOTICE') {
        // dom = [
        //   item.contents[0],
        //   item.contents[1].map(text => (<span class="notice-group">{text}</span>)),
        //   item.contents[2],
        //   <span class="notice-status">{this.alertStatusMap[item.contents[3]]}</span>,
        //   <span class="can-click" on-click={() => this.handleNoticeDetail(item.offset)}> { this.$t('点击查看明细') } </span>
        // ]
      } else if (item.operate === 'ACK') {
        dom = [
          item.contents[0],
          <span
            key={'alarm-ack'}
            class='alarm-ack'
          >
            {item.contents[1]}
          </span>,
        ];
      } else if (
        item.contents.length > 1 &&
        (item.operate === 'CREATE' || item.operate === 'CONVERGE' || item.operate === 'EVENT_DROP')
      ) {
        dom = convergeDom();
      }
      if (item.operate === 'EVENT_DROP') {
        if (item.count > 1) {
          dom = (
            <span>
              <span
                class='tip-dashed'
                v-bk-tooltips={{
                  placement: 'top',
                  content: item.source_time ? `${this.$t('数据时间')}：${item.source_time}` : '',
                  disabled: !item.source_time,
                  allowHTML: false,
                }}
              >
                {this.$t('低级别事件流水过多，已忽略{count}条。', { count: item.count })}
              </span>
            </span>
          );
        } else {
          dom = convergeDom();
        }
      }
      return (
        <div class='item-content'>
          <div class='item-content-desc'>
            {OperateMap[item.operate]}
            {dom}
          </div>
          <div
            style={{ borderColor: item.border ? '#979BA5' : '#DCDEE5' }}
            class='item-border'
          />
        </div>
      );
    };
    return (
      <div class='alarm-detail-alarm-view-alarm-records'>
        <div class='alarm-records-header'>
          <span class='header-title'>{this.t('节点过滤')}</span>
          <span class='header-options'>
            <Checkbox.Group modelValue={this.checked}>
              {this.circulationFilter.map(item => (
                <Checkbox
                  key={item.id}
                  label={item.id}
                >
                  {item.name}
                </Checkbox>
              ))}
            </Checkbox.Group>
          </span>
        </div>
        <ul class='log-list'>
          {this.recordData.list.length > 0 ? (
            this.recordData.list.map((item, index) => (
              <li
                key={index}
                style={{ display: !item.show ? 'none' : 'flex' }}
                class='log-list-item'
              >
                {getTitleComponent(item)}
                {getContentComponent(item)}
              </li>
            ))
          ) : (
            <EmptyStatus
              type={this.emptyType}
              // onOperation={this.handleOperation}
            />
          )}
        </ul>
      </div>
    );
  },
});
