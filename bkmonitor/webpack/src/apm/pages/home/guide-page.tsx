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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { skipToDocsLink } from 'monitor-common/utils/docs';

import AppStore from '../../store/modules/app';

import type { IAppSelectOptItem } from './app-select';
import type { IGuideLink } from './typings/app';

import './guide-page.scss';

interface IEvents {
  onCreateApp: () => void;
}
interface IProps {
  isDialogContent?: boolean;
  pluginsList: IAppSelectOptItem[]; // 插件列表
  guideUrl: IGuideLink; // 链接数据
}

interface ILinkItem {
  title: string; // 链接名
  link: string; // url
  to?: 'monitor'; // 跳转值监控
}
@Component
export default class GuidePage extends tsc<IProps, IEvents> {
  @Prop({ type: Boolean, default: false }) isDialogContent: boolean;
  @Prop({ type: Array, default: () => [] }) pluginsList: IAppSelectOptItem[];
  @Prop({ type: Object }) guideUrl: IGuideLink;

  /** 描述文案 */
  tipsList = [
    window.i18n.tc('通过拓扑图，可以了解服务之间调用的关系和出现问题的节点'),
    window.i18n.tc('通过调用次数、耗时、错误率等指标可以了解服务本身的运行状况'),
    window.i18n.tc('可以添加告警即时的发现问题'),
  ];
  /** 业务id */
  get bizId() {
    return this.$store.getters.bizId;
  }
  /** DEMO业务 */
  get demoBiz() {
    return this.$store.getters.demoBiz;
  }
  /** 快速链接 */
  get linkList(): ILinkItem[] {
    return [
      {
        title: window.i18n.tc('快速接入'),
        link: 'apmAccess',
      },
      // {
      //   title: window.i18n.tc('经典案例'),
      //   link: 'case'
      // },
      {
        title: window.i18n.tc('指标说明'),
        link: 'apmMetrics',
      },
      {
        title: window.i18n.tc('告警配置'),
        link: 'alarmConfig',
      },
    ];
  }

  @Emit('createApp')
  handleCreateApp(item: IAppSelectOptItem) {
    return item;
  }

  /**
   * 快捷链接跳转
   * @param item 链接数据
   */
  handleLinkTo(item) {
    skipToDocsLink(item.link);
  }

  /**
   * 切换demo业务
   */
  handleToDemo() {
    if (this.demoBiz?.id) {
      if (+this.$store.getters.bizId === +this.demoBiz.id) {
        location.reload();
      } else {
        /** 切换为demo业务 */
        AppStore.handleChangeBizId({
          bizId: this.demoBiz.id,
          ctx: this,
        });
      }
    }
  }

  render() {
    return (
      <div class={`guide-page-wrap ${this.isDialogContent ? 'is-guide-dialog' : ''}`}>
        <div class='guide-page-main'>
          <div class='guide-left'>
            <div class='guide-title'>{this.$t('开启应用监控')}</div>
            <ul class='guide-tips'>
              {this.tipsList.map((item, index) => (
                <li class='guide-tips-item'>
                  {index + 1}. {item}
                </li>
              ))}
            </ul>
            <div class='guide-btn-group'>
              {/* <AppSelect
                list={this.pluginsList}
                placement="bottom-start"
                class="add-btn"
                tipsPlacement="right"
                onSelected={this.handleCreateApp}/> */}
              <bk-button
                theme='primary'
                onClick={this.handleCreateApp}
              >
                {this.$t('新建应用')}
              </bk-button>
              {!!this.demoBiz && <bk-button onClick={this.handleToDemo}>DEMO</bk-button>}
            </div>
            <div class='guide-link'>
              <div class='link-title'>{this.$t('快捷链接')}</div>
              <div class='link-list'>
                {this.linkList.map(item =>
                  item.link ? (
                    <span
                      class='link-item'
                      onClick={() => this.handleLinkTo(item)}
                    >
                      {item.title}
                    </span>
                  ) : undefined
                )}
              </div>
            </div>
          </div>
          <div class='guide-right'>
            <div class='guide-img-wrap' />
          </div>
        </div>
      </div>
    );
  }
}
