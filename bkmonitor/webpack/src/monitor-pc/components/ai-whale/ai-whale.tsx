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

import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import AiBlueking, { RoleType, type AIBluekingExpose } from '@blueking/ai-blueking/vue2';
import { fetchRobotInfo } from 'monitor-api/modules/commons';
import { copyText } from 'monitor-common/utils/utils';
import { throttle } from 'throttle-debounce';

import aiWhaleStore from '../../store/modules/ai-whale';
import { getEventPaths } from '../../utils';

import './ai-whale.scss';
import '@blueking/ai-blueking/dist/vue2/style.css';

/* 最近n天 枚举 1h, 3h, 6h, 12h,1d */
const fetchRangeOfStr = {
  '1h': `1${window.i18n.tc('小时')}`,
  '3h': `3${window.i18n.tc('小时')}`,
  '6h': `4${window.i18n.tc('小时')}`,
  '12h': `12${window.i18n.tc('小时')}`,
  '1d': `1${window.i18n.tc('天')}`,
};

/* 蓝 红 黄 枚举 */
const levelOfColor = {
  1: 'red',
  2: 'yellow',
  3: 'blue',
};

/* 以下路由不显示此组件 */
// export const AI_WHALE_EXCLUDE_ROUTES =
//   ['event-center', 'event-action', 'event-center-detail', 'event-center-action-detail'];
export const AI_WHALE_EXCLUDE_ROUTES = ['no-business', 'error-exception', 'share']; // 告警页也可显示ai小鲸

interface IHostPreviewListItem {
  ip: string;
  exception_metric_count: number;
  other_metric_count?: number;
  bk_cloud_id?: number;
}
interface IWhaleHelperListItem {
  icon_name?: string;
  link: string;
  name: string;
}

type ThemeType = 'blue' | 'red' | 'yellow';

export type AIQuickActionData = {
  type: 'explanation' | 'translate';
  content: string;
};

interface IData {
  alert: {
    abnormal_count: number; // 空间告警
    emergency_count: number;
    recent_count: number;
    latest_person_abnormal_count?: number; // 个人最近新增告警
    person_abnormal_count?: number; // 个人最近告警
  };
  intelligent_detect: {
    host: {
      abnormal_count: number;
      preview: {
        exception_metric_count: number;
        ip: string;
        other_metric_count?: number;
      }[];
    };
  };
  link: IWhaleHelperListItem[];
  need_notice: boolean;
  fetch_range?: string;
  robot_level?: number;
}

const robotWidth = 64;

const tipClassName = 'ai-small-whale-tip-content';
const questions = [
  '蓝鲸监控的告警包含哪几个级别？',
  '如何在仪表盘中进行指标计算？',
  '主机监控场景包含哪些指标？',
  '如何接入第三方告警源？',
  '智能检测目前能支持哪些场景？',
];
@Component
export default class AiWhale extends tsc<{
  enableAiAssistant: boolean;
}> {
  @Ref('robot') robotRef: HTMLDivElement;
  @Ref('aiAssistant') aiAssistantRef: AIBluekingExpose;
  @Prop({ default: false }) enableAiAssistant: boolean;
  type: ThemeType = 'blue';
  /* 机器人位置 */
  whalePosition = {
    top: 0,
    left: 0,
  };
  /* 当前是否展开 */
  isExpand = false;
  /* 当前屏幕宽高 */
  width = 0;
  height = 0;
  /* 是否已点击机器人 */
  downActive = false;
  /* 主机列表 */
  hostPreviewList: IHostPreviewListItem[] = [];
  /* 弹出层实例 */
  popoverInstance = null;
  hoverTimer = null;
  /* 轮询 */
  timeInstance = null;
  /* 区分点击/与拖拽 */
  downTime = 0;
  data: IData = null;
  /* 最近xx时间 */
  fetchRange = `1${window.i18n.tc('天')}`;
  /* 蓝色小球链接列表 */
  whaleHelperList: IWhaleHelperListItem[] = [];
  /* 10分钟已弹出则不再主动弹出 */
  lastRecordTime = 0;

  /* AI Blueking */
  prompts = questions.map((v, index) => ({ id: index + 1, content: window.i18n.tc(v) }));
  background = '#f5f7fa';
  headBackground = 'linear-gradient(267deg, #2dd1f4 0%, #1482ff 95%)';
  positionLimit = {
    top: 0,
    bottom: 0,
    left: 0,
    right: 0,
  };
  startPosition = {
    right: 10,
    left: window.innerWidth - 480 - 10,
    bottom: 20,
    top: window.innerHeight - 600 - 20,
  };
  mousemoveFn: (event: MouseEvent) => void;
  resizeFn = () => {};

  get showAIBlueking() {
    return aiWhaleStore.showAIBlueking;
  }

  get messages() {
    return aiWhaleStore.messages;
  }

  get loading() {
    return aiWhaleStore.loading;
  }
  get space() {
    const { bizId } = this.$store.getters;
    return this.$store.getters.bizList.find(item => item.id === bizId) || { name: '', type_name: '' };
  }
  @Watch('enableAiAssistant', { immediate: true })
  enableAiAssistantChange() {
    this.enableAiAssistant && aiWhaleStore.initStreamChatHelper();
  }

  @Watch('$store.state.aiWhale.aiQuickActionData')
  handleIsTypeChange(newVal: AIQuickActionData, oldVal: AIQuickActionData) {
    // 检查新值是否有 type 和 content
    if (newVal.type && newVal.content && (newVal.type !== oldVal.type || newVal.content !== oldVal.content)) {
      this.aiAssistantRef.quickActions(newVal.type, newVal.content);
    }
  }
  created() {
    this.mousemoveFn = throttle(50, this.handleMousemove);
    this.resizeFn = throttle(50, this.handleWindowResize);
    aiWhaleStore.setDefaultMessage();
    window.addEventListener('resize', this.resizeFn);
  }

  mounted() {
    document.addEventListener('mouseup', this.handleMouseup);
    this.width = document.querySelector('.bk-monitor').clientWidth;
    this.height = document.querySelector('.bk-monitor').clientHeight;
    this.whalePosition.top = this.height - robotWidth - 20;
    this.whalePosition.left = this.width - robotWidth / 2;
    this.init();
  }

  destroyed() {
    document.removeEventListener('mouseup', this.handleMouseup);
    window.removeEventListener('resize', this.resizeFn);
    window.clearInterval(this.timeInstance);
    window.clearTimeout(this.hoverTimer);
    this.handlePopoverHidden();
  }
  getDefaultMessage() {
    return [
      {
        content: `${this.$t('你好，我是AI小鲸，你可以向我提问蓝鲸监控产品使用相关的问题。')}<br/>${this.$t('例如')}：<a href="javascript:;" data-ai='${JSON.stringify({ type: 'send', content: this.$t('监控策略如何使用？') })}' class="ai-clickable">${this.$t('监控策略如何使用？')}</a>`,
        role: RoleType.Assistant,
      },
    ];
  }
  handleWindowResize() {
    this.width = document.querySelector('.bk-monitor').clientWidth;
    this.height = document.querySelector('.bk-monitor').clientHeight;
    if (this.popoverInstance) {
      this.handlePopoverHidden();
    }
    const height = this.height - robotWidth - 20;
    const width = this.width - robotWidth / 2;
    this.whalePosition.top = height;
    this.whalePosition.left = width;
  }

  /* 点击小球 */
  handleMousedown(event: MouseEvent) {
    event.preventDefault();
    // this.handlePopoverHidden();
    this.downActive = true;
    this.downTime = new Date().getTime();
    document.addEventListener('mousemove', this.mousemoveFn);
  }
  /* 小球停止移动 */
  handleMouseup(event: Event) {
    this.downActive = false;
    document.removeEventListener('mousemove', this.mousemoveFn);
    if (
      getEventPaths(event)
        .map(item => item.className)
        .includes(tipClassName)
    )
      return;
    if (this.getIsDrag()) {
      this.handleClose();
    } else {
      this.handleInitiativeTip();
    }
  }

  /* 小球移动 */
  handleMousemove(event: MouseEvent) {
    if (this.downActive) {
      this.handlePopoverHidden();
      this.whalePosition.top = (() => {
        if (event.pageY <= 0) return 0 - robotWidth / 2;
        if (event.pageY >= this.height) return this.height - robotWidth / 2;
        return event.pageY - robotWidth / 2;
      })();
      this.whalePosition.left = (() => {
        if (event.pageX <= 0) return 0 - robotWidth / 2;
        if (event.pageX >= this.width) return this.width - robotWidth / 2;
        return event.pageX - robotWidth / 2;
      })();
    }
  }

  /* tip弹窗 */
  handlePopoverShow(e: Event, wait = 300) {
    if (this.downActive) return;
    this.hoverTimer && window.clearTimeout(this.hoverTimer);
    this.hoverTimer = setTimeout(() => {
      if (this.popoverInstance?.show) {
        this.popoverInstance?.show?.();
      } else {
        this.handlePopoverHidden();
        this.popoverInstance = this.$bkPopover(e.target, {
          content: this.$refs.tips,
          trigger: 'manual',
          interactive: true,
          // triggerTarget: e.target,
          theme: 'light ai-whale',
          arrow: true,
          placement: 'top',
          boundary: 'window',
          hideOnClick: false,
        });
        this.popoverInstance?.show?.();
      }
    }, wait);
  }
  /* 清除tip */
  handlePopoverHidden() {
    this.hoverTimer && window.clearTimeout(this.hoverTimer);
    this.popoverInstance?.hide?.(0);
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
  }

  /* 收起 */
  handleClose() {
    this.handlePopoverHidden();
    this.whalePosition.left = this.width - robotWidth / 2;
  }

  handleClick(event: Event) {
    event.stopPropagation();
  }

  /* 跳转链接 */
  handleToHelpItem(item: IWhaleHelperListItem) {
    if (item.link) {
      window.open(item.link);
    }
  }

  /* 展开主机预览 */
  handleHostPreview(isExpand: boolean) {
    this.handlePopoverHidden();
    this.isExpand = isExpand;
    setTimeout(() => {
      this.handlePopoverShow({ target: this.robotRef } as any, 200);
    }, 0);
  }

  /* 获取告警信息，每两分钟拉取一次 */
  init() {
    this.handleGetData();
    this.timeInstance = setInterval(
      () => {
        this.handleGetData();
      },
      2 * 60 * 1000
    );
  }

  /* 调取接口 */
  async handleGetData() {
    this.handlePopoverHidden();
    const data = await fetchRobotInfo({}, { reject403: true }).catch(() => null);
    if (data) {
      this.data = data;
      const level = this.data?.robot_level || 3;
      this.type = levelOfColor[level];
      if (this.type !== 'red' || !this.data.intelligent_detect?.host) {
        this.isExpand = false;
      }
      this.fetchRange = fetchRangeOfStr[this.data?.fetch_range || '1d'];
      this.hostPreviewList = this.data.intelligent_detect?.host?.preview || [];
      this.whaleHelperList = this.data.link || [];
      if (this.data.need_notice) {
        if (this.lastRecordTime) {
          const needTime = 10 * 60 * 1000;
          const curTime = new Date().getTime();
          if (curTime - this.lastRecordTime < needTime) {
            this.lastRecordTime = curTime;
            return;
          }
          this.lastRecordTime = 0;
        } else {
          this.lastRecordTime = new Date().getTime();
        }
        this.$nextTick(() => {
          this.handleInitiativeTip(true);
        });
      }
    } else {
      this.hostPreviewList = [];
    }
  }

  /* 主动弹出 */
  handleInitiativeTip(isInit = false) {
    this.whalePosition.left = this.width - robotWidth;
    if (isInit) {
      this.handlePopoverHidden();
    }
    setTimeout(() => {
      this.handlePopoverShow({ target: this.robotRef } as any);
    }, 0);
  }

  /* 区分点击与拖拽 */
  getIsDrag() {
    const curTime = new Date().getTime();
    const isDrag = curTime - this.downTime > 300;
    this.downTime = 0;
    return isDrag;
  }

  /* 跳转到事件中心 */
  handleToEventCenter(isSeverity = false) {
    const fetchRange = this.data?.fetch_range || '24h';
    let query = '';
    if (isSeverity) {
      query = `activeFilterId=MY_ASSIGNEE&from=now-${fetchRange}&to=now`;
    } else {
      // const condition = encodeURIComponent('{"severity":[1]}');
      query = `activeFilterId=NOT_SHIELDED_ABNORMAL&from=now-${fetchRange}&to=now`;
    }
    const url = `${location.origin}${location.pathname}?bizId=${
      this.$store.getters.bizId || window.cc_biz_id
    }#/event-center?${query}`;
    window.open(url);
  }

  handleClickCopyIp() {
    const copyStr = this.hostPreviewList.map(item => item.ip).join('\n');
    copyText(copyStr, msg => {
      this.$bkMessage({
        message: msg,
        theme: 'error',
      });
      return;
    });
    this.$bkMessage({
      message: this.$t('复制成功'),
      theme: 'success',
    });
  }

  /* 跳转到主机详情 */
  handleToPerformance(ip, bkCloudId) {
    const fetchRange = this.data?.fetch_range || '24h';
    const url = `${location.origin}${location.pathname}?bizId=${
      this.$store.getters.bizId || window.cc_biz_id
    }#/performance/detail/${ip}-${bkCloudId || 0}?from=now-${fetchRange}&to=now`;
    window.open(url);
  }

  /* 跳转到ai设置 */
  handleToAiSettings() {
    const url = `${location.origin}${location.pathname}?bizId=${
      this.$store.getters.bizId || window.cc_biz_id
    }#/ai-settings`;
    window.open(url);
  }
  /* 跳转到策略 */
  handleToStrategyConfig() {
    const url = `${location.origin}${location.pathname}?bizId=${
      this.$store.getters.bizId || window.cc_biz_id
    }#/strategy-config/add`;
    window.open(url);
  }
  handleAiBluekingClear() {
    aiWhaleStore.setDefaultMessage();
  }
  handleAiBluekingStop() {
    aiWhaleStore.stopChatHelper();
  }
  handleAiBluekingClose() {
    aiWhaleStore.setShowAIBlueking(false);
  }
  handleAiBluekingChoosePrompt(prompt) {
    console.log('choose prompt', prompt);
  }
  handleToggleAiBlueking() {
    aiWhaleStore.setShowAIBlueking(!this.showAIBlueking);
    // this.startPosition.left = this.whalePosition.left +;
  }
  handleAiBluekingClick(v: string) {
    const data = JSON.parse(v);
    if (data?.type !== 'send') return;
    aiWhaleStore.handleAiBluekingSend(data);
  }
  createAIContent() {
    const countSpan = count => {
      const countNum = Number(count || 0);
      if (countNum === 0) {
        return <span class='grey-bold'>{countNum}</span>;
      }
      return <span class='red-bold'>{countNum}</span>;
    };
    const helpList = () => (
      <div class='help-list'>
        {this.whaleHelperList.map(item => (
          <div
            key={item.name}
            class='help-item'
            onClick={() => this.handleToHelpItem(item)}
          >
            {item.icon_name ? <span class={['icon-monitor', `${item.icon_name}`]} /> : undefined}
            <span>{item.name}</span>
          </div>
        ))}
      </div>
    );
    const abnormalCountContent = () => (
      <div class='click-message'>
        <span
          class={{ 'can-click': !!this.data.alert.abnormal_count }}
          onClick={() => !!this.data.alert.abnormal_count && this.handleToEventCenter()}
        >
          <i18n path='当前空间: [{0}] {1}  ； 未恢复告警: {2}'>
            <span>{this.space.type_name}</span>
            <span>{this.space.name}</span>
            <span class='blue-bold'>{this.data.alert.abnormal_count}</span>
          </i18n>
          {!!this.data.alert.abnormal_count && <span class='icon-monitor icon-fenxiang' />}
        </span>
      </div>
    );
    if (this.type === 'blue') {
      return (
        <div class='blue-content'>
          <div class='header'>
            <div class='left'>
              <div>{this.$t('AI小鲸发现当前有')}:</div>
            </div>
            <div
              class='right'
              onClick={this.handleClose}
            >
              {this.$t('收起')}
            </div>
          </div>
          <div class='click-message click-message-blue-type'>
            <span
              class={{ 'can-click': !!this.data.alert.abnormal_count }}
              onClick={() => !!this.data.alert.abnormal_count && this.handleToEventCenter()}
            >
              <i18n path='当前空间: [{0}] {1}  ； 未恢复告警: {2}'>
                <span>{this.space.type_name}</span>
                <span>{this.space.name}</span>
                <span class='blue-bold'>{this.data.alert.abnormal_count}</span>
              </i18n>
            </span>
          </div>
          <div class='content'>
            <div>{this.$t('如有其他问题,可选择:')}</div>
            {helpList()}
          </div>
        </div>
      );
    }
    if (this.type === 'red') {
      return (
        <div class='red-content'>
          {(() => {
            if (this.isExpand) {
              return (
                <div class='host-detail'>
                  <div class='header'>
                    <div class='left'>
                      <i18n path='主机智能异常检测发现{0}个主机异常'>
                        {countSpan(this.data.intelligent_detect?.host?.abnormal_count)}
                      </i18n>
                      :
                    </div>
                    <div
                      class='right'
                      onClick={this.handleClose}
                    >
                      {this.$t('收起')}
                    </div>
                  </div>
                  <div class='table-content'>
                    <bk-table
                      data={this.hostPreviewList}
                      maxHeight={259}
                    >
                      <bk-table-column
                        renderHeader={() => (
                          <span>
                            <span>{this.$t('内网IP')}</span>
                            <span
                              class='icon-monitor icon-mc-copy'
                              onClick={this.handleClickCopyIp}
                            />
                          </span>
                        )}
                        scopedSlots={{
                          default: props => (
                            <span
                              class='link'
                              onClick={() => {
                                this.handleToPerformance(props.row.ip, props.row?.bk_cloud_id);
                              }}
                            >
                              {props.row.ip}
                            </span>
                          ),
                        }}
                      />
                      <bk-table-column
                        label={this.$t('异常指标数')}
                        prop='exception_metric_count'
                        resizable={false}
                      />
                      {/* <bk-table-column label={this.$t('其他指标')} prop="other_metric_count"></bk-table-column> */}
                    </bk-table>
                    <div class='bottom-options'>
                      <div
                        class='option'
                        onClick={() => this.handleHostPreview(false)}
                      >
                        <span class='icon-monitor icon-back-left' />
                        <span>{this.$t('返回概览')}</span>
                      </div>
                      <div
                        class='option'
                        onClick={this.handleToAiSettings}
                      >
                        <span class='icon-monitor icon-menu-setting' />
                        <span>{this.$t('AI设置')}</span>
                      </div>
                      {/* <div class="option" onClick={this.handleToStrategyConfig}>
              <span class="icon-monitor icon-mc-add-strategy"></span>
              <span>{this.$t('新建策略')}</span>
            </div> */}
                    </div>
                  </div>
                </div>
              );
            }
            return (
              <div class='alert-overview'>
                <div class='header'>
                  <div class='left'>
                    <span>{this.$t('AI小鲸发现当前有')}:</span>
                  </div>
                  <div
                    class='right'
                    onClick={this.handleClose}
                  >
                    {this.$t('收起')}
                  </div>
                </div>
                <div class='content'>
                  {abnormalCountContent()}
                  {!!this.data.alert.person_abnormal_count && (
                    <div class='click-message'>
                      <span
                        class={{ 'can-click': !!this.data.alert.person_abnormal_count }}
                        onClick={() => !!this.data.alert.person_abnormal_count && this.handleToEventCenter(true)}
                      >
                        <i18n path='当前您有未恢复告警{0}条,最近{1}新增{2}条'>
                          {countSpan(this.data.alert.person_abnormal_count)}
                          <span>
                            <span class='grey-bold'>{this.fetchRange.match(/[1236]+/g)[0]}</span>
                            {this.fetchRange.match(/[\u4e00-\u9fa5A-Za-z\s]+/g)?.[0] || ''}
                          </span>
                          {countSpan(this.data.alert.latest_person_abnormal_count)}
                        </i18n>
                        {!!this.data.alert.latest_person_abnormal_count && <span class='icon-monitor icon-fenxiang' />}
                      </span>
                    </div>
                  )}
                  {!!this.data.intelligent_detect?.host && (
                    <div class='click-message'>
                      <span
                        class={{ 'can-click': !!this.data.intelligent_detect?.host?.abnormal_count }}
                        onClick={() =>
                          !!this.data.intelligent_detect?.host?.abnormal_count && this.handleHostPreview(true)
                        }
                      >
                        <i18n path='主机智能异常检测发现最近{0}{1}台主机异常'>
                          <span>
                            <span class='grey-bold'>{this.fetchRange?.match(/[1236]+/g)?.[0] || ''}</span>
                            {this.fetchRange.match?.(/[\u4e00-\u9fa5A-Za-z\s]+/g)?.[0] || ''}
                          </span>
                          {countSpan(this.data.intelligent_detect?.host?.abnormal_count) || 0}
                        </i18n>
                        {!!this.data.intelligent_detect?.host?.abnormal_count && (
                          <span class='icon-monitor icon-double-down' />
                        )}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            );
          })()}
        </div>
      );
    }
    return (
      <div class='red-content'>
        <div class='alert-overview'>
          <div class='header'>
            <div class='left'>
              <span>{this.$t('AI小鲸发现当前有')}:</span>
            </div>
            <div
              class='right'
              onClick={this.handleClose}
            >
              {this.$t('收起')}
            </div>
          </div>
          <div class='content'>
            {abnormalCountContent()}
            <div class='mt16'>{this.$t('如有其他问题,可选择:')}:</div>
            {helpList()}
          </div>
        </div>
      </div>
    );
  }
  createAiBlueking() {
    return (
      <AiBlueking
        ref='aiAssistant'
        class='ai-blueking'
        background={this.background}
        head-background={this.headBackground}
        isShow={this.showAIBlueking}
        loading={this.loading}
        messages={this.messages}
        placeholder={this.$t('您可以键入“/”查看更多提问示例')}
        position-limit={this.positionLimit}
        prompts={this.prompts}
        start-position={this.startPosition}
        on-ai-click={this.handleAiBluekingClick}
        onChoose-prompt={this.handleAiBluekingChoosePrompt}
        onClear={this.handleAiBluekingClear}
        onClose={this.handleAiBluekingClose}
        onSend={aiWhaleStore.handleAiBluekingSend}
        onShowDialog={(v: boolean) => {
          aiWhaleStore.setShowAIBlueking(v);
        }}
        onStop={this.handleAiBluekingStop}
      />
    );
  }
  createAIDialogFooter() {
    return (
      <div
        class='ai-whale-footer'
        onClick={this.handleToggleAiBlueking}
      >
        <span class='ai-icon' />
        {this.showAIBlueking ? this.$t('关闭 AI 小鲸会话') : this.$t('打开 AI 小鲸会话')}
      </div>
    );
  }
  render() {
    return (
      <div class='ai-small-whale'>
        {!!this.data && (
          <div
            ref='robot'
            style={{
              top: `${this.whalePosition.top}px`,
              left: `${this.whalePosition.left}px`,
            }}
            class={['robot-img', this.type]}
            onClick={this.handleClick}
            onMousedown={event => this.handleMousedown(event)}
            onMouseenter={event => this.handlePopoverShow(event)}
          />
        )}
        <div style={{ display: 'none' }}>
          {!!this.data && (
            <div
              ref='tips'
              class={tipClassName}
            >
              {this.createAIContent()}
              {this.enableAiAssistant && this.createAIDialogFooter()}
            </div>
          )}
        </div>
        {this.enableAiAssistant && this.createAiBlueking()}
      </div>
    );
  }
}
