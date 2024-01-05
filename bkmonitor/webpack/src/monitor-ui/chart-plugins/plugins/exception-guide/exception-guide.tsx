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
import { Component } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import bus from '../../../../monitor-common/utils/event-bus';
import { random } from '../../../../monitor-common/utils/utils';
import { ITableItem } from '../../../../monitor-pc/pages/monitor-k8s/typings';
import { PanelModel } from '../../typings';
import CommonSimpleChart from '../common-simple-chart';

import './exception-guide.scss';

interface IExceptionGuideProps {
  panel: PanelModel;
}

interface IGuideInfo {
  type: string;
  title: string;
  subTitle: string;
  link: ITableItem<'link'> | null;
}

@Component
class ExceptionGuide extends CommonSimpleChart {
  guideInfo: IGuideInfo = {
    type: '',
    title: '',
    subTitle: '',
    link: null
  };

  created() {
    this.handleSetGuide();
  }

  /** 设置指引内容 */
  handleSetGuide() {
    const data = this.panel.targets[0]?.data;
    if (data) {
      Object.assign(this.guideInfo, data);
    }
  }
  handleButton() {
    const { link } = this.guideInfo;
    if (link) {
      let urlStr = link.url;
      if (link.syncTime) {
        urlStr += urlStr.indexOf('?') === -1 ? '?' : '&';
        const { from, to } = this.$route.query;
        urlStr += `from=${from}&to${to}`;
      }

      if (link.target === 'self') {
        this.$router.push({
          path: `${window.__BK_WEWEB_DATA__?.baseroute || ''}${urlStr}`.replace(/\/\//g, '/')
        });
        return;
      }
      if (link.target === 'event') {
        bus.$emit(link.key, link);
      } else {
        window.open(urlStr, random(10));
      }
    }
  }

  render() {
    return (
      <div class='exception-guide-wrap'>
        <bk-exception type={this.guideInfo.type}>
          <span>{this.guideInfo.title}</span>
          <div class='text-wrap'>
            <pre class='text-row'>{this.guideInfo.subTitle}</pre>
            {this.guideInfo.link && (
              <bk-button
                theme='primary'
                onClick={() => this.handleButton()}
              >
                {this.guideInfo.link.value}
              </bk-button>
            )}
          </div>
        </bk-exception>
      </div>
    );
  }
}

export default ofType<IExceptionGuideProps>().convert(ExceptionGuide);
