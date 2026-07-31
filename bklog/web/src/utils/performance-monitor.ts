/*
 * 性能监控工具
 * 用于记录和分析关键操作的耗时
 */

interface PerformanceMetric {
  name: string;
  startTime: number;
  endTime?: number;
  duration?: number;
  metadata?: Record<string, any>;
}

class PerformanceMonitor {
  private metrics: Map<string, PerformanceMetric> = new Map();
  private enabled: boolean = process.env.NODE_ENV === 'development' || window.localStorage.getItem('bklog_perf_monitor') === 'true';

  /**
   * 开始记录性能指标
   */
  start(name: string, metadata?: Record<string, any>): void {
    if (!this.enabled) return;

    const metric: PerformanceMetric = {
      name,
      startTime: performance.now(),
      metadata,
    };
    this.metrics.set(name, metric);
  }

  /**
   * 结束记录性能指标
   */
  end(name: string, metadata?: Record<string, any>): number | undefined {
    if (!this.enabled) return;

    const metric = this.metrics.get(name);
    if (!metric) {
      console.warn(`Performance metric "${name}" not found`);
      return;
    }

    metric.endTime = performance.now();
    metric.duration = metric.endTime - metric.startTime;
    if (metadata) {
      metric.metadata = { ...metric.metadata, ...metadata };
    }

    // 如果耗时超过阈值，输出警告
    if (metric.duration > 100) {
      console.warn(`[Performance] ${name} took ${metric.duration.toFixed(2)}ms`, metric.metadata);
    } else {
      console.log(`[Performance] ${name} took ${metric.duration.toFixed(2)}ms`, metric.metadata);
    }

    return metric.duration;
  }

  /**
   * 记录一个操作的耗时
   */
  measure<T>(name: string, fn: () => T, metadata?: Record<string, any>): T {
    if (!this.enabled) return fn();

    this.start(name, metadata);
    try {
      const result = fn();
      if (result instanceof Promise) {
        return result.then(
          (value) => {
            this.end(name, metadata);
            return value;
          },
          (error) => {
            this.end(name, { ...metadata, error: error.message });
            throw error;
          },
        ) as T;
      }
      this.end(name, metadata);
      return result;
    } catch (error) {
      this.end(name, { ...metadata, error: error.message });
      throw error;
    }
  }

  /**
   * 获取所有指标
   */
  getMetrics(): PerformanceMetric[] {
    return Array.from(this.metrics.values());
  }

  /**
   * 清除所有指标
   */
  clear(): void {
    this.metrics.clear();
  }

  /**
   * 获取特定指标的耗时
   */
  getDuration(name: string): number | undefined {
    const metric = this.metrics.get(name);
    return metric?.duration;
  }

  /**
   * 输出性能报告
   */
  report(): void {
    if (!this.enabled) return;

    const metrics = this.getMetrics();
    if (metrics.length === 0) {
      console.log('[Performance] No metrics recorded');
      return;
    }

    console.group('[Performance Report]');
    metrics.forEach((metric) => {
      if (metric.duration) {
        console.log(`${metric.name}: ${metric.duration.toFixed(2)}ms`, metric.metadata || '');
      }
    });
    const totalTime = metrics.reduce((sum, m) => sum + (m.duration || 0), 0);
    console.log(`Total: ${totalTime.toFixed(2)}ms`);
    console.groupEnd();
  }

  /**
   * 获取性能报告摘要
   */
  getSummary(): {
    totalTime: number;
    slowOperations: Array<{ name: string; duration: number; metadata?: Record<string, any> }>;
    averageTime: number;
    operationCount: number;
  } {
    const metrics = this.getMetrics().filter(m => m.duration);
    const totalTime = metrics.reduce((sum, m) => sum + (m.duration || 0), 0);
    const slowOperations = metrics
      .filter(m => m.duration && m.duration > 100)
      .map(m => ({
        name: m.name,
        duration: m.duration!,
        metadata: m.metadata,
      }))
      .sort((a, b) => b.duration - a.duration);

    return {
      totalTime,
      slowOperations,
      averageTime: metrics.length > 0 ? totalTime / metrics.length : 0,
      operationCount: metrics.length,
    };
  }
}

// 导出单例
export const performanceMonitor = new PerformanceMonitor();

// 在开发环境下，将旧版轻量性能计时器挂载到独立命名空间，方便调试。
// 注意：`window.__BKLOG_PERF_MONITOR__` 已由 IndexedDB 性能诊断服务占用，提供 enable/mark/export 等能力。
// 这里不能再覆盖该全局对象，否则会导致控制台调用 `__BKLOG_PERF_MONITOR__.enable/mark` 为 undefined。
if (process.env.NODE_ENV === 'development') {
  (window as any).__BKLOG_LEGACY_PERF_MONITOR__ = performanceMonitor;
  (window as any).__BKLOG_PERF_REPORT__ = () => performanceMonitor.report();
  (window as any).__BKLOG_PERF_SUMMARY__ = () => {
    const summary = performanceMonitor.getSummary();
    console.table(summary.slowOperations);
    console.log('Summary:', {
      totalTime: `${summary.totalTime.toFixed(2)}ms`,
      averageTime: `${summary.averageTime.toFixed(2)}ms`,
      operationCount: summary.operationCount,
    });
    return summary;
  };
}

// 导出便捷函数
export const perfStart = (name: string, metadata?: Record<string, any>) => performanceMonitor.start(name, metadata);
export const perfEnd = (name: string, metadata?: Record<string, any>) => performanceMonitor.end(name, metadata);
export const perfMeasure = <T>(name: string, fn: () => T, metadata?: Record<string, any>) =>
  performanceMonitor.measure(name, fn, metadata);
