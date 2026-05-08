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

import type { NormalizedBkOTConfig } from './config';
import type { Attributes, Meter, Span, Tracer } from '@opentelemetry/api';
import type { Logger, LogRecord } from '@opentelemetry/api-logs';

export interface BkOTPlugin {
  enabled?: ((config: NormalizedBkOTConfig) => boolean) | boolean;
  name: string;
  flush?: () => Promise<void> | void;
  init: (context: BkOTRuntimeContext) => Promise<void> | void;
  shutdown?: () => Promise<void> | void;
}

export interface BkOTRuntimeContext {
  config: NormalizedBkOTConfig;
  logger: Logger;
  meter: Meter;
  tracer: Tracer;
  /** 对外提供的属性脱敏入口，所有插件在 emit 前都应过一次 */
  applyRedact: (attributes: Attributes) => Attributes;
  /** 包装 logger.emit，自动应用 redact 与 runtime attributes */
  emitLog: (record: LogRecord) => void;
  getRuntimeAttributes: () => Attributes;
  setRuntimeAttributes: (attributes: Attributes) => void;
  startSpan: (name: string, attributes?: Attributes) => Span;
}

export const isPluginEnabled = (plugin: BkOTPlugin, config: NormalizedBkOTConfig) => {
  if (typeof plugin.enabled === 'function') {
    return plugin.enabled(config);
  }
  return plugin.enabled !== false;
};

export const createPlugin = (plugin: BkOTPlugin) => plugin;

export class PluginManager {
  private readonly plugins: BkOTPlugin[];
  private startedPlugins: BkOTPlugin[] = [];

  public constructor(plugins: BkOTPlugin[]) {
    this.plugins = plugins;
  }

  public async flush() {
    // 并行 flush，避免单个慢插件拖累整体
    await Promise.all(this.startedPlugins.map(plugin => Promise.resolve().then(() => plugin.flush?.())));
  }

  public async shutdown() {
    const plugins = [...this.startedPlugins].reverse();
    for (const plugin of plugins) {
      await plugin.shutdown?.();
    }
    this.startedPlugins = [];
  }

  public async start(context: BkOTRuntimeContext) {
    try {
      for (const plugin of this.plugins) {
        if (!isPluginEnabled(plugin, context.config)) {
          continue;
        }
        await plugin.init(context);
        this.startedPlugins.push(plugin);
      }
    } catch (error) {
      await this.shutdown();
      throw error;
    }
  }
}
