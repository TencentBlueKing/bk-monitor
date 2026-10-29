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
import { type PropType, defineComponent, nextTick, shallowRef, watch } from 'vue';

import { Button, DatePicker, Exception, Form, Input, Radio, Select, Sideslider, Switcher } from 'bkui-vue';
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

import type { CollectionFieldKey, CollectionMeta, CollectionTask } from '../../types/collection';

import './collection-task-form.scss';

/**
 * @description 取下一个可用 z-index，magic-vue 计数器不可用时兜底 2000
 *
 * 主机选择弹窗（ip-selector 内置 magic-vue 弹层，transfer 到 body）的 z-index 取自 magic-vue 的全局计数器，
 * 侧栏 z-index 用同一计数器保证弹窗必然更高；只能在实例创建时取一次，若在 render 中取值，
 * 弹窗打开后的任意表单重渲染都会让侧栏 z-index 反超并重新压住弹窗
 * @returns 侧栏使用的 z-index
 */
const getNextZIndex = () =>
  (window as unknown as { __bk_zIndex_manager?: { nextZIndex?: () => number } }).__bk_zIndex_manager?.nextZIndex?.() ||
  2000;

/** 时间快捷项相对当前时间的偏移，单位为分钟 */
const TIME_SHORTCUT_OFFSET_MINUTES = [5, 10, 60];

/** 采集任务新建 / 编辑侧栏表单 */
export default defineComponent({
  name: 'CollectionTaskForm',
  props: {
    /** 业务 ID */
    bizId: { type: Number, required: true },
    /** 采集能力元信息，决定可选的方式、类型与默认配置 */
    meta: { type: Object as PropType<CollectionMeta>, required: true },
    /** 待编辑的采集任务，缺省表示新建 */
    task: { type: Object as PropType<CollectionTask>, default: undefined },
    /** 默认时区，时间选择按此时区解析并回写 */
    timezone: { type: String, required: true },
  },
  /** 对外事件：close 关闭侧栏；saved 保存成功，参数为是否立即执行 */
  emits: { close: () => true, saved: (_immediate: boolean) => true },
  setup(props, { emit }) {
    const { t, locale } = useI18n();
    /** 侧栏 z-index，实例创建时取一次，保证始终低于主机选择弹窗 */
    const sidesliderZIndex = getNextZIndex();
    const form = useCollectionForm(props.meta, props.bizId, props.timezone, props.task, immediate =>
      emit('saved', immediate)
    );
    /** 执行周期组件实例，提交前用于校验 cron 表达式 */
    const crontab = shallowRef<InstanceType<typeof CollectionCrontab>>();
    /** 表单滚动容器，用于把首条错误滚动到可视区 */
    const formBody = shallowRef<HTMLElement>();
    /** 底部操作栏下方的哨兵元素，用其可见性判断是否需要吸底 */
    const footerBoundary = shallowRef<HTMLElement>();
    /** 底部操作栏是否吸底（哨兵未完全可见时为 true） */
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
    /**
     * @description 关闭侧栏，提交加载中不允许关闭
     * @returns 无
     */
    const close = () => {
      if (!form.loading.value) emit('close');
    };
    /**
     * @description 等错误节点渲染完成后，把首条错误滚动到可视区中部
     * @returns 无
     */
    const scrollToFirstError = async () => {
      await nextTick();
      formBody.value
        ?.querySelector<HTMLElement>('[data-field-error]')
        ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    };
    /**
     * @description 把日期选择器返回的时间串转成时间戳写入草稿
     * @param key 目标字段，结束时间 / 执行时间 / 开始时间
     * @param value 日期选择器返回的时间串，空串表示清空
     * @param type 选择器变更类型，date 表示仅选日期
     * @returns 无
     */
    const changeDate = (key: 'endAt' | 'executeAt' | 'startAt', value: string, type: string) => {
      const date = value ? dayjs.tz(value, form.draft.value.timezone) : null;
      const selectedDate = key === 'endAt' && type === 'date' ? date?.endOf('day').millisecond(0) : date;
      form.patch({ [key]: selectedDate?.valueOf() ?? null });
    };
    /**
     * @description 构建时间快捷项，点击后按当前时间偏移直接写入草稿
     * 只给 onClick 不给 value：单选面板（type=datetime）下 value 返回数组会被组件再包一层导致回填异常，
     * 直接写草稿也避开了 change 事件里 type=date 时结束时间被改成当日 23:59:59 的处理
     * @param key 目标字段，结束时间 / 执行时间 / 开始时间
     * @returns 日期选择器的 shortcuts 配置
     */
    const timeShortcuts = (key: 'endAt' | 'executeAt' | 'startAt') =>
      TIME_SHORTCUT_OFFSET_MINUTES.map(minutes => ({
        text: minutes < 60 ? t('{n} 分钟后', { n: minutes }) : t('{n} 小时后', { n: minutes / 60 }),
        onClick: () => form.patch({ [key]: Date.now() + minutes * 60 * 1000 }),
      }));
    return {
      t,
      locale,
      form,
      crontab,
      formBody,
      footerBoundary,
      footerSticky,
      close,
      changeDate,
      timeShortcuts,
      scrollToFirstError,
      sidesliderZIndex,
    };
  },
  /**
   * @description 渲染侧栏表单：基础配置、采集方式相关配置、进程选择、执行方式与底部操作
   * @returns 侧栏表单节点
   */
  render() {
    const f = this.form;
    const d = f.draft.value;
    const healthyHostCount = d.hosts.some(host => host.alive === undefined)
      ? '--'
      : d.hosts.filter(host => host.alive === 1).length;
    const numericField = (key: 'duration_sec' | 'frequency_hz' | 'port', suffix?: string) => (
      <Input
        v-slots={suffix ? { suffix: () => <span class='collection-input-suffix'>{suffix}</span> } : undefined}
        min={0}
        modelValue={d.collector[key]}
        type='number'
        onUpdate:modelValue={value =>
          f.patch({ collector: { ...d.collector, [key]: value === '' ? undefined : Number(value) } })
        }
      />
    );
    const fieldError = (key: CollectionFieldKey) =>
      f.fieldErrors.value[key] ? (
        <div
          class='collection-form-item-error'
          data-field-error={key}
        >
          {f.fieldErrors.value[key]}
        </div>
      ) : null;
    /** 按任务时区判断是否早于今天，早于今天的日期不可选 */
    const todayStart = dayjs().tz(d.timezone).startOf('day');
    const dateField = (key: 'endAt' | 'executeAt' | 'startAt') => (
      <DatePicker
        disabledDate={date => dayjs(date).isBefore(todayStart.format('YYYY-MM-DD'), 'day')}
        modelValue={d[key] ? formatCollectionTime(d[key], d.timezone) : ''}
        placeholder={this.t('请选择日期时间')}
        shortcutClose={true}
        shortcuts={this.timeShortcuts(key)}
        type='datetime'
        onChange={(value, type) => this.changeDate(key, value as string, type)}
      />
    );
    return (
      <Sideslider
        width='min(1400px, 100vw)'
        class='collection-task-form'
        beforeClose={() => !f.loading.value}
        escClose={!f.loading.value}
        isShow={true}
        quickClose={false}
        title={this.t(this.task ? '编辑采集' : '新建采集')}
        transfer={false}
        zIndex={this.sidesliderZIndex}
        onClosed={this.close}
      >
        {{
          default: () => (
            <>
              <div
                ref='formBody'
                class='collection-form-body'
              >
                <Form
                  formType='vertical'
                  model={d}
                >
                  <Form.FormItem
                    label={this.t('trace-任务名称')}
                    required
                  >
                    <Input
                      modelValue={d.name}
                      placeholder={this.t('请输入任务名称')}
                      onInput={name => f.patch({ name })}
                    />
                    {fieldError('name')}
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
                    {fieldError('hosts')}
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
                      {fieldError('method')}
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
                        {fieldError('duration_sec')}
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
                        {fieldError('ip_address')}
                      </Form.FormItem>
                      <Form.FormItem
                        label={this.t('端口')}
                        required
                      >
                        {numericField('port')}
                        {fieldError('port')}
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
                        {fieldError('frequency_hz')}
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
                      {fieldError('process')}
                    </Form.FormItem>
                  )}
                  <div class='collection-advanced'>
                    <Button
                      class='collection-advanced-button'
                      theme='primary'
                      text
                      onClick={() => {
                        f.advancedOpen.value = !f.advancedOpen.value;
                      }}
                    >
                      <i class={['icon-monitor', 'icon-double-down', { 'is-open': f.advancedOpen.value }]} />{' '}
                      {this.t('高级设置')}
                    </Button>
                    {f.advancedOpen.value && (
                      <div class='collection-advanced-content'>
                        {d.method === 'perf' && (
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
                            {fieldError('stack_unwind')}
                          </Form.FormItem>
                        )}
                        <div class='collection-resource-guard'>
                          <Switcher
                            modelValue={d.resourceGuard.auto_stop_on_resource_pressure}
                            size='small'
                            theme='primary'
                            onChange={auto_stop_on_resource_pressure =>
                              f.patch({ resourceGuard: { ...d.resourceGuard, auto_stop_on_resource_pressure } })
                            }
                          />
                          <span>{this.t('资源不足时，提前终止')}</span>
                        </div>
                      </div>
                    )}
                  </div>
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
                    {fieldError('scheduleType')}
                  </Form.FormItem>
                  {d.scheduleType === 'once_at' && (
                    <Form.FormItem
                      label={this.t('执行时间')}
                      required
                    >
                      {dateField('executeAt')}
                      {fieldError('executeAt')}
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
                          {fieldError('startAt')}
                        </Form.FormItem>
                        <Form.FormItem
                          label={this.t('结束时间')}
                          required
                        >
                          {dateField('endAt')}
                          {fieldError('endAt')}
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
                        {fieldError('cron')}
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
                <div>
                  <Button
                    disabled={!d.name.trim() || !d.hosts.length}
                    loading={f.loading.value}
                    theme='primary'
                    onClick={async () => {
                      if (!(await f.submit(() => this.crontab?.validate()))) this.scrollToFirstError();
                    }}
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
