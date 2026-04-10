/**
 * 告警中心容器（Vue 2 宿主）
 *
 * 在 Vue 2 + vue-tsx-support 的图表插件环境中，挂载独立的 Vue 3 子应用（monitor-alarm-center），
 * 实现「大屏/仪表盘等场景嵌入告警中心 UI」而无需整站迁移到 Vue 3。
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

/** 父级传给 Vue 3 告警中心子应用的透传属性（由子应用自行消费） */
interface AlarmCenterContainerProps {
  /** 传递给 Vue 3 子应用的属性 */
  v3Props?: Record<string, unknown>;
}

interface AlarmCenterContainerEvents {
  /** Vue 3 子应用向外抛出的事件 */
  onV3Event?: (event: string, ...args: unknown[]) => void;
}

@Component
export default class AlarmCenterContainer extends tsc<AlarmCenterContainerProps, AlarmCenterContainerEvents> {
  /** 透传给 monitor-alarm-center 的 props，变更时会触发子应用 update */
  @Prop({ type: Object, default: () => ({}) }) readonly v3Props!: Record<string, unknown>;

  /**
   * 标记组件是否已进入销毁流程。
   * mount 为异步：若在 import 完成前路由离开或父级销毁，需跳过 mount 及后续赋值，防止内存泄漏与异常。
   */
  private isUnmounted = false;

  /**
   * 在实例上定义非响应式、不可枚举的 _v3handle，存放子应用 mount 返回的控制句柄（update / unmount）。
   * 使用 defineProperty 避免 Vue 2 对未知字段做响应式包装，也避免出现在 devtools 枚举中。
   */
  created() {
    Object.defineProperty(this, '_v3handle', {
      value: null,
      writable: true,
      enumerable: false,
    });
  }

  /**
   * 在 ref="root" 的 div 上挂载 Vue 3 子应用。
   *
   * 执行顺序要点：
   * 1. 保存当前 window.i18n，供子应用或构建链在加载时使用；
   * 2. 动态加载 monitor-alarm-center，取出 mount；
   * 3. 立即恢复 window.i18n，缩短全局污染窗口；
   * 4. 若组件已卸载则不再 mount；
   * 5. 调用 mount(el, { props, onEvent })，onEvent 桥接到 Vue 2 的 v3Event 事件。
   */
  async mounted() {
    const el = this.$refs.root as HTMLElement;
    if (!el) return;

    const savedI18n = window.i18n;
    // 本地测试使用
    // const { mount } = await import('monitor-alarm-center');
    // 线上使用
    const { mount } = await import('@blueking/monitor-alarm-center');
    window.i18n = savedI18n;

    if (this.isUnmounted) return;

    (this as any)._v3handle = mount(el, {
      props: { ...this.v3Props },
      onEvent: (event: string, ...args: unknown[]) => {
        this.$emit('v3Event', event, ...args);
      },
    });
  }

  /**
   * v3Props 深度变化时同步到子应用（若已 mount）。
   * 子应用通过 handle.update 合并新 props，无需整页重载。
   */
  @Watch('v3Props', { deep: true })
  onV3PropsChange(val: Record<string, unknown>) {
    (this as any)._v3handle?.update({ ...val });
  }

  /**
   * Vue 2 生命周期：组件销毁前卸载子应用并清空句柄。
   * 先置 isUnmounted，使尚未完成的 mounted 异步路径在后续步骤中短路。
   */
  beforeDestroy() {
    this.isUnmounted = true;
    (this as any)._v3handle?.unmount();
    (this as any)._v3handle = null;
  }

  /** 仅提供挂载根节点；实际内容由 Vue 3 子应用渲染到该节点内 */
  render() {
    return <div ref='root' />;
  }
}
