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

import { defineComponent } from 'vue';

import { Button, Exception } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import './issues-empty.scss';

export default defineComponent({
  name: 'IssuesEmpty',
  setup() {
    const { t } = useI18n();

    /**
     * @description 处理操作按钮点击
     * @returns {void}
     */
    const handleAction = () => {
      // TODO: 跳转逻辑代补全
      console.log('Issues-empty - handleAction - 跳转逻辑代不全');
      const actionLink = '';
      window.open(actionLink, '_blank');
      return;
    };

    return {
      t,
      handleAction,
    };
  },
  render() {
    return (
      <div class='issues-empty'>
        <Exception
          scene='part'
          type='empty'
        >
          <div class='issues-empty-content'>
            <div class='issues-empty-title'>{this.t('暂无 Issues')}</div>
            <div class='issues-empty-desc'>{this.t('请前往 iwiki 查看如何接入')}</div>
            <div class='issues-empty-action'>
              <Button
                theme='primary'
                onClick={this.handleAction}
              >
                {this.t('查看 iwiki')}
              </Button>
            </div>
          </div>
        </Exception>
      </div>
    );
  },
});
