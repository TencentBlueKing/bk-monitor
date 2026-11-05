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
import { type PropType, defineComponent, shallowRef } from 'vue';

import { type TableProps, PrimaryTable } from '@blueking/tdesign-ui';
import { Button, Input, Pagination, Radio, Switcher } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { formatCollectionTime, processKey, processLabels } from '../../utils/collection';
import CollectionSkeleton from './collection-skeleton';
import EmptyStatus from '@/components/empty-status/empty-status';

import type { CollectionForm } from '../../composables/use-collection-form';
import type { ProcessMode, ProcessRow } from '../../types/collection';

import './collection-process-selector.scss';

export default defineComponent({
  name: 'CollectionProcessSelector',
  props: {
    form: { type: Object as PropType<CollectionForm>, required: true },
    modes: { type: Array as PropType<ProcessMode[]>, required: true },
  },
  setup() {
    const { t } = useI18n();
    const collapsed = shallowRef(false);
    return { t, collapsed };
  },
  render() {
    const f = this.form;
    const d = f.draft.value;
    const p = d.process;
    const selected = f.selected.value;
    const condition = f.processCondition.value;
    const manual = f.manualSelection.value;
    const hostLabel = (row: ProcessRow) =>
      row.ip || d.hosts.find(host => host.host_id === row.bk_host_id)?.ip || `#${row.bk_host_id}`;
    const columns: TableProps['columns'] = [
      ...(manual
        ? [
            {
              colKey: 'row-select',
              type: 'multiple' as const,
              width: 40,
              checkProps: ({ row }) => ({ disabled: !!row.err_msg || !row.pid }),
            },
          ]
        : []),
      { colKey: 'ip', title: this.t('主机 IP'), width: 120, cell: (_, { row }) => hostLabel(row as ProcessRow) },
      { colKey: 'pid', title: 'PID', width: 70, cell: (_, { row }) => row.pid || '--' },
      {
        colKey: 'process_name',
        title: this.t('进程名'),
        minWidth: 100,
        ellipsis: true,
        cell: (_, { row }) => row.process_name || '--',
      },
      {
        colKey: 'command',
        title: this.t('命令行'),
        minWidth: 160,
        ellipsis: true,
        cell: (_, { row }) =>
          row.err_msg ? (
            <span class='collection-error-text'>{row.err_msg}</span>
          ) : (
            row.command || (row.pid ? '--' : this.t('未匹配到进程'))
          ),
      },
      {
        colKey: 'started_at',
        title: this.t('启动时间'),
        width: 165,
        cell: (_, { row }) => formatCollectionTime(row.started_at, d.timezone),
      },
    ];
    const values =
      condition?.type === 'pid'
        ? condition.config.pids.split(';')
        : condition?.type === 'pid_file'
          ? condition.config.pid_path.split(';')
          : [];
    const count = manual ? selected.length : f.dynamic.value ? Number(!!condition) : values.length;
    const countKey = manual
      ? '已选择 {n} 个进程'
      : f.dynamic.value
        ? '已配置 {n} 个动态下发'
        : d.processMode === 'pid'
          ? '已选择 {n} 个 PID'
          : '已选择 {n} 个 PID 文件';
    return (
      <div class={['collection-process-selector', { 'is-condition': d.processMode !== 'command' }]}>
        <div class='collection-process-query'>
          <div class='collection-process-conditions'>
            <div class='collection-process-inputs'>
              <Radio.Group
                modelValue={d.processMode}
                type='capsule'
                onChange={processMode => f.patch({ processMode })}
              >
                {this.modes.map(mode => (
                  <Radio.Button
                    key={mode}
                    label={mode}
                  >
                    {this.t(processLabels[mode])}
                  </Radio.Button>
                ))}
              </Radio.Group>
              {d.processMode === 'command' ? (
                <>
                  <Input
                    modelValue={p.matchPattern}
                    placeholder={this.t('直接字符串匹配，不支持正则，举例：/data/home/user00/word')}
                    onEnter={f.queryProcesses}
                    onInput={matchPattern => f.patchProcess({ matchPattern })}
                  >
                    {{ prefix: () => <span class='collection-input-prefix'>{this.t('包含')}</span> }}
                  </Input>
                  <Input
                    modelValue={p.excludePattern}
                    placeholder={this.t('排除匹配到的进程，支持正则，举例：/data/home/user00/word[d].+')}
                    onEnter={f.queryProcesses}
                    onInput={excludePattern => f.patchProcess({ excludePattern })}
                  >
                    {{ prefix: () => <span class='collection-input-prefix'>{this.t('排除')}</span> }}
                  </Input>
                </>
              ) : d.processMode === 'pid_file' ? (
                <Input
                  modelValue={p.pidPath}
                  placeholder={this.t('输入 PID 文件的绝对路径，多个以分号（;）分隔')}
                  onEnter={f.queryProcesses}
                  onInput={pidPath => f.patchProcess({ pidPath })}
                >
                  {{ prefix: () => <span class='collection-input-prefix'>{this.t('PID 文件')}</span> }}
                </Input>
              ) : (
                <Input
                  modelValue={p.pids}
                  placeholder={this.t('输入进程 PID，多个以分号（;）分隔')}
                  onEnter={f.queryProcesses}
                  onInput={pids => f.patchProcess({ pids })}
                >
                  {{ prefix: () => <span class='collection-input-prefix'>PID</span> }}
                </Input>
              )}
            </div>
            <Button
              class='collection-process-preview-button'
              loading={f.previewLoading.value}
              theme='primary'
              onClick={f.queryProcesses}
            >
              {this.t('预览')}
            </Button>
          </div>
          {d.processMode === 'command' && (
            <div class='collection-dynamic-toggle'>
              <Switcher
                modelValue={p.dynamic}
                theme='primary'
                onChange={dynamic => f.patchProcess({ dynamic })}
              />
              <span>{this.t('动态下发')}</span>
              <i
                class='icon-monitor icon-hint'
                v-tippy={{
                  content: this.t('开启后保存匹配条件，在每次执行时重新匹配进程，无需选择具体进程'),
                  theme: 'dark',
                }}
              />
            </div>
          )}
          <div
            class='collection-process-results'
            aria-busy={f.previewLoading.value}
          >
            {f.previewLoading.value ? (
              <CollectionSkeleton columns={[...(manual ? [40] : []), 120, 70, 100, 160, 165]} />
            ) : f.previewError.value ? (
              <EmptyStatus
                textMap={{ 500: f.previewError.value }}
                type='500'
                onOperation={f.queryProcesses}
              />
            ) : (
              <>
                <div v-tippy={{ content: this.t('已选择动态下发，无需具体选择进程'), onShow: () => f.dynamic.value }}>
                  <PrimaryTable
                    v-slots={{
                      empty: () => (
                        <EmptyStatus
                          showOperation={false}
                          textMap={{ empty: this.t('输入条件并预览进程'), 'search-empty': this.t('暂无匹配进程') }}
                          type={f.previewed.value ? 'search-empty' : 'empty'}
                        />
                      ),
                    }}
                    data={f.preview.value.data
                      .slice(
                        (f.previewPage.value - 1) * f.previewPageSize.value,
                        f.previewPage.value * f.previewPageSize.value
                      )
                      .map(row => ({ ...row, key: processKey(row) }))}
                    columns={columns}
                    rowKey='key'
                    selectedRowKeys={manual ? selected.map(processKey) : []}
                    size='small'
                    onSelectChange={f.selectPreview}
                  />
                </div>
                {!!f.preview.value.data.length && (
                  <Pagination
                    class='collection-process-pagination'
                    align='right'
                    count={f.preview.value.data.length}
                    layout={['total', 'limit', 'list']}
                    limit={f.previewPageSize.value}
                    limitList={[10, 20, 50, 100]}
                    modelValue={f.previewPage.value}
                    small
                    onChange={page => {
                      f.previewPage.value = page;
                    }}
                    onLimitChange={limit => {
                      f.previewPageSize.value = limit;
                    }}
                  />
                )}
              </>
            )}
          </div>
        </div>
        <aside class='collection-process-targets'>
          <h4>{this.t('目标进程')}</h4>
          <div class='collection-process-target-heading'>
            <Button
              class='collection-process-count'
              aria-expanded={!this.collapsed}
              text
              onClick={() => {
                this.collapsed = !this.collapsed;
              }}
            >
              <i class={['icon-monitor icon-mc-triangle-down', { 'is-collapsed': this.collapsed }]} />
              <i18n-t
                keypath={countKey}
                tag='span'
              >
                {{ n: () => <span class='collection-process-count-value'>{count}</span> }}
              </i18n-t>
            </Button>
            <Button
              class='collection-process-clear'
              aria-label={this.t('清空')}
              disabled={!count || f.previewLoading.value}
              theme='primary'
              text
              onClick={f.clearTargets}
            >
              <i class='icon-monitor icon-mc-delete-line' />
              {this.t('清空')}
            </Button>
          </div>
          {!this.collapsed &&
            (f.previewLoading.value ? (
              <CollectionSkeleton variant='targets' />
            ) : f.dynamic.value && condition?.type === 'command' ? (
              <div class='collection-process-card'>
                <div class='collection-process-card-title'>
                  {this.t('包含')}：{condition.config.match_pattern}
                </div>
                {condition.config.exclude_pattern && (
                  <div class='collection-process-card-title'>
                    {this.t('排除')}：{condition.config.exclude_pattern}
                  </div>
                )}
                <p class='collection-process-card-desc'>{this.t('命令行匹配')}</p>
                <Button
                  class='collection-process-remove'
                  aria-label={this.t('删除')}
                  text
                  onClick={f.clearTargets}
                >
                  <i class='icon-monitor icon-mc-close' />
                </Button>
              </div>
            ) : manual ? (
              selected.map(row => (
                <div
                  key={processKey(row)}
                  class='collection-process-card'
                >
                  <div class='collection-process-card-title'>PID：{row.pid}</div>
                  <p
                    class='collection-process-card-desc'
                    title={`${hostLabel(row)} / ${row.process_name || '--'}`}
                  >
                    {hostLabel(row)} / {row.process_name || '--'}
                  </p>
                  <Button
                    class='collection-process-remove'
                    aria-label={this.t('删除')}
                    text
                    onClick={() => f.selectProcesses(selected.filter(item => processKey(item) !== processKey(row)))}
                  >
                    <i class='icon-monitor icon-mc-close' />
                  </Button>
                </div>
              ))
            ) : (
              !!values.length && (
                <div class='collection-process-card collection-process-summary'>
                  <div class='collection-process-card-title'>
                    {d.processMode === 'pid_file' ? this.t('PID 文件') : 'PID'}：
                  </div>
                  <p>{values.join('; ')}</p>
                </div>
              )
            ))}
          {!count && !f.previewLoading.value && (
            <p class='collection-muted'>{this.t(manual ? '请从左侧选择目标进程' : '请在左侧输入采集条件')}</p>
          )}
        </aside>
      </div>
    );
  },
});
