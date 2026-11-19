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

import { useI18n } from 'vue-i18n';

import type { InvalidHostGroup } from '../../types/collection';

import './host-plugin-version-warning.scss';

/** 采集器版本校验不通过提示内容 */
export default defineComponent({
  name: 'HostPluginVersionWarning',
  props: {
    /** 各插件及其版本不满足的主机 */
    groups: { type: Array as PropType<InvalidHostGroup[]>, required: true },
  },
  setup() {
    const { t } = useI18n();
    return { t };
  },
  /**
   * @description 渲染提示内容：插件最低版本要求（跳转节点管理）、该插件下全部不满足的主机与继续采集的后果
   * @returns 提示内容节点
   */
  render() {
    return (
      <div class='collection-plugin-version-warning'>
        {this.groups.map(group => (
          <div
            key={group.name}
            class='collection-plugin-version-plugin'
          >
            <div class='collection-plugin-version-summary'>
              <i18n-t
                keypath='以下 {n} 台主机的 {plugin}'
                tag='span'
              >
                {{
                  n: () => group.hosts.length,
                  plugin: () => (
                    <a
                      class='collection-plugin-version-link'
                      href={`${window.bk_nodeman_host || ''}#/plugin-manager/list`}
                      rel='noopener'
                      target='_blank'
                      title={this.t('前往节点管理处理')}
                    >
                      {this.t('{name} 版本低于 {version}', { name: group.name, version: group.version })}
                    </a>
                  ),
                }}
              </i18n-t>
            </div>
            {/* 不通过的主机全部展示，超出高度时可滚动 */}
            <div class='collection-plugin-version-hosts'>
              {group.hosts.map(ip => (
                <span
                  key={ip}
                  class='collection-plugin-version-host'
                >
                  {ip}
                </span>
              ))}
            </div>
          </div>
        ))}
        <div class='collection-plugin-version-question'>{this.t('可能出现采集失败或无数据上报，是否继续采集？')}</div>
      </div>
    );
  },
});
