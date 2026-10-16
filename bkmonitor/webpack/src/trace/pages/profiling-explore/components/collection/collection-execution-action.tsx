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

import { Alert, Button, Dialog } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import type { UseCollectionExecutionReturn } from '../../composables/use-collection-execution';

export default defineComponent({
  name: 'CollectionExecutionAction',
  props: {
    controller: { type: Object as PropType<UseCollectionExecutionReturn>, required: true },
    readonly: Boolean,
  },
  setup() {
    const { t } = useI18n();
    return { t };
  },
  render() {
    const c = this.controller;
    return (
      <Dialog
        title={this.t(
          c.pending.value?.action === 'cancel'
            ? '确认终止本次采集？'
            : c.pending.value?.action === 'retry'
              ? '确认仅重试失败项？'
              : '确认重新执行？'
        )}
        beforeClose={() => !c.busy.value}
        isShow={!!c.pending.value}
        quickClose={false}
        transfer={false}
        onClosed={c.dismissAction}
      >
        {{
          default: () => (
            <>
              <p>{c.pending.value?.execution.task_name}</p>
              <p>
                {this.t(
                  c.pending.value?.action === 'cancel'
                    ? '仅终止当前执行轮次，不影响后续执行计划。'
                    : '将使用本次执行的历史配置创建一次立即采集，原有执行计划保持不变。'
                )}
              </p>
              {c.pending.value?.action === 'retry' && <p>{this.t('只重新采集失败和超时主机。')}</p>}
              {c.actionError.value && (
                <Alert
                  theme='danger'
                  title={c.actionError.value}
                />
              )}
            </>
          ),
          footer: () => (
            <div class='collection-dialog-footer'>
              <Button
                v-tippy={this.t(
                  c.pending.value?.action === 'cancel'
                    ? '确认终止本次采集'
                    : c.pending.value?.action === 'retry'
                      ? '仅重新采集失败和超时主机'
                      : '使用历史配置重新执行本次采集'
                )}
                disabled={this.readonly}
                loading={c.busy.value}
                theme='primary'
                onClick={c.confirmAction}
              >
                {this.t('确定')}
              </Button>
              <Button
                v-tippy={this.t('取消本次操作')}
                disabled={c.busy.value}
                onClick={c.dismissAction}
              >
                {this.t('取消')}
              </Button>
            </div>
          ),
        }}
      </Dialog>
    );
  },
});
