import { isEn } from '@/i18n/i18n';
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
import { type CSSProperties, type PropType, defineComponent, shallowRef, Teleport } from 'vue';

import IconDiagnosisEn from 'monitor-pc/static/images/png/icon-diagnosis-en.png';
import IconDiagnosisZh from 'monitor-pc/static/images/png/icon-diagnosis-zh.png';
import { useI18n } from 'vue-i18n';

import AiDiagnosticInfoCard from './ai-diagnostic-info-card';
import AnalysisPanel from './analysis-panel';
import { DiagnosticTypeEnum } from './constant';

import type { IDiagnosticAnalysisItem } from './typing';

import './diagnostic-analysis.scss';
export default defineComponent({
  name: 'DiagnosticAnalysis',
  props: {
    /** 入口按钮样式 */
    entryBtnStyle: {
      type: Object as PropType<CSSProperties>,
      default: () => ({
        right: '8px',
        top: '44px',
      }),
    },
  },
  setup() {
    const { t } = useI18n();
    /** 是否全部展开 */
    const isAllExpand = shallowRef(true);
    /** 是否关闭 */
    const isClosed = shallowRef(false);
    /** 是否固定 */
    const isFixed = shallowRef(false);

    const analysisPanelRefs = shallowRef<InstanceType<typeof AnalysisPanel>[]>([]);

    // 设置 ref 的函数
    const setItemRef = (el, index: number) => {
      if (el) {
        analysisPanelRefs.value[index] = el;
      } else {
        analysisPanelRefs.value.splice(index, 1);
      }
    };

    const data: IDiagnosticAnalysisItem[] = [
      {
        type: DiagnosticTypeEnum.DIMENSION,
        list: [
          {
            id: '1',
            groupHeader: {
              name: {
                title: '异常维度（组合）1',
              },
            },
            errorContent: [],
            errorInfo: [
              { name: '主机名', value: 'VM-156-110-centos' },
              { name: '目标IP', value: '11.185.157.110' },
              { name: '管控区域', value: '0' },
              { name: 'Key占位', value: 'Value 占位' },
            ],
            reason: {
              content: '可疑原因：主调成功率 17%',
              link: '1231231',
            },
          },
          {
            id: '2',
            groupHeader: {
              name: {
                title: '异常维度（组合）2',
              },
            },
            errorContent: [],
            errorInfo: [
              { name: '主机名', value: 'VM-156-110-centos' },
              { name: '目标IP', value: '11.185.157.110' },
              { name: '管控区域', value: '0' },
              { name: 'Key占位', value: 'Value 占位' },
            ],
            reason: {
              content: '可疑原因：主调成功率 17%',
              link: '1231231',
            },
          },
        ],
      },
      {
        type: DiagnosticTypeEnum.LINK,
        list: [
          {
            id: '1',
            groupHeader: {
              name: {
                title: '调用链：dfasdfsdfg4534saldfj3l4j52345',
              },
            },
            errorContent: [
              {
                title: '错误情况',
                value: [
                  "tE monitor_web，incident，resources, fronted_resources. IncidentHandlersResource 这个 span 中，发生了一个类型为 TypeError 的异常。异常信息为'<' not supported between instances of 'str' and 'int'. 这表明在代表中存在一个比较操作。试图将字符串和整数进行比较，导致了类型错误。",
                ],
              },
              {
                title: '错误详情',
                value: ['异常类型：TypenError', "异常信息：'<' not supported between instances of 'str' and 'int'"],
              },
              { title: '堆栈跟踪', value: ['TraranarkImnct rarant'] },
            ],
            errorInfo: [],
          },
        ],
      },
      {
        type: DiagnosticTypeEnum.LOG,
        list: [
          {
            id: '1',
            groupHeader: {
              name: {
                title: '日志内容摘要：',
              },
              detail: {
                link: '',
                title: '日志详情',
              },
            },
            errorContent: [
              {
                title: '运维视角分析',
                value: [
                  '这条日志表明在指定时间，systemd 系统管理器启动了一个新的会话(session 723423)，并且这个会话是以 root 用户身份运行的。这是一个正常的系统操作日志，通常用于记录用户登录或系统服务的启动。',
                ],
              },
              {
                title: '研发视角分析',
                value: [
                  '从研发的角度看，这条日志显示了一个新的会话被创建，可能是由于用户登录或者某个需要 root 权限的服务启用。这本身是一个正常的操作，不需要特别的关心。',
                ],
              },
              {
                title: '结论',
                value: [
                  '这条日志记录的是一个正常的系统事件，即一个新的会话被创建并且是以 root 用户身份运行的。没有发现任何异常或错误信息。',
                ],
              },
            ],
            errorInfo: [
              { name: '服务器IP', value: '11.185.157.110' },
              { name: '时间戳', value: '17234345235（对应时间 2024年4月20日 19:22:02）' },
              { name: '主机ID', value: '603452' },
              { name: '日志路径', value: '/var/log/messages' },
              { name: '日志信息', value: 'systemd: Started Session 7345234 of user root' },
            ],
          },
        ],
      },
      {
        type: DiagnosticTypeEnum.EVENT,
        list: [
          {
            id: '1',
            groupHeader: { name: { title: '五一大版本发布', link: '123' } },
            errorInfo: [],
            errorContent: [],
            reason: {
              content: '可疑原因：该时间关联的服务跟告警服务相同',
              link: '1231231',
            },
          },
        ],
      },
    ];

    const handleAllExpandChange = () => {
      isAllExpand.value = !isAllExpand.value;
      for (const item of analysisPanelRefs.value) {
        item?.toggleExpand(isAllExpand.value);
      }
    };

    const handleFixedChange = () => {
      isFixed.value = !isFixed.value;
    };

    const handleClosedChange = (value: boolean) => {
      isClosed.value = value;
    };

    return {
      t,
      isAllExpand,
      isFixed,
      isClosed,
      data,
      setItemRef,
      handleAllExpandChange,
      handleFixedChange,
      handleClosedChange,
    };
  },
  render() {
    return (
      <Teleport
        disabled={!this.isFixed}
        to='body'
      >
        <div class={['diagnostic-analysis-panel-comp', { fixed: this.isFixed }]}>
          {this.isClosed ? (
            <div
              style={this.entryBtnStyle}
              class='diagnostic-analysis-entry-btn'
              onClick={() => {
                this.handleClosedChange(false);
              }}
            >
              <div class='btn-tag'>
                <img
                  class='text-image'
                  alt=''
                  src={isEn ? IconDiagnosisEn : IconDiagnosisZh}
                />
              </div>
            </div>
          ) : (
            <div class='diagnostic-analysis-wrapper'>
              <div class='diagnostic-analysis-wrapper-header'>
                <div class='title'>{this.t('诊断分析')}</div>
                <div class='tool-btns'>
                  <i
                    class={['icon-monitor', 'expand-icon', this.isAllExpand ? 'icon-zhankai-2' : 'icon-shouqi3']}
                    v-bk-tooltips={{
                      content: this.isAllExpand ? this.t('全部收起') : this.t('全部展开'),
                    }}
                    onClick={this.handleAllExpandChange}
                  />
                  <i
                    class={['icon-monitor', 'fixed-icon', this.isFixed ? 'icon-a-pinnedtuding' : 'icon-a-pintuding']}
                    v-bk-tooltips={{
                      content: this.isFixed ? this.t('取消固定') : this.t('固定在界面上'),
                    }}
                    onClick={this.handleFixedChange}
                  />
                  <i
                    class='icon-monitor icon-mc-close close-icon'
                    v-bk-tooltips={{
                      content: this.t('关闭'),
                    }}
                    onClick={() => {
                      this.handleClosedChange(true);
                    }}
                  />
                </div>
                <div class='bg-mask-wrap'>
                  <div class='bg-mask' />
                </div>
              </div>
              <div class='diagnostic-analysis-wrapper-content'>
                <AiDiagnosticInfoCard />

                {this.data.map((item, index) => (
                  <AnalysisPanel
                    key={item.type}
                    ref={el => this.setItemRef(el, index)}
                    data={item}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      </Teleport>
    );
  },
});
