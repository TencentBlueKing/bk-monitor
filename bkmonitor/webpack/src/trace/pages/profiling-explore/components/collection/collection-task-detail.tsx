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

import { Button, Sideslider } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import CollectionConfiguration from './collection-configuration';

import type { CollectionHost, CollectionTask } from '../../types/collection';

export default defineComponent({
  name: 'CollectionTaskDetail',
  props: {
    task: { type: Object as PropType<CollectionTask>, required: true },
    hosts: { type: Array as PropType<CollectionHost[]>, required: true },
    hostError: { type: String, default: '' },
    hostLoading: { type: Boolean, default: false },
    readonly: { type: Boolean, default: false },
    busy: { type: Boolean, default: false },
  },
  emits: { close: () => true, edit: () => true, history: () => true, delete: () => true, retryHosts: () => true },
  setup() {
    return { t: useI18n().t };
  },
  render() {
    const task = this.task;
    const schedule = task.schedule;
    return (
      <Sideslider
        width='min(640px, 100vw)'
        class='collection-task-detail'
        isShow={true}
        transfer={false}
        onClosed={() => this.$emit('close')}
      >
        {{
          header: () => (
            <div class='collection-detail-header'>
              <span>{this.t('定时任务详情')}</span>
              <span
                class='collection-detail-name'
                title={task.name}
              >
                {task.name}
              </span>
              <div class='collection-detail-actions'>
                <Button
                  disabled={this.readonly || this.busy}
                  theme='primary'
                  text
                  onClick={() => this.$emit('edit')}
                >
                  {this.t('编辑')}
                </Button>
                <span v-tippy={{ content: this.t('指定时间无执行记录'), onShow: () => schedule.type !== 'cron' }}>
                  <Button
                    disabled={schedule.type !== 'cron'}
                    theme='primary'
                    text
                    onClick={() => this.$emit('history')}
                  >
                    {this.t('执行记录')}
                  </Button>
                </span>
                <span
                  v-tippy={{ content: this.t('请先停用任务后再删除'), onShow: () => task.task_status !== 'disabled' }}
                >
                  <Button
                    disabled={this.readonly || this.busy || task.task_status !== 'disabled'}
                    theme='danger'
                    text
                    onClick={() => this.$emit('delete')}
                  >
                    {this.t('删除')}
                  </Button>
                </span>
              </div>
            </div>
          ),
          default: () => (
            <CollectionConfiguration
              hostError={this.hostError}
              hostLoading={this.hostLoading}
              hosts={this.hosts}
              task={task}
              onRetryHosts={() => this.$emit('retryHosts')}
            />
          ),
        }}
      </Sideslider>
    );
  },
});
