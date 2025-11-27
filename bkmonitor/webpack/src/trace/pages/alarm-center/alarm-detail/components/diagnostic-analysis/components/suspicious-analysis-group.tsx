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
import { type PropType, defineComponent, shallowRef, watch } from 'vue';

import { useI18n } from 'vue-i18n';

import type { ISuspiciousGroup } from '../typing';

import './suspicious-analysis-group.scss';
export default defineComponent({
  name: 'SuspiciousAnalysisGroup',
  props: {
    defaultExpand: {
      type: Boolean,
      default: true,
    },
    data: {
      type: Object as PropType<ISuspiciousGroup>,
    },
  },
  setup(props) {
    const { t } = useI18n();
    const expand = shallowRef(props.defaultExpand);

    const toggleExpand = () => {
      expand.value = !expand.value;
    };

    const unWatchExpand = watch(
      () => props.defaultExpand,
      val => {
        expand.value = val;
        unWatchExpand();
      }
    );

    return {
      t,
      expand,
      toggleExpand,
    };
  },
  render() {
    return (
      <div class={['suspicious-analysis-group', { expand: this.expand }]}>
        <div class='suspicious-analysis-group-wrapper'>
          <div
            class='group-header'
            onClick={this.toggleExpand}
          >
            <i class='icon-monitor icon-arrow-right arrow-icon' />
            <div
              class={['group-name', { 'link-text': !!this.data?.groupHeader.name.link }]}
              onClick={e => {
                this.data?.groupHeader.name.link && e.stopPropagation();
              }}
            >
              {this.data?.groupHeader.name.title}
              {!!this.data?.groupHeader.name.link && <i class='icon-monitor icon-fenxiang' />}
            </div>
            {this.data?.groupHeader.detail && (
              <div
                class='link-text'
                onClick={e => {
                  e.stopPropagation();
                }}
              >
                <i class='icon-monitor' />
                {this.data?.groupHeader.detail.title}
              </div>
            )}
          </div>
          {this.data?.errorInfo.length > 0 && (
            <div class='error-info'>
              {this.data?.errorInfo.map((item, index) => (
                <div
                  key={item.name}
                  class={['error-info-item', { even: index % 2 === 0 }]}
                >
                  <div class='error-info-name'>{item.name}</div>
                  <div class='error-info-value'>{item.value}</div>
                </div>
              ))}
            </div>
          )}
          {this.data?.reason && (
            <div class='suspicious-reason'>
              <div class='reason'>{this.data?.reason.content}</div>
              {this.data?.reason.link && (
                <span class='link-text'>
                  <i class='icon-monitor icon-xiangqing1' />
                  {this.t('分析详情')}
                </span>
              )}
            </div>
          )}
          {this.data?.errorContent.length > 0 && (
            <div class='error-content'>
              {this.data?.errorContent.map(item => (
                <div
                  key={item.title}
                  class='error-content-item'
                >
                  <div class='error-content-item-name'>{item.title}</div>
                  {item.value.map(value => (
                    <div
                      key={value}
                      class='error-content-item-value'
                    >
                      {value}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  },
});
