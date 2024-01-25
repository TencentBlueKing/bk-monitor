/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import { defineComponent, PropType } from 'vue';
import { Button, Exception } from 'bkui-vue';

import { ITableItem } from '../../../monitor-pc/pages/monitor-k8s/typings';

import './exception-guide.scss';

export interface IGuideInfo {
  type?: string;
  title: string;
  subTitle: string;
  link: ITableItem<'link'> | null;
  icon?: string;
}

export default defineComponent({
  name: 'ExceptionGuide',
  props: {
    guideInfo: {
      type: Object as PropType<IGuideInfo>,
      required: true
    }
  },
  setup() {
    const handleButton = () => {};
    return {
      handleButton
    };
  },
  render() {
    const { guideInfo } = this.$props;
    return (
      <div class='exception-guide-wrap'>
        <Exception
          type={guideInfo.type}
          v-slots={
            guideInfo.icon
              ? {
                  type: () => (
                    <img
                      class='custom-icon'
                      src={guideInfo.icon}
                      alt=''
                    />
                  )
                }
              : null
          }
        >
          <div class='title'>{guideInfo.title}</div>
          <div class='text-wrap'>
            <pre class='text-row'>{guideInfo.subTitle}</pre>
            {guideInfo.link && (
              <Button
                theme='primary'
                onClick={() => this.handleButton()}
              >
                {guideInfo.link.value}
              </Button>
            )}
          </div>
        </Exception>
      </div>
    );
  }
});
