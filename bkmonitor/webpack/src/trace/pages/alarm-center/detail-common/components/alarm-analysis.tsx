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

import { aiContent, dimensional, content } from '../mockData';
import DiagnosticAnalysis from './diagnostic-analysis';
import MarkdownView from './diagnostic-analysis/markdown-view';
import TitleBtn from './diagnostic-analysis/title-btn';

import type { IPanelItem } from '../typeing';

import './alarm-analysis.scss';
export default defineComponent({
  name: 'AlarmAnalysis',
  props: {
    id: String as PropType<string>,
    isFixed: {
      type: Boolean as PropType<boolean>,
      default: false,
    },
  },
  emits: ['close', 'fixed'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const aiConfig = aiContent;
    /** 关闭 */
    const handleClose = () => {
      emit('close');
    };
    /** 固定 */
    const handleFixed = () => {
      emit('fixed', !props.isFixed);
    };
    const renderValueList = (item: IPanelItem) => {
      return (
        <div class='dimensional-list'>
          {item.data.map(ele => (
            <span
              key={ele.key}
              class='dimensional-content-item'
            >
              <span class='item-label'>{ele.label}</span>
              <span>{ele.value}</span>
            </span>
          ))}
        </div>
      );
    };
    const list = [
      {
        name: t('可疑维度'),
        list: dimensional,
        icon: 'icon-dimension-line',
        slots: {
          default: (item: IPanelItem) => {
            return (
              <div>
                {renderValueList(item)}
                <div class='item-box'>
                  <TitleBtn
                    isPoint={true}
                    title={t('可疑原因：主调成功率 17%')}
                  />
                </div>
              </div>
            );
          },
          label: () => (
            <span>
              经过
              <span
                class='link'
                onClick={() => {}}
              >
                {t('维度下钻')}
              </span>
              分析，发现以下可疑维度（组合）：
            </span>
          ),
        },
      },
      {
        name: t('可疑调用链'),
        icon: 'icon-Tracing',
        list: dimensional.slice(0, 1),
        slots: {
          title: () => (
            <span class='dimensional-title'>
              <TitleBtn
                icon={''}
                isLinkRight={false}
                linkTxt={'dfasdfsdfg4534saldfj3l4j52345'}
                title={t('调用链：')}
              />
            </span>
          ),
          default: () => <MarkdownView content={content} />,
        },
      },
      {
        name: t('可疑日志'),
        icon: 'icon-dimension-line',
        list: dimensional.slice(0, 1),
        slots: {
          title: () => (
            <TitleBtn
              linkTxt={t('日志详情')}
              title={t('日志内容摘要：')}
            />
          ),
          default: (item: IPanelItem) => (
            <div>
              {renderValueList(item)}
              <MarkdownView content={content} />
            </div>
          ),
        },
      },
      {
        name: t('可疑事件'),
        icon: 'icon-shijianjiansuo',
        render: () => (
          <div class='panel-box'>
            <div class='panel-box-title'>
              <i class='icon-circle' />
              五一大版本发布
              <i class='icon-monitor icon-mc-goto icon-btn' />
            </div>
            <span class='item-box'>
              <TitleBtn
                isPoint={true}
                title={t('可疑原因：该时间关联的服务跟告警服务相同')}
              />
            </span>
          </div>
        ),
      },
      {
        name: t('相关性指标'),
        icon: 'icon-zhibiaojiansuo',
        list: dimensional.slice(0, 1),
        slots: {
          title: () => (
            <TitleBtn
              icon={'icon-zhibiaojiansuo'}
              linkTxt={t('指标检索')}
              title={t('指标：证书剩余天数（cert_shengyu_days）')}
            />
          ),
          default: (item: IPanelItem) => (
            <div>
              {renderValueList(item)}
              <span class='red-txt trace-txt'>{item.message}</span>
            </div>
          ),
          label: () => t('下面这些指标维度，在过去时间里产生过相似的告警事件，希望能够帮助您进一步分析告警可能原因。'),
        },
      },
    ];
    const renderAiCard = () => {
      return aiConfig.map(item => (
        <div
          key={item.key}
          class='ai-card-item'
        >
          <span class='item-title'>{item.title}：</span>
          <span class={['item-label', { link: item.label && item.link }]}>
            {item.label ? item.label : <span class='gray-txt'>{t('无')}</span>}
            {item.edit && (
              <span class='link edit'>
                <i class='icon-monitor icon-bianji edit-btn' />
                这个告警我有经验
              </span>
            )}
          </span>
        </div>
      ));
    };

    return () => (
      <div class='alarm-center-detail-alarm-analysis'>
        <DiagnosticAnalysis
          v-slots={{
            aiDefault: () => renderAiCard(),
          }}
          aiTitle={`${t('诊断概率：')}85%`}
          isFixed={props.isFixed}
          panels={list}
          onClose={handleClose}
          onFixed={handleFixed}
        />
      </div>
    );
  },
});
