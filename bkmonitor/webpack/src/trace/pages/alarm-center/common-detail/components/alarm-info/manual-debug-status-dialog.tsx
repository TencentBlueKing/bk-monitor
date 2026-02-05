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

import { type PropType, computed, defineComponent, shallowRef, watch } from 'vue';

import { Dialog } from 'bkui-vue';
import { getDemoActionDetail } from 'monitor-api/modules/action';
import { useI18n } from 'vue-i18n';

import type { DebugStatusData, MealInfo } from '../../../typings';

import './manual-debug-status-dialog.scss';

export default defineComponent({
  name: 'ManualDebugStatusDialog',
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    actionIds: {
      type: Array as PropType<number[]>,
      default: () => [],
    },
    mealInfo: {
      type: Object as PropType<MealInfo>,
    },
    alarmBizId: {
      type: Number,
      default: null,
    },
  },
  emits: {
    'update:show': (value: boolean) => typeof value === 'boolean',
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    // 手动处理状态轮询
    const isQueryStatus = shallowRef(false);
    const debugStatusData = shallowRef<DebugStatusData>({});

    const actionUrl = computed(() => {
      const conditions = [
        {
          key: 'action_name',
          method: 'eq',
          value: [props.mealInfo.name],
        },
      ];
      return `${location.origin}${location.pathname}${location.search}#/trace/alarm-center?conditions=${decodeURIComponent(JSON.stringify(conditions))}&filterMode=ui&alarmType=alert&from=now-24h&to=now&bizIds=-1`;
    });

    const handleShowChange = (value: boolean) => {
      emit('update:show', value);
    };

    // 轮询调试状态
    const getDebugStatus = actionIds => {
      let timer = null;

      // biome-ignore lint/suspicious/noAsyncPromiseExecutor: <explanation>
      return new Promise(async resolve => {
        if (!isQueryStatus.value) {
          resolve({});
          return;
        }
        debugStatusData.value = await getDemoActionDetail({
          bk_biz_id: props.alarmBizId,
          action_id: actionIds[0],
        })
          .then(res => (isQueryStatus.value ? res : {}))
          .catch(() => false);
        if (debugStatusData.value.is_finished || !debugStatusData.value) {
          resolve(debugStatusData.value);
        } else {
          timer = setTimeout(() => {
            clearTimeout(timer);
            if (!isQueryStatus.value) {
              resolve({});
              return;
            }
            getDebugStatus(actionIds).then(data => {
              if (!isQueryStatus.value) {
                resolve({});
                return;
              }
              debugStatusData.value = data as any;
              if (debugStatusData.value.is_finished) {
                resolve(debugStatusData.value);
              }
            });
          }, 2000);
        }
      });
    };

    watch(
      () => props.show,
      async show => {
        if (show) {
          isQueryStatus.value = true;
          debugStatusData.value = await getDebugStatus(props.actionIds);
        }
      }
    );

    const debugStatusIcon = () => {
      const loading = (
        <svg
          class='loading-svg'
          viewBox='0 0 64 64'
        >
          <g>
            <path d='M20.7,15c1.6,1.6,1.6,4.1,0,5.7s-4.1,1.6-5.7,0l-2.8-2.8c-1.6-1.6-1.6-4.1,0-5.7s4.1-1.6,5.7,0L20.7,15z' />
            <path d='M12,28c2.2,0,4,1.8,4,4s-1.8,4-4,4H8c-2.2,0-4-1.8-4-4s1.8-4,4-4H12z' />
            <path d='M15,43.3c1.6-1.6,4.1-1.6,5.7,0c1.6,1.6,1.6,4.1,0,5.7l-2.8,2.8c-1.6,1.6-4.1,1.6-5.7,0s-1.6-4.1,0-5.7L15,43.3z' />
            <path d='M28,52c0-2.2,1.8-4,4-4s4,1.8,4,4v4c0,2.2-1.8,4-4,4s-4-1.8-4-4V52z' />
            <path d='M51.8,46.1c1.6,1.6,1.6,4.1,0,5.7s-4.1,1.6-5.7,0L43.3,49c-1.6-1.6-1.6-4.1,0-5.7s4.1-1.6,5.7,0L51.8,46.1z' />
            <path d='M56,28c2.2,0,4,1.8,4,4s-1.8,4-4,4h-4c-2.2,0-4-1.8-4-4s1.8-4,4-4H56z' />
            <path d='M46.1,12.2c1.6-1.6,4.1-1.6,5.7,0s1.6,4.1,0,5.7l0,0L49,20.7c-1.6,1.6-4.1,1.6-5.7,0c-1.6-1.6-1.6-4.1,0-5.7L46.1,12.2z' />
            <path d='M28,8c0-2.2,1.8-4,4-4s4,1.8,4,4v4c0,2.2-1.8,4-4,4s-4-1.8-4-4V8z' />
          </g>
        </svg>
      );
      const statusMap = {
        received: loading,
        running: loading,
        success: (
          <div class='success'>
            <span class='icon-monitor icon-mc-check-small' />
          </div>
        ),
        failure: (
          <div class='failure'>
            <span class='icon-monitor icon-mc-close' />
          </div>
        ),
      };
      return statusMap[debugStatusData.value?.status];
    };

    const handleStopDebug = () => {
      debugStatusData.value = {};
      isQueryStatus.value = false;
    };

    const debugStatusTitle = () => {
      const statusMap = {
        received: `${t('处理中...')}...`,
        running: `${t('处理中...')}...`,
        success: t('处理成功'),
        failure: t('处理失败'),
      };
      return statusMap[debugStatusData.value?.status];
    };
    /* 以下为调试内容 */
    const debugStatusText = content => {
      if (!content) return undefined;
      const contentText = { text: '', link: '' };
      const arrContent = content?.text?.split('$');
      contentText.text = arrContent?.[0] || '';
      contentText.link = arrContent?.[1] || '';
      return (
        <div class='info-jtnr'>
          {contentText.text}
          {contentText.link ? (
            <span
              class='info-jtnr-link'
              onClick={() => content?.url && window.open(content.url)}
            >
              <span class='icon-monitor icon-copy-link' />
              {contentText.link}
            </span>
          ) : undefined}
        </div>
      );
    };
    const debugStatusOperate = () => {
      const statusMap = {
        success: (
          <div class='status-operate'>
            {/* <bk-button theme="primary" style={{ marginRight: '8px' }}>{this.$t('查看详情')}</bk-button> */}
            <bk-button onClick={() => handleStopDebug()}>{t('button-完成')}</bk-button>
          </div>
        ),
        failure: (
          <div class='status-operate'>
            <bk-button
              theme='primary'
              onClick={() => handleStopDebug()}
            >
              {t('再次处理')}
            </bk-button>
          </div>
        ),
      };
      return statusMap[debugStatusData.value?.status];
    };

    return {
      debugStatusData,
      actionUrl,
      handleShowChange,
      debugStatusIcon,
      debugStatusTitle,
      debugStatusText,
      debugStatusOperate,
    };
  },
  render() {
    return (
      <Dialog
        width={400}
        class='manual-debug-running-dialog'
        isShow={this.show}
        quick-close={false}
        renderDirective={'if'}
        onUpdate:isShow={this.handleShowChange}
      >
        <div class='status-content'>
          <div class='spinner'>{this.debugStatusIcon()}</div>
          <div class='status-title'>{this.debugStatusTitle()}</div>
          <div class='status-text'>{this.debugStatusText(this.debugStatusData?.content)}</div>
          {!['success', 'failure'].includes(this.debugStatusData?.status) && [
            <div
              key='status-tip'
              class='status-tip'
            >
              <span class='icon-monitor icon-hint' />
              <i18n
                class='text'
                path='退出当前窗口可前往{0}查看结果'
              >
                <a
                  class='link'
                  href={this.actionUrl}
                  rel='noopener noreferrer'
                  target='_blank'
                >
                  {this.$t('处理记录')}
                </a>
              </i18n>
            </div>,
            this.debugStatusOperate(),
          ]}
        </div>
      </Dialog>
    );
  },
});
