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
import { type PropType, defineComponent } from 'vue';

import { Button, Dialog } from 'bkui-vue';
import { Warn } from 'bkui-vue/lib/icon';
import { useI18n } from 'vue-i18n';

import HostPluginVersionWarning from './host-plugin-version-warning';

import type { InvalidHostGroup } from '../../types/collection';

import './host-plugin-check-dialog.scss';

/** 采集器版本校验不通过弹窗：只提示不拦截，用户可选择继续采集或重新选择主机 */
export default defineComponent({
  name: 'HostPluginCheckDialog',
  props: {
    /** 弹窗是否展示 */
    show: { type: Boolean, required: true },
    /** 版本校验不通过的主机分组 */
    groups: { type: Array as PropType<InvalidHostGroup[]>, required: true },
  },
  emits: {
    /** 校验不通过时点击「继续」，保留已选主机 */
    continue: () => true,
    /** 校验不通过时点击「重新选择」，关闭弹窗让用户重新选择主机 */
    reselect: () => true,
  },
  setup() {
    const { t } = useI18n();
    return { t };
  },
  /**
   * @description 渲染校验不通过弹窗：展示异常主机与后续操作
   * @returns 弹窗节点
   */
  render() {
    return (
      // dialogType 默认是 operation，不显式指定会渲染出多余的确定/取消底部操作栏
      <Dialog
        width={480}
        closeIcon={false}
        dialogType='show'
        escClose={false}
        headerAlign='center'
        isShow={this.show}
        quickClose={false}
      >
        {{
          header: () => (
            <div class='collection-check-dialog-header'>
              <Warn class='collection-check-dialog-icon' />
              <span class='collection-check-dialog-title'>{this.t('版本校验不通过')}</span>
            </div>
          ),
          default: () => (
            <div class='collection-check-dialog-content'>
              <HostPluginVersionWarning groups={this.groups} />
              <div class='collection-check-dialog-actions'>
                <Button
                  theme='primary'
                  onClick={() => this.$emit('continue')}
                >
                  {this.t('继续')}
                </Button>
                <Button onClick={() => this.$emit('reselect')}>{this.t('重新选择')}</Button>
              </div>
            </div>
          ),
        }}
      </Dialog>
    );
  },
});
