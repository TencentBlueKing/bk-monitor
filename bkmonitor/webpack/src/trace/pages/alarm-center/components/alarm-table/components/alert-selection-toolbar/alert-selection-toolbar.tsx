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
import { defineComponent, type PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import BkButton from 'bkui-vue/lib/button';

import { AlertSelectAction } from '../../../../typings/constants';

import './alert-selection-toolbar.scss';

export default defineComponent({
  name: 'AlertSelectionToolbar',
  props: {
    /** 选中行 keys */
    selectedRowKeys: {
      type: Array as PropType<(number | string)[]>,
      default: () => [],
    },
    /* 关注人则禁用操作 */
    isSelectedFollower: {
      type: Boolean,
    },
  },
  emits: {
    clickAction: (action: AlertSelectAction) => typeof action === 'string',
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    /** 当前环境是否支持一键拉群 */
    const enableCreateChatGroup = window.enable_create_chat_group || false;
    /** 所有的操作配置集合 */
    const allSelectActionsMap = {
      [AlertSelectAction.CONFIRM]: {
        id: AlertSelectAction.CONFIRM,
        label: t('批量确认'),
        prefixIcon: 'icon-check',
        onClick: () => emit('clickAction', AlertSelectAction.CONFIRM),
      },
      [AlertSelectAction.SHIELD]: {
        id: AlertSelectAction.SHIELD,
        label: t('批量屏蔽'),
        prefixIcon: 'icon-mc-notice-shield',
        onClick: () => emit('clickAction', AlertSelectAction.SHIELD),
      },
      [AlertSelectAction.DISPATCH]: {
        id: AlertSelectAction.DISPATCH,
        label: t('批量分派'),
        prefixIcon: 'icon-fenpai',
        onClick: () => emit('clickAction', AlertSelectAction.DISPATCH),
      },
      [AlertSelectAction.CHAT]: {
        id: AlertSelectAction.CHAT,
        label: t('一键拉群'),
        prefixIcon: 'icon-qiye-weixin',
        onClick: () => emit('clickAction', AlertSelectAction.CHAT),
      },
      [AlertSelectAction.CANCEL]: {
        id: AlertSelectAction.CANCEL,
        label: t('取消选择'),
        prefixIcon: 'icon-a-3yuan-bohui',
        onClick: () => emit('clickAction', AlertSelectAction.CANCEL),
      },
    };
    /** 需要渲染的操作id数组 */
    const showActionsIds = !enableCreateChatGroup
      ? [
          AlertSelectAction.CONFIRM,
          AlertSelectAction.SHIELD,
          AlertSelectAction.DISPATCH,
          AlertSelectAction.CHAT,
          AlertSelectAction.CANCEL,
        ]
      : [AlertSelectAction.CONFIRM, AlertSelectAction.SHIELD, AlertSelectAction.DISPATCH, AlertSelectAction.CANCEL];

    return { t, allSelectActionsMap, showActionsIds };
  },

  render() {
    return (
      <div class='alert-selection-toolbar'>
        <div class='alert-selection-info'>
          <span>
            <i18n-t keypath='已选择 {0} 条告警'>
              <span class='info-count'>{this.selectedRowKeys?.length || 0}</span>
            </i18n-t>
            ，
          </span>
        </div>
        <div class='alert-selection-actions'>
          {this.showActionsIds.map(actionId => (
            <BkButton
              key={actionId}
              class='action-item'
              disabled={actionId === AlertSelectAction.CHAT ? false : this.isSelectedFollower}
              text={true}
              theme='primary'
              onClick={this.allSelectActionsMap[actionId].onClick}
            >
              <i class={`icon-monitor ${this.allSelectActionsMap[actionId].prefixIcon}`} />
              <span class='action-label'>{this.allSelectActionsMap[actionId].label}</span>
            </BkButton>
          ))}
        </div>
      </div>
    );
  },
});
