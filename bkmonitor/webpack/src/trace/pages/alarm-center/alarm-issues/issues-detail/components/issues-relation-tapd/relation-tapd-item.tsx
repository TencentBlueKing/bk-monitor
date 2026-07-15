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
import { type PropType, defineComponent } from 'vue';

import tapdLogo from 'trace/static/img/issues/tapd-logo.svg';
import { useI18n } from 'vue-i18n';

import { TapdLinkModeEnum } from '../../../issues-tapd/constant';

import type { TapdRelationItem } from '../../../services/relation-tapd';

import './relation-tapd-item.scss';

export default defineComponent({
  name: 'RelationTapdItem',
  props: {
    value: {
      type: Object as PropType<TapdRelationItem>,
      default: () => null,
    },
  },
  setup(props) {
    const { t } = useI18n();
    /** 跳转 TAPD 原始单据页面 */
    const handleGoTapd = () => {
      window.open(
        `https://tapd.woa.com/tapd_fe/${props.value?.workspace_id}/${props.value?.tapd_type}/detail/${props.value?.tapd_id}`
      );
    };
    return {
      t,
      handleGoTapd,
    };
  },
  render() {
    return (
      <div class='issues-relation-tapd-item'>
        <div class='tapd-item-left'>
          <img
            alt=''
            src={tapdLogo}
          />
        </div>
        <div class='tapd-item-right'>
          <div class='tapd-item-right-top'>
            <div class='tapd-id'>#TAPD-{this.value?.tapd_id || ''}</div>
            <div
              class='link-mode'
              v-overflow-tips
            >
              {`${this.value?.link_mode === TapdLinkModeEnum.LINK ? this.t('关联已有单据') : this.t('新建单据')}`}
            </div>
          </div>
          <div class='tapd-item-right-bottom'>
            <span
              class='tapd-name'
              v-overflow-tips
              onClick={this.handleGoTapd}
            >
              {this.value?.tapd_title || '--'}
            </span>
            <span
              class='icon-monitor icon-fenxiang'
              onClick={this.handleGoTapd}
            />

            {this.value?.sync_status ? (
              <span class='sync-status-wrap green'>
                <span class='icon-monitor icon-change' />
                <span class='sync-status'>{this.t('状态同步')}</span>
              </span>
            ) : (
              <span class='sync-status-wrap yellow'>
                <span class='split' />
                <span class='icon-monitor icon-change' />
                <span class='sync-status'>{this.t('状态不同步')}</span>
              </span>
            )}
          </div>
        </div>
      </div>
    );
  },
});
