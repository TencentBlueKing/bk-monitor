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

import { type PropType, computed, defineComponent } from 'vue';

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
    /**
     * 当前行主机在 CMDB 中的地址
     * 必须使用行内主机所属的 CMDB 业务号：关联空间入口下页面 cc_biz_id 为负空间号，CMDB 无法识别；
     * 行内业务号或主机号无效时返回空串，不提供跳转
     */
    const cmdbHostUrl = computed(() => {
      const bizId = Number(props.row?.bk_biz_id);
      const hostId = Number(props.row?.bk_host_id);
      if (!Number.isInteger(bizId) || bizId <= 0 || !Number.isInteger(hostId) || hostId <= 0) return '';
      const cmdbUrl = (window as Window & { bk_cc_url?: string }).bk_cc_url || '';
      return `${cmdbUrl}#/business/${bizId}/index/host/${hostId}`;
    });

    const handleToCMDB = () => {
      if (!cmdbHostUrl.value) return;
      window.open(cmdbHostUrl.value);
    };

    const renderCmdbLink = () => {
      if (!cmdbHostUrl.value) return <span>CMDB</span>;
      return (
        <span
          class='link'
          onClick={handleToCMDB}
        >
          CMDB
        </span>
      );
    };

    return () => {
      if (props.row?.ignore_monitoring) {
        return (
          <div class='ip-status-tips'>
            <i18n-t keypath='不监控，就是不进行告警策略判断。可在{0}进行设置。'>{renderCmdbLink()}</i18n-t>
          </div>
        );
      }

      if (props.row?.is_shielding) {
        return (
          <div class='ip-status-tips'>
            <i18n-t keypath='不告警，会生成告警但不进行告警通知等处理。可在{0}进行设置'>{renderCmdbLink()}</i18n-t>
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
