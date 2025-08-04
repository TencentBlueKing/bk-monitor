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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import EmptyStatus from 'monitor-pc/components/empty-status/empty-status';

import EventDetail from '../../../store/modules/event-detail';
import LoadingBox from './loading-box';
import NoticeStatusDialog from './notice-status-dialog';

import type { IDetail } from './type';
import type { EmptyStatusOperationType, EmptyStatusType } from 'monitor-pc/components/empty-status/types';

import './circulation-record.scss';

const { i18n } = window;

interface ICirculationRecordProps {
  actions?: any[];
  conditions?: string[];
  detail?: IDetail;
  isScrollEnd?: boolean;
  show?: boolean;
}

@Component({
  name: 'CirculationRecord',
})
export default class CirculationRecord extends tsc<ICirculationRecordProps> {
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: Array, default: () => [] }) conditions: string[];
  @Prop({ type: Object, default: () => ({}) }) detail: IDetail;
  @Prop({ type: Boolean, default: false }) isScrollEnd: boolean;
  @Prop({ type: Array, default: () => [] }) actions: any[];

  public circulationRecord = {
    list: [],
    offset: 0,
    limit: 20,
    operate: [],
    isAll: false,
    first: true,
    loading: false,
    abnormal: false,
    defaultClickCollapseIndex: -1,
    isEnd: false,
  };
  public lastLogOffset = -1;
  public disabledClick = false;
  public operateMap = {
    CREATE: `【${i18n.t('告警产生')}】`,
    CONVERGE: `【${i18n.t('告警收敛')}】`,
    RECOVER: `【${i18n.t('告警恢复')}】`,
    CLOSE: `【${i18n.t('告警失效')}】`,
    RECOVERING: `【${i18n.t('告警恢复中')}】`,
    DELAY_RECOVER: `【${i18n.t('延迟恢复')}】`,
    ABORT_RECOVER: `【${i18n.t('中断恢复')}】`,
    SYSTEM_RECOVER: `【${i18n.t('告警恢复')}】`,
    SYSTEM_CLOSE: `【${i18n.t('告警关闭')}】`,
    ACK: `【${i18n.t('告警确认')}】`,
    SEVERITY_UP: `【${i18n.t('告警级别调整')}】`,
    ACTION: `【${i18n.t('告警处理')}】`,
    ALERT_QOS: `【${i18n.t('告警流控')}】`,
    EVENT_DROP: `【${i18n.t('事件忽略')}】`,
  };
  public alertStatusMap = {
    SUCCESS: i18n.t('成功'),
    FAILED: i18n.t('失败'),
    SHIELDED: i18n.t('已屏蔽'),
    PARTIAL_SUCCESS: i18n.t('部分失败'),
  };

  public isShowHandleStatus = false;
  public offsetId = '';
  public showLoadingBox = false;
  public actionStatusMap = {
    running: i18n.t('执行中'),
    success: i18n.t('成功'),
    failure: i18n.t('失败'),
    skipped: i18n.t('已收敛'),
    shield: i18n.t('已屏蔽'),
    partial_success: i18n.t('部分失败'),
  };

  public emptyType: EmptyStatusType = 'empty';

  @Watch('show', { immediate: true })
  handleShow(v: boolean) {
    if (v && !this.circulationRecord.list.length) {
      this.dataReset();
      this.handleGetLogList(this.conditions, true);
    }
  }

  @Watch('conditions', { deep: true })
  async handleConditions(v) {
    this.dataReset();
    await this.handleGetLogList(v);
  }

  @Watch('circulationRecord.defaultClickCollapseIndex')
  handleDefaultClickCollapseIndex(index) {
    const { list } = this.circulationRecord;
    if (index !== -1 && list[index]) {
      this.disabledClick = false;
      this.handleCollapseChange(list[index], index);
    }
  }

  @Watch('isScrollEnd')
  async handleIsScrollEnd(v) {
    if (v && !this.showLoadingBox && !this.circulationRecord.isEnd && this.show) {
      this.showLoadingBox = true;
      await this.handleGetLogList(this.conditions);
      this.showLoadingBox = false;
    }
  }

  @Emit('goto-strategy')
  handleGotoShieldStrategy(shieldId) {
    return shieldId;
  }
  @Emit('related-events')
  handleRelatedEvents(v) {
    return v;
  }

  dataReset() {
    this.circulationRecord = {
      list: [],
      offset: 0,
      limit: 20,
      operate: [],
      isAll: false,
      first: true,
      loading: false,
      abnormal: false,
      defaultClickCollapseIndex: -1,
      isEnd: false,
    };
    this.lastLogOffset = -1;
    this.isShowHandleStatus = false;
    this.showLoadingBox = false;
  }
  handleNoticeDetail(offset = '') {
    this.offsetId = offset;
    this.isShowHandleStatus = true;
  }

  async handleGetLogList(conditions, isCreate = false) {
    if (this.lastLogOffset === this.circulationRecord.offset) return;
    this.circulationRecord.abnormal = false;
    const operate = conditions || this.conditions;
    this.circulationRecord.loading = true;
    const list = await EventDetail.getListEventLog({
      bk_biz_id: this.detail.bk_biz_id,
      id: this.detail.id,
      offset: this.circulationRecord.offset,
      limit: this.circulationRecord.limit,
      operate,
    }).catch(() => {
      this.circulationRecord.loading = false;
      this.circulationRecord.abnormal = true;
      this.emptyType = '500';
    });
    if (list?.length) {
      if (isCreate) {
        this.circulationRecord.list = this.listLinkCompatibility(list);
      } else {
        this.circulationRecord.list.push(...this.listLinkCompatibility(list));
      }
      // 保留上一次的ID
      this.lastLogOffset = this.circulationRecord.offset;
      // 记录最后一位ID
      this.circulationRecord.offset = list[list.length - 1].offset;
      if (list.length < this.circulationRecord.limit) {
        this.circulationRecord.isEnd = true;
      }
    } else {
      this.circulationRecord.isAll = true;
      this.circulationRecord.isEnd = true;
    }
    this.showLoadingBox = false;
    this.circulationRecord.loading = false;
  }

  /**
   * @description 含router_info的由前端拼接url
   * @param list
   * @returns
   */
  listLinkCompatibility(list) {
    return list.map(item => {
      if (item?.routerInfo) {
        const routerName = item.routerInfo?.routerName;
        const params = item.routerInfo?.params;
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
              url: `${location.origin}${location.pathname}?bizId=${this.detail.bk_biz_id}/#/trace/alarm-shield/edit/${id}`,
            };
          }
        }
      }
      return item;
    });
  }

  // async handleInsertItemIntoLogList(item, index) {
  //   const convergeData = await EventDetail.getListConvergeLog({
  //     id: 1,
  //     time_range: `${item.beginTime} -- ${item.time}`
  //   });
  //   // 将要展开的数据插入list中并设置next属性
  //   this.circulationRecord.list.splice(index + 1, 0, ...convergeData);
  //   this.circulationRecord.list[index].next = index + convergeData.length;
  //   // 数据更新完毕通知alarm-log-list组件执行点击事件
  //   this.circulationRecord.defaultClickCollapseIndex = index;
  // }

  beforeCollapseChange(item) {
    const startTime = item.beginSourceTimestamp;
    const endTime = item.sourceTimestamp;
    this.handleRelatedEvents({
      start_time: startTime,
      end_time: endTime,
    });
    // if (!this.disabledClick && item.operate === 'CONVERGE' && item.isMultiple && !item.next) {
    //   this.handleInsertItemIntoLogList(item, index)
    //   this.disabledClick = true
    // } else {
    //   this.handleCollapseChange(item, index)
    // }
  }
  async handleCollapseChange(item, index) {
    const { list } = this.circulationRecord;
    item.expand = !item.expand;
    const preItem = list[index - 1];
    const nextItem = list[item.next];
    if (preItem) {
      const preNextItem = list.slice(0, index).find(set => set.next === index - 1);
      if (preNextItem) {
        preItem.border = !!preNextItem.expand;
        preNextItem.border = !preNextItem.expand && item.expand;
      } else {
        preItem.border = item.expand;
      }
    }
    if (nextItem) {
      // const hasNextPre = index > 2 && this.list[item.next + 1].collapse && this.list[item.next + 1].expand
      const nextPreItem = list[item.next + 1];
      if (nextPreItem?.collapse) {
        nextItem.border = nextPreItem.expand || item.expand;
      } else {
        nextItem.border = item.expand;
      }
    }
    for (let i = index + 1; i <= item.next; i++) {
      list[i].show = item.expand;
    }
    item.border = nextItem?.border && !nextItem.show;
  }

  openLink(url) {
    window.open(url);
  }

  handleOperation(type: EmptyStatusOperationType) {
    if (type === 'refresh') {
      this.emptyType = 'empty';
      this.dataReset();
      this.handleGetLogList(this.conditions, true);
    }
  }

  getTitleComponent(item) {
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
  }

  getContentComponent(item) {
    let dom = null;
    const convergeDom = () => {
      return item.contents.map((content, i) => {
        const showTip =
          i === item.index &&
          item.sourceTime &&
          (item.operate === 'CREATE' || item.operate === 'CONVERGE' || item.operate === 'EVENT_DROP');
        return (
          <span
            key={i}
            class={{
              'tip-dashed': showTip,
            }}
            v-bk-tooltips={{
              placement: 'top',
              content: showTip ? `${this.$t('数据时间')}：${item.sourceTime}` : '',
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
      if (item.operate === 'ANOMALY_NOTICE' && item.shieldType === 'saas_config') {
        child = (
          <span
            class='can-click'
            on-click={this.handleGotoShieldStrategy(item.shieldSnapshotId)}
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
              content: item.sourceTime ? `${this.$t('数据时间')}：${item.sourceTime}` : '',
              disabled: !item.sourceTime,
              allowHTML: false,
            }}
            on-click={() => item.isMultiple && this.beforeCollapseChange(item)}
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
        if (item.actionPluginType === 'notice') {
          link = (
            <span
              class='can-click m0'
              on-click={() => this.handleNoticeDetail(item.actionId)}
            >
              {' '}
              {this.$t('点击查看明细')}{' '}
            </span>
          );
        } else {
          link = (
            <span
              class='can-click m0'
              on-click={() => this.openLink(item.url)}
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
                content: item.sourceTime ? `${this.$t('数据时间')}：${item.sourceTime}` : '',
                disabled: !item.sourceTime,
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
          {this.operateMap[item.operate]}
          {dom}
        </div>
        <div
          style={{ borderColor: item.border ? '#979BA5' : '#DCDEE5' }}
          class='item-border'
        />
      </div>
    );
  }

  render() {
    const { list } = this.circulationRecord;
    return (
      <div
        class={['event-detail-circulation', { displaynone: !this.show }]}
        v-bkloading={{ isLoading: this.circulationRecord.loading }}
      >
        <ul class='log-list'>
          {list.length > 0 ? (
            list.map((item, index) => (
              <li
                key={index}
                style={{ display: !item.show ? 'none' : 'flex' }}
                class='log-list-item'
              >
                {this.getTitleComponent(item)}
                {this.getContentComponent(item)}
              </li>
            ))
          ) : (
            <EmptyStatus
              type={this.emptyType}
              onOperation={this.handleOperation}
            />
          )}

          <li
            style={{ display: this.showLoadingBox ? 'flex' : 'none' }}
            class='log-list-loading'
          >
            <LoadingBox />
          </li>
        </ul>
        <NoticeStatusDialog
          v-model={this.isShowHandleStatus}
          actionId={`${this.offsetId}`}
        />
      </div>
    );
  }
}
