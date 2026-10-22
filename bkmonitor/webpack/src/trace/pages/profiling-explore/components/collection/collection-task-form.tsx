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
import { type PropType, defineComponent, shallowRef, watch } from 'vue';

import { Alert, Button, DatePicker, Exception, Form, Input, Radio, Select, Sideslider, Switcher } from 'bkui-vue';
import dayjs from 'dayjs';
import { useI18n } from 'vue-i18n';

import { useCollectionForm } from '../../composables/use-collection-form';
import {
  collectionMethodLabels,
  collectionTypeLabels,
  formatCollectionTime,
  scheduleLabels,
} from '../../utils/collection';
import hostEditIcon from './assets/collection-host-edit.svg';
import hostNormalBackground from './assets/collection-host-normal-background.svg';
import hostNormalDot from './assets/collection-host-normal-dot.svg';
import CollectionCrontab from './collection-crontab';
import CollectionHostSelector from './collection-host-selector';
import CollectionProcessSelector from './collection-process-selector';

import type { CollectionMeta, CollectionTask } from '../../types/collection';

import './collection-task-form.scss';

export default defineComponent({
  name: 'CollectionTaskForm',
  props: {
    bizId: { type: Number, required: true },
    meta: { type: Object as PropType<CollectionMeta>, required: true },
    task: { type: Object as PropType<CollectionTask>, default: undefined },
    timezone: { type: String, required: true },
  },
  emits: { close: () => true, saved: (_immediate: boolean) => true },
  setup(props, { emit }) {
    const { t, locale } = useI18n();
    const form = useCollectionForm(props.meta, props.bizId, props.timezone, props.task, immediate =>
      emit('saved', immediate)
    );
    const crontab = shallowRef<InstanceType<typeof CollectionCrontab>>();
    const footerBoundary = shallowRef<HTMLElement>();
    const footerSticky = shallowRef(false);
    watch(
      footerBoundary,
      (target, _, onCleanup) => {
        if (!target) return;
        const observer = new IntersectionObserver(
          ([entry]) => {
            footerSticky.value = entry.intersectionRatio < 1;
          },
          { threshold: 1 }
        );
        observer.observe(target);
        onCleanup(() => observer.disconnect());
      },
      { flush: 'post' }
    );
    const close = () => {
      if (!form.loading.value) emit('close');
    };
    const changeDate = (key: 'endAt' | 'executeAt' | 'startAt', value: string, type: string) => {
      const date = value ? dayjs.tz(value, form.draft.value.timezone) : null;
      const selectedDate = key === 'endAt' && type === 'date' ? date?.endOf('day').millisecond(0) : date;
      form.patch({ [key]: selectedDate?.valueOf() ?? null });
    };
    return { t, locale, form, crontab, footerBoundary, footerSticky, close, changeDate };
  },
  render() {
    const f = this.form;
    const d = f.draft.value;
    const healthyHostCount = d.hosts.some(host => host.alive === undefined)
      ? '--'
      : d.hosts.filter(host => host.alive === 1).length;
    const numericField = (key: 'duration_sec' | 'frequency_hz' | 'port', suffix: string) => (
      <Input
        modelValue={d.collector[key]}
        type='number'
        onInput={value => f.patch({ collector: { ...d.collector, [key]: value === '' ? undefined : Number(value) } })}
      >
        {{ suffix: () => <span class='collection-input-suffix'>{suffix}</span> }}
      </Input>
    );
    const dateField = (key: 'endAt' | 'executeAt' | 'startAt') => (
      <DatePicker
        modelValue={d[key] ? formatCollectionTime(d[key], d.timezone) : ''}
        placeholder={this.t('请选择日期时间')}
        type='datetime'
        onChange={(value, type) => this.changeDate(key, value as string, type)}
      />
    );
    return (
      <Sideslider
        width='min(1200px, 100vw)'
        class='collection-task-form'
        beforeClose={() => !f.loading.value}
        escClose={!f.loading.value}
        isShow={true}
        quickClose={false}
        title={this.t(this.task ? '编辑任务' : '新建任务')}
        transfer={false}
        onClosed={this.close}
      >
        {{
          default: () => (
            <>
              <div class='collection-form-body'>
                <Form
                  formType='vertical'
                  model={d}
                >
                  <Form.FormItem
                    label={this.t('任务名称')}
                    required
                  >
                    <Input
                      modelValue={d.name}
                      placeholder={this.t('请输入任务名称')}
                      onInput={name => f.patch({ name })}
                    />
                  </Form.FormItem>
                  <Form.FormItem
                    label={this.t('目标主机')}
                    required
                  >
                    <div class='collection-host-selection'>
                      {d.hosts.length ? (
                        <div class='collection-host-summary'>
                          <span class='collection-host-selected'>
                            <Button
                              class='collection-host-edit'
                              aria-label={this.t('编辑主机')}
                              text
                              onClick={() => {
                                f.hostSelectorOpen.value = true;
                              }}
                            >
                              <img
                                alt=''
                                src={hostEditIcon}
                              />
                            </Button>
                            <i18n-t
                              keypath='已选择 {n} 个主机'
                              tag='span'
                              title={d.hosts.map(host => host.ip || host.ipv6 || `#${host.host_id}`).join(', ')}
                            >
                              {{ n: () => <strong>{d.hosts.length}</strong> }}
                            </i18n-t>
                          </span>
                          <span
                            class='collection-host-divider'
                            aria-hidden='true'
                          />
                          <span class='collection-host-health'>
                            <span
                              class='collection-host-status-icon'
                              aria-hidden='true'
                            >
                              <img
                                class='status-background'
                                alt=''
                                src={hostNormalBackground}
                              />
                              <img
                                class='status-dot'
                                alt=''
                                src={hostNormalDot}
                              />
                            </span>
                            <i18n-t
                              keypath='采集器正常 {n} / {total}'
                              tag='span'
                            >
                              {{
                                n: () => <strong>{healthyHostCount}</strong>,
                                total: () => d.hosts.length,
                              }}
                            </i18n-t>
                          </span>
                        </div>
                      ) : (
                        <Button
                          class='collection-host-add'
                          onClick={() => {
                            f.hostSelectorOpen.value = true;
                          }}
                        >
                          <span class='collection-host-add-inner'>
                            <i class='icon-monitor icon-a-1jiahao' />
                            {this.t('添加主机')}
                          </span>
                        </Button>
                      )}
                    </div>
                    {f.hostError.value && (
                      <div class='collection-error-text'>
                        {f.hostError.value}{' '}
                        <Button
                          theme='primary'
                          text
                          onClick={f.hydrateHosts}
                        >
                          {this.t('重试')}
                        </Button>
                      </div>
                    )}
                  </Form.FormItem>
                  <div class='collection-form-columns'>
                    <Form.FormItem
                      label={this.t('采集方式')}
                      required
                    >
                      <Select
                        clearable={false}
                        modelValue={d.method}
                        onChange={f.changeMethod}
                      >
                        {this.meta.collection_methods.map(method => (
                          <Select.Option
                            id={method}
                            key={method}
                            name={collectionMethodLabels[method]}
                          />
                        ))}
                      </Select>
                    </Form.FormItem>
                    <Form.FormItem
                      label={this.t('采集类型')}
                      required
                    >
                      <Select
                        clearable={false}
                        modelValue={d.collectionType}
                        onChange={f.changeType}
                      >
                        {this.meta.collection_types_by_method[d.method]?.map(type => (
                          <Select.Option
                            id={type}
                            key={type}
                            name={collectionTypeLabels[type]}
                          />
                        ))}
                      </Select>
                    </Form.FormItem>
                    {d.collectionType !== 'go_heap' && (
                      <Form.FormItem
                        label={this.t('采集时长')}
                        required
                      >
                        {numericField('duration_sec', this.t('秒'))}
                      </Form.FormItem>
                    )}
                  </div>
                  {d.method === 'golang' && (
                    <div class='collection-form-columns'>
                      <Form.FormItem
                        label={this.t('采集地址')}
                        required
                      >
                        <Input
                          modelValue={d.collector.ip_address}
                          onInput={ip_address => f.patch({ collector: { ...d.collector, ip_address } })}
                        />
                      </Form.FormItem>
                      <Form.FormItem
                        label={this.t('端口')}
                        required
                      >
                        {numericField('port', '')}
                      </Form.FormItem>
                    </div>
                  )}
                  {d.method === 'perf' && (
                    <div class='collection-form-columns'>
                      <Form.FormItem
                        label={this.t('采样频率')}
                        required
                      >
                        {numericField('frequency_hz', 'Hz')}
                      </Form.FormItem>
                      <Form.FormItem
                        label={this.t('栈展开方式')}
                        required
                      >
                        <Select
                          clearable={false}
                          modelValue={d.collector.stack_unwind}
                          onChange={stack_unwind => f.patch({ collector: { ...d.collector, stack_unwind } })}
                        >
                          {this.meta.stack_unwinds.map(value => (
                            <Select.Option
                              id={value}
                              key={value}
                              name={value}
                            />
                          ))}
                        </Select>
                      </Form.FormItem>
                    </div>
                  )}
                  {d.method !== 'golang' && (
                    <Form.FormItem
                      label={this.t('进程选择')}
                      required
                    >
                      {d.hosts.length ? (
                        <CollectionProcessSelector
                          form={f}
                          modes={this.meta.process_selector_types}
                        />
                      ) : (
                        <div class='collection-process-empty'>
                          <Exception
                            scene='part'
                            type='empty'
                          >
                            {this.t('请先选择目标主机')}
                          </Exception>
                        </div>
                      )}
                    </Form.FormItem>
                  )}
                  <Button
                    class='collection-advanced-button'
                    theme='primary'
                    text
                    onClick={() => {
                      f.advancedOpen.value = !f.advancedOpen.value;
                    }}
                  >
                    {f.advancedOpen.value ? '▴' : '▾'} {this.t('高级设置')}
                  </Button>
                  {f.advancedOpen.value && (
                    <Form.FormItem label={this.t('资源不足时提前终止')}>
                      <Switcher
                        modelValue={d.resourceGuard.auto_stop_on_resource_pressure}
                        onChange={auto_stop_on_resource_pressure =>
                          f.patch({ resourceGuard: { ...d.resourceGuard, auto_stop_on_resource_pressure } })
                        }
                      />
                    </Form.FormItem>
                  )}
                  <Form.FormItem
                    label={this.t('执行方式')}
                    required
                  >
                    <Radio.Group
                      modelValue={d.scheduleType}
                      onChange={scheduleType => f.patch({ scheduleType })}
                    >
                      {this.meta.schedule_types
                        .filter(type => !this.task || type !== 'immediate')
                        .map(type => (
                          <Radio
                            key={type}
                            label={type}
                          >
                            {this.t(scheduleLabels[type])}
                          </Radio>
                        ))}
                    </Radio.Group>
                  </Form.FormItem>
                  {d.scheduleType === 'immediate' && (
                    <p class='collection-muted'>
                      {this.t('立即执行仅支持 Linux 主机，提交后可在采集任务历史查看进度')}
                    </p>
                  )}
                  {d.scheduleType !== 'immediate' && (
                    <p class='collection-muted'>
                      {this.t('时区')}：{d.timezone}
                    </p>
                  )}
                  {d.scheduleType === 'once_at' && (
                    <Form.FormItem
                      label={this.t('执行时间')}
                      required
                    >
                      {dateField('executeAt')}
                    </Form.FormItem>
                  )}
                  {d.scheduleType === 'cron' && (
                    <>
                      <div class='collection-form-columns'>
                        <Form.FormItem
                          label={this.t('开始时间')}
                          required
                        >
                          {dateField('startAt')}
                        </Form.FormItem>
                        <Form.FormItem
                          label={this.t('结束时间')}
                          required
                        >
                          {dateField('endAt')}
                        </Form.FormItem>
                      </div>
                      <Form.FormItem
                        label={this.t('执行周期')}
                        required
                      >
                        <CollectionCrontab
                          ref='crontab'
                          timezone={d.timezone}
                          value={d.cron}
                          onChange={cron => f.patch({ cron })}
                        />
                      </Form.FormItem>
                    </>
                  )}
                </Form>
                {f.hostSelectorOpen.value && (
                  <CollectionHostSelector
                    hosts={d.hosts}
                    service={f.hostServices}
                    onChange={f.changeHosts}
                    onClose={() => {
                      f.hostSelectorOpen.value = false;
                    }}
                  />
                )}
              </div>
              <div class={['collection-form-footer', { 'is-sticky': this.footerSticky }]}>
                {f.error.value && (
                  <Alert
                    theme='danger'
                    title={f.error.value}
                  />
                )}
                <div>
                  <Button
                    disabled={!d.name.trim() || !d.hosts.length}
                    loading={f.loading.value}
                    theme='primary'
                    onClick={() => f.submit(() => this.crontab?.validate())}
                  >
                    {this.t('确定')}
                  </Button>
                  <Button
                    disabled={f.loading.value}
                    onClick={this.close}
                  >
                    {this.t('取消')}
                  </Button>
                </div>
              </div>
              <div
                ref='footerBoundary'
                class='collection-form-footer-boundary'
                aria-hidden='true'
              />
            </>
          ),
        }}
      </Sideslider>
    );
  },
});
