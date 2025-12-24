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

import { defineComponent } from 'vue';

import useLocale from '@/hooks/use-locale';

import ClassifyCard from '../common-comp/classify-card';

import './step1-classify.scss';

export default defineComponent({
  name: 'StepClassify',
  props: {
    scenarioId: {
      type: String,
      default: 'linux',
    },
  },

  emits: ['next', 'handle', 'cancel'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const list = [
      {
        name: t('主机采集'),
        value: 'host',
        children: [
          {
            name: t('主机日志'),
            value: 'linux',
            icon: 'host_log',
          },
          {
            name: t('windows events 日志'),
            value: 'winevent',
            icon: 'windows',
          },
        ],
      },
      {
        name: t('容器采集'),
        value: 'container',
        children: [
          {
            name: t('文件采集'),
            value: 'container_file',
            icon: 'file',
          },
          {
            name: t('标准输出'),
            value: 'container_stdout',
            icon: 'IO',
          },
        ],
      },
      {
        name: t('第三方日志'),
        value: 'third_party',
        children: [
          {
            name: t('计算平台日志接入'),
            value: 'bkdata',
            icon: 'compute_platform',
          },
          {
            name: t('第三方 ES 日志接入'),
            value: 'es',
            icon: 'third_party_es',
          },
          {
            name: t('自定义上报日志'),
            value: 'custom_report',
            icon: 'custom_report',
          },
        ],
      },
    ];
    const handleChoose = (data: {name: string, value: string, icon: string}) => {
      emit('handle', 'choose', data);
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
                    activeKey={props.scenarioId}
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
            class='width-88 mr-8'
            theme='primary'
            on-click={() => {
              emit('next');
            }}
          >
            {t('下一步')}
          </bk-button>
          <bk-button
            on-click={() => {
              emit('cancel');
            }}
          >
            {t('取消')}
          </bk-button>
        </div>
      </div>
    );
  },
});
