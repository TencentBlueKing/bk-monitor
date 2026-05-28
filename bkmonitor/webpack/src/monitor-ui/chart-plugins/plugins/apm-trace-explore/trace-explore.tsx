/**
 * Trace 检索容器（Vue 2 宿主）
 *
 * 在 Vue 2 + vue-tsx-support 的图表插件环境中，挂载独立的 Vue 3 子应用（monitor-trace-explore），
 * 实现「APM 等场景嵌入 Trace 检索 UI」而无需整站迁移到 Vue 3。
 *
 * 职责概要：
 * - 动态 import 子应用入口，在根 DOM 上调用 mount，并保存返回的 handle；
 * - 将父组件传入的 v3Props 作为子应用 props，深度监听变更后调用 handle.update；
 * - 销毁前 unmount，并配合 isUnmounted 避免异步 mount 完成后组件已卸载仍操作 DOM。
 *
 * 说明：子应用挂载期间会临时覆盖 window.i18n，挂载结束后恢复，避免污染宿主全局 i18n。
 */
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

interface TraceExploreContainerProps {
  v3Props?: Record<string, unknown>;
}

interface TraceExploreContainerEvents {
  onV3Event?: (event: string, ...args: unknown[]) => void;
}

@Component
export default class TraceExploreContainer extends tsc<TraceExploreContainerProps, TraceExploreContainerEvents> {
  @Prop({ type: Object, default: () => ({}) }) readonly v3Props!: Record<string, unknown>;

  private isUnmounted = false;

  created() {
    Object.defineProperty(this, '_v3handle', {
      value: null,
      writable: true,
      enumerable: false,
    });
  }

  async mounted() {
    const el = this.$refs.root as HTMLElement;
    if (!el) return;

    const savedI18n = window.i18n;
    // 本地测试使用
    // const { mount } = await import('monitor-trace-explore');
    // 线上使用
    const { mount } = await import('@blueking/monitor-trace-explore');
    window.i18n = savedI18n;

    if (this.isUnmounted) return;

    (this as any)._v3handle = mount(el, {
      props: { ...this.v3Props },
      onEvent: (event: string, ...args: unknown[]) => {
        this.$emit('v3Event', event, ...args);
      },
    });
  }

  @Watch('v3Props', { deep: true })
  onV3PropsChange(val: Record<string, unknown>) {
    (this as any)._v3handle?.update({ ...val });
  }

  beforeDestroy() {
    this.isUnmounted = true;
    (this as any)._v3handle?.unmount();
    (this as any)._v3handle = null;
  }

  render() {
    return (
      <div
        ref='root'
        style={{ height: 'calc(100vh - 142px - var(--notice-alert-height))' }}
      />
    );
  }
}
