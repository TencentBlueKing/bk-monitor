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
import Vue, { h, onMounted, ref, Ref } from 'vue';

import useLocale from '@/hooks/use-locale';

import TaskRunning from '../global/utils/task-pool';

export default ({ onSegmentEnumClick }) => {
  const { $t } = useLocale();
  const className = 'bklog-segment-pop-content';
  const wrapperClassName = 'bklog-pop-wrapper';
  const wrapperIdName = 'bklog_pop_wrapper';
  const refContent = ref();

  const eventBoxList = [
    {
      onClick: () => onSegmentEnumClick('copy'),
      iconName: 'icon bklog-icon bklog-copy',
      text: $t('复制'),
    },
    {
      onClick: () => {
        onSegmentEnumClick('is');
      },
      iconName: 'icon bk-icon icon-plus-circle',
      text: $t('添加到本次检索'),
      link: {
        tooltip: $t('新开标签页'),
        iconName: 'bklog-icon bklog-jump',
        onClick: e => {
          e.stopPropagation();
          onSegmentEnumClick('is', true);
        },
      },
    },
    {
      onClick: () => onSegmentEnumClick('not'),
      iconName: 'icon bk-icon icon-minus-circle',
      text: $t('从本次检索中排除'),
      link: {
        tooltip: $t('新开标签页'),
        iconName: 'bklog-icon bklog-jump',
        onClick: e => {
          e.stopPropagation();
          onSegmentEnumClick('not', true);
        },
      },
    },
    {
      onClick: () => onSegmentEnumClick('new-search-page-is', true),
      iconName: 'icon bk-icon icon-plus-circle',
      text: $t('新建检索'),
      link: {
        iconName: 'bklog-icon bklog-jump',
      },
    },
  ];

  const createSegmentContent = (refName: Ref) =>
    h('div', { class: 'event-icons event-tippy-content', ref: refName }, [
      eventBoxList.map(item =>
        h(
          'div',
          {
            class: 'event-box',
          },
          [
            h(
              'span',
              {
                class: 'event-btn',
                on: {
                  click: item.onClick,
                },
              },
              [
                h('i', { class: item.iconName }),
                h('span', {}, [item.text]),
                item.link
                  ? h(
                      'div',
                      {
                        class: 'new-link',
                        on: { ...(item.link.onClick ? { click: item.link.onClick } : {}) },
                        directives: item.link.tooltip
                          ? [
                              {
                                name: 'bk-tooltips',
                                value: item.link.tooltip,
                              },
                            ]
                          : [],
                      },
                      [h('i', { class: item.link.iconName })],
                    )
                  : null,
              ],
            ),
          ],
        ),
      ),
    ]);

  const mountedToBody = () => {
    let target = document.body.querySelector(`.${wrapperClassName}`);
    if (!target) {
      target = document.createElement('div');
      target.setAttribute('id', wrapperIdName);
      target.classList.add(wrapperClassName);
      document.body.appendChild(target);
    }

    if (!target.querySelector(`.${className} .event-tippy-content`)) {
      const app = new Vue({
        render: () => {
          return h('div', { class: className, style: 'display: none;' }, [createSegmentContent(refContent)]);
        },
      });
      const tempDiv = document.createElement('div');
      app.$mount(tempDiv);
      target.append(app.$el);
    }

    if (!refContent.value) {
      refContent.value = target.querySelector(`.${className} .event-tippy-content`);
    }
  };

  const getSegmentContent = () => refContent;
  onMounted(() => {
    TaskRunning(mountedToBody);
  });

  return { getSegmentContent };
};
