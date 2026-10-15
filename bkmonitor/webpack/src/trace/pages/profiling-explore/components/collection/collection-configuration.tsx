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

import { Alert, Button } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import {
  collectionMethodLabels,
  collectionTypeLabels,
  formatCollectionTime,
  processLabels,
  scheduleLabels,
} from '../../utils/collection';
import CollectionCrontab from './collection-crontab';

import type { CollectionHost, CollectionPayload } from '../../types/collection';

export default defineComponent({
  name: 'CollectionConfiguration',
  props: {
    task: { type: Object as PropType<Omit<CollectionPayload, 'bk_biz_id'>>, required: true },
    hosts: { type: Array as PropType<CollectionHost[]>, required: true },
    hostError: { type: String, default: '' },
    hostLoading: { type: Boolean, default: false },
    snapshot: { type: Boolean, default: false },
  },
  emits: { retryHosts: () => true },
  setup() {
    return { t: useI18n().t };
  },
  render() {
    const task = this.task;
    const schedule = task.schedule;
    const selector = task.process_selector;
    const row = (label: string, value) => (
      <div class='collection-detail-row'>
        <dt>{this.t(label)}：</dt>
        <dd>{value ?? '--'}</dd>
      </div>
    );
    const time = (value: number) => formatCollectionTime(value, schedule.timezone);
    return (
      <div class='collection-detail-body'>
        <h3>{this.t('任务信息')}</h3>
        <dl>
          {row('任务名称', task.name)}
          {row(
            '目标主机',
            <>
              {this.t('共 {n} 台主机', { n: task.target_config.nodes.length })}：
              {this.hostLoading
                ? this.t('加载中...')
                : this.hosts.map(host => host.ip || host.ipv6 || `#${host.host_id}`).join('，')}
            </>
          )}
          {this.hostError && (
            <Alert
              theme='danger'
              title={this.hostError}
            >
              <Button
                theme='primary'
                text
                onClick={() => this.$emit('retryHosts')}
              >
                {this.t('重试')}
              </Button>
            </Alert>
          )}
        </dl>
        <h3>{this.t('采集配置')}</h3>
        <dl>
          {row('采集方式', collectionMethodLabels[task.collection_method])}
          {row('采集类型', collectionTypeLabels[task.collection_type])}
          {task.collector_config.duration_sec !== undefined &&
            row('采集时长', `${task.collector_config.duration_sec} ${this.t('秒')}`)}
          {task.collection_method === 'golang' && (
            <>
              {row('采集地址', task.collector_config.ip_address)}
              {row('端口', task.collector_config.port)}
            </>
          )}
          {task.collection_method === 'perf' && (
            <>
              {row(
                '采样频率',
                task.collector_config.frequency_hz === undefined ? '--' : `${task.collector_config.frequency_hz} Hz`
              )}
              {row('栈展开方式', task.collector_config.stack_unwind)}
            </>
          )}
          {selector &&
            row(
              '目标进程',
              <div class='collection-detail-processes'>
                <span class='collection-detail-tag'>{this.t(processLabels[selector.type])}</span>
                {selector.type === 'command' && (
                  <>
                    <div>
                      {this.t('包含')}：{selector.config.match_pattern}
                    </div>
                    {selector.config.exclude_pattern && (
                      <div>
                        {this.t('排除')}：{selector.config.exclude_pattern}
                      </div>
                    )}
                    {row('动态下发', this.t(selector.config.enable_dynamic_collection ? '开启' : '关闭'))}
                  </>
                )}
                {selector.type === 'pid_file' && <div>{selector.config.pid_path}</div>}
                {selector.type === 'pid' && <div>PID：{selector.config.pids}</div>}
                {selector.type === 'command' &&
                  selector.config.host_pids?.map(host => (
                    <div key={`${host.bk_host_id}:${host.pid}`}>
                      {this.hosts.find(item => item.host_id === host.bk_host_id)?.ip || `#${host.bk_host_id}`}：
                      {host.pid}
                    </div>
                  ))}
              </div>
            )}
          {row(
            '高级设置',
            <>
              {this.t('资源不足时提前终止')}：
              {this.t(task.resource_guard_config.auto_stop_on_resource_pressure ? '开启' : '关闭')}
            </>
          )}
        </dl>
        <h3>{this.t('执行计划')}</h3>
        <dl>
          {row('执行方式', this.t(scheduleLabels[schedule.type]))}
          {row('时区', schedule.timezone)}
          {schedule.type === 'cron' ? (
            <>
              {row('开始时间', time(schedule.effective_start_at))}
              {row('结束时间', time(schedule.effective_end_at))}
              {row(
                '执行周期',
                <CollectionCrontab
                  timezone={schedule.timezone}
                  value={schedule.cron_expression}
                  readonly
                />
              )}
            </>
          ) : (
            row('执行时间', time(schedule.execute_at))
          )}
          {this.snapshot && schedule.type === 'cron' && row('下次执行', '--')}
        </dl>
      </div>
    );
  },
});
