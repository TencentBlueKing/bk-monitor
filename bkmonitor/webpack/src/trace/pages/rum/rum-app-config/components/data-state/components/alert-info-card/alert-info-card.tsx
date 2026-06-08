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

import { type PropType, defineComponent, useTemplateRef } from 'vue';

import { Button, Switcher } from 'bkui-vue';
import { getAlarmCenterListHash } from 'monitor-common/utils/alarm-center-router';
import { isEnFn } from 'monitor-pc/utils';
import { useI18n } from 'vue-i18n';

import { usePopover } from '../../../../../../alarm-center/components/alarm-table/hooks/use-popover';
import AlertTrendMiniChart from '../alert-trend-mini-chart/alert-trend-mini-chart';
import ConfirmActionBar from '../confirm-action-bar/confirm-action-bar';

import type { TimeRangeType } from '../../../../../../../components/time-range/utils';
import type { AsyncDialogConfirmEvent, IStrategyData } from '../../../../../typings';

import './alert-info-card.scss';

/** 跳转路由映射表 */
const JUMP_HASH_MAP: Record<'edit' | 'event', (id: number) => string> = {
  edit: id => `#/strategy-config/edit/${id}`,
  event: id => {
    const isEn = isEnFn();
    return getAlarmCenterListHash({
      queryString: `${isEn ? 'strategy_id' : window.i18n.t('策略ID')} : ${id}`,
    });
  },
};

export default defineComponent({
  name: 'AlertInfoCard',
  props: {
    /** 无数据告警策略信息 */
    strategyInfo: {
      type: Object as PropType<IStrategyData>,
      default: () => ({}),
    },
    /** 骨架屏加载状态 */
    loading: {
      type: Boolean,
      default: false,
    },
    /** 时间范围 */
    timeRange: {
      type: Array as PropType<TimeRangeType>,
      default: () => [],
    },
  },
  emits: {
    /** 开关变化事件，携带 AsyncDialogConfirmEvent 供父组件 resolve/reject 控制 Switcher loading 状态 */
    enabledChange: (_event: AsyncDialogConfirmEvent<{ is_enabled: boolean }>) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    /** Switch 触发元素引用 */
    const switchRef = useTemplateRef<HTMLDivElement>('switchRef');

    /** 确认弹窗控制器 */
    const { hidePopover, showPopover } = usePopover({
      showDelay: 0,
      tippyOptions: {
        appendTo: () => document.body,
        arrow: true,
        interactive: true,
        offset: [0, 8],
        placement: 'top',
        theme: 'light padding-0',
        trigger: 'manual',
      },
    });

    /**
     * @description 处理 Switch before-change，弹出确认弹窗后触发 enabledChange 事件。
     *   返回 Promise 使 Switcher 在确认弹窗和接口请求期间显示 loading 状态；
     *   用户取消或接口失败时 reject，Switcher 回退到原状态。
     * @param {boolean} newVal - 即将切换的目标值
     * @returns {Promise<void>} resolve 切换 / reject 回退
     */
    const handleSwitchBeforeChange = (newVal: boolean): Promise<void> => {
      if (!switchRef.value) {
        return Promise.reject();
      }

      let promiseResolve: () => void;
      let promiseReject: () => void;
      const promise = new Promise<void>((res, rej) => {
        promiseResolve = res;
        promiseReject = rej;
      });

      // promise settle 后关闭 popover
      promise.finally(hidePopover);

      const popoverAnchor = {
        currentTarget: switchRef.value,
      } as unknown as MouseEvent;

      showPopover(
        popoverAnchor,
        (
          <ConfirmActionBar
            title={props.strategyInfo?.is_enabled ? t('确认关闭？') : t('确认开启？')}
            onClose={() => {
              promiseReject();
            }}
            onConfirm={() =>
              emit('enabledChange', {
                payload: { is_enabled: newVal },
                resolve: promiseResolve,
                reject: promiseReject,
                promise,
              })
            }
          />
        ) as unknown as Element,
        {
          onHidden: () => {
            promiseReject();
          },
        }
      );

      return promise;
    };

    /**
     * @description 处理页面跳转（告警事件中心/策略编辑）
     * @param {'edit' | 'event'} type - 跳转类型：'edit' 跳转策略编辑 | 'event' 跳转事件中心
     * @returns {void}
     */
    const handlePageJump = (type: 'edit' | 'event') => {
      const { id } = props.strategyInfo ?? {};
      const hash = JUMP_HASH_MAP[type](id);
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_blank', 'noopener,noreferrer');
    };

    return {
      t,
      switchRef,
      handleSwitchBeforeChange,
      handlePageJump,
    };
  },
  render() {
    return (
      <div class='alert-info-card'>
        {this.loading ? (
          <div class='skeleton-element alert-info-card-skeleton' />
        ) : (
          <div class='alert-info-card-main'>
            {/* 左侧：无数据告警开关 */}
            <div class='alert-info-card-left'>
              <span
                class='alert-label'
                v-bk-tooltips={{
                  content: this.t('当没有收到任何数据可以进行告警通知。'),
                  allowHTML: false,
                }}
              >
                {this.t('无数据告警')}
              </span>
              <div
                ref='switchRef'
                class='switch-wrapper'
              >
                <Switcher
                  beforeChange={this.handleSwitchBeforeChange}
                  modelValue={this.strategyInfo?.is_enabled}
                  size='small'
                  theme='primary'
                />
              </div>
            </div>

            {/* 右侧：告警历史与操作链接 */}
            <div class='alert-info-card-right'>
              <div class='alert-history'>
                <span class='history-label'>{this.t('告警历史')} ：</span>
                <AlertTrendMiniChart
                  alertGraph={this.strategyInfo?.alert_graph}
                  timeRange={this.timeRange}
                />
              </div>
              <Button
                class='action-link'
                theme='primary'
                text
                onClick={() => this.handlePageJump('event')}
              >
                {this.t('更多')}
                <i class='icon-monitor icon-fenxiang link-icon' />
              </Button>
              <Button
                class='action-link action-link-edit'
                theme='primary'
                text
                onClick={() => this.handlePageJump('edit')}
              >
                {this.t('编辑告警策略')}
                <i class='icon-monitor icon-fenxiang link-icon' />
              </Button>
            </div>
          </div>
        )}
      </div>
    );
  },
});
