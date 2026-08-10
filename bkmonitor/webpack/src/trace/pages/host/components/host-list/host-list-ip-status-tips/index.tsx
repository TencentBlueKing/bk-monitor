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

import type { IHostListRow } from '../../../types/host-list';

import './index.scss';

export default defineComponent({
  name: 'HostListIpStatusTips',
  props: {
    row: {
      type: Object as PropType<IHostListRow>,
      default: null,
    },
  },
  setup(props) {
    const handleToCMDB = () => {
      if (!props.row) return;
      const cmdbUrl = (window as Window & { bk_cc_url?: string }).bk_cc_url || '';
      const url = `${cmdbUrl}#/business/${window.cc_biz_id}/index/host/${props.row.bk_host_id}`;
      window.open(url);
    };

    return () => {
      if (props.row?.ignore_monitoring) {
        return (
          <div class='ip-status-tips'>
            <i18n-t keypath='不监控，就是不进行告警策略判断。可在{0}进行设置。'>
              <span
                class='link'
                onClick={handleToCMDB}
              >
                CMDB
              </span>
            </i18n-t>
          </div>
        );
      }

      if (props.row?.is_shielding) {
        return (
          <div class='ip-status-tips'>
            <i18n-t keypath='不告警，会生成告警但不进行告警通知等处理。可在{0}进行设置'>
              <span
                class='link'
                onClick={handleToCMDB}
              >
                CMDB
              </span>
            </i18n-t>
          </div>
        );
      }

      return (
        <div
          style={{ display: 'none' }}
          class='ip-status-tips'
        />
      );
    };
  },
});
