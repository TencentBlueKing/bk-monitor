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

import { computed, defineComponent, onBeforeUnmount, onMounted, ref } from 'vue';

import useLocale from '@/hooks/use-locale';
import ClassifyCard from '../common-comp/classify-card';

import './step1-classify.scss';

export default defineComponent({
  name: 'StepClassify',

  emits: ['width-change'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const activeKey = ref('');
    const list = [
      {
        name: '主机采集',
        value: 'host',
        children: [
          {
            name: '主机日志',
            value: 'host_log',
            icon: 'host_log',
          },
          {
            name: 'windows events 日志',
            value: 'windows_events',
            icon: 'windows',
          },
          {
            name: 'syslog 日志',
            value: 'syslog',
            icon: 'syslog',
          },
        ],
      },
      {
        name: '容器采集',
        value: 'container',
        children: [
          {
            name: '文件采集',
            value: 'file',
            icon: 'file',
          },
          {
            name: '标准输出',
            value: 'stdout',
            icon: 'IO',
          },
        ],
      },
      {
        name: '第三方日志',
        value: 'third_party',
        children: [
          {
            name: '计算平台日志接入',
            value: 'compute_platform',
            icon: 'compute_platform',
          },
          {
            name: '第三方 ES 日志接入',
            value: 'third_party_es',
            icon: 'third_party_es',
          },
          {
            name: '自定义上报日志',
            value: 'custom_report',
            icon: 'custom_report',
          },
        ],
      },
    ];
    const handleChoose = data => {
      activeKey.value = data.value;
    };
    return () => (
      <div class='operation-step1-classify'>
        <div class='classify-main'>
          {list.map(item => (
            <div
              key={item.value}
              class='classify-item'
            >
              <div class='classify-title'>{item.name}</div>
              <div class='classify-list'>
                {item.children.map(child => (
                  <ClassifyCard
                    key={child.value}
                    activeKey={activeKey.value}
                    data={child}
                    on-choose={handleChoose}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
        <div class='classify-btns'>
          <bk-button
            class='mr-8 width-88'
            theme='primary'
          >
            {t('下一步')}
          </bk-button>
          <bk-button>{t('取消')}</bk-button>
        </div>
      </div>
    );
  },
});
