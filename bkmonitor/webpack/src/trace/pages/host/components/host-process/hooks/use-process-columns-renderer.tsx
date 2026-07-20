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

import { useI18n } from 'vue-i18n';

import {
  type IProcessColumnConfig,
  formatCpuChange,
  formatMemRss,
  getCpuBarColor,
  getCpuChangeColor,
  getFileHandleBarColor,
  getMemBarColor,
  PROCESS_PORT_STATUS_MAP,
} from '../../../constants/process';

import type { ProcessItem } from '../../../types/process';

export type ProcessColumnsRendererCtx = {
  /** 行点击回调（进程名列点击时触发） */
  onRowClick: (row: ProcessItem) => void;
};

/** 根据进程名生成 LOGO 文本（多词取各首字母，单词取前两位大写） */
const getLogoText = (name: string): string => {
  const parts = name.split(/[^a-zA-Z0-9]+/).filter(Boolean);
  if (parts.length >= 2) {
    return parts
      .slice(0, 2)
      .map(p => p[0]?.toUpperCase() ?? '')
      .join('');
  }
  return name.slice(0, 2).toUpperCase();
};

/**
 * @description 进程名列渲染（可点击触发详情）
 * @param {ProcessItem} row - 当前行进程数据
 * @returns {SlotReturnValue} 进程名列 JSX
 */
const renderNameCell = (row: ProcessItem, onClick: (row: ProcessItem) => void) => (
  <div class='process-table-name'>
    <div class='process-table-name__logo'>
      <span class='process-table-name__logo-text'>{getLogoText(row.name)}</span>
    </div>
    <div class='process-table-name__info'>
      <span
        class='process-table-name__title'
        onClick={() => onClick(row)}
      >
        {row.name || '--'}
      </span>
      {row.subtitle && <span class='process-table-name__subtitle'>{row.subtitle}</span>}
    </div>
  </div>
);

/**
 * @description 实例数列渲染
 * @param {ProcessItem} row - 当前行进程数据
 * @returns {SlotReturnValue} 实例数列 JSX
 */
const renderInstanceCountCell = (row: ProcessItem) => (
  <span class='process-table-instance'>{row.instanceCount >= 0 ? row.instanceCount : '--'}</span>
);

/**
 * @description 端口列渲染（状态圆点 + 协议/地址文本）
 * @param {ProcessItem} row - 当前行进程数据
 * @returns {SlotReturnValue} 端口列 JSX
 */
const renderPortCell = (row: ProcessItem) => {
  const config = PROCESS_PORT_STATUS_MAP[row.portStatus];
  return (
    <div class='process-table-port'>
      <span
        style={{ backgroundColor: config?.color || '#c4c6cc' }}
        class='process-table-port__dot'
      />
      <span class='process-table-port__text'>{`${row.protocol} ${row.bindIp}:${row.port}`}</span>
    </div>
  );
};

/**
 * @description 主机列渲染
 * @param {ProcessItem} row - 当前行进程数据
 * @returns {SlotReturnValue} 主机列 JSX
 */
const renderHostCell = (row: ProcessItem) => <span class='process-table-link'>{row.hostIp || '--'}</span>;

/**
 * @description CPU 占用列渲染（百分比 + 变化值 + 进度条）
 * @param {ProcessItem} row - 当前行进程数据
 * @returns {SlotReturnValue} CPU 列 JSX
 */
const renderCpuCell = (row: ProcessItem) => {
  if (!(row.cpuUsage >= 0)) {
    return <span class='process-table-cpu__empty'>--</span>;
  }
  return (
    <div class='process-table-cpu'>
      <div class='process-table-cpu__row'>
        <span class='process-table-cpu__value'>{`${row.cpuUsage}%`}</span>
        <span
          style={{ color: getCpuChangeColor(row.cpuChangeStatus) }}
          class='process-table-cpu__change'
        >
          {formatCpuChange(row.cpuChangePercent, row.cpuChangeStatus)}
        </span>
      </div>
      <div class='process-table-cpu__bar'>
        <div
          style={{
            width: `${Math.min(row.cpuUsage, 100)}%`,
            backgroundColor: getCpuBarColor(row.cpuUsage),
          }}
          class='process-table-cpu__bar-inner'
        />
      </div>
    </div>
  );
};

/**
 * @description 物理内存 RSS 列渲染（数值 + 使用率 + 进度条）
 * @param {ProcessItem} row - 当前行进程数据
 * @returns {SlotReturnValue} 内存列 JSX
 */
const renderMemoryCell = (row: ProcessItem) => {
  if (!(row.memRss > 0)) {
    return <span class='process-table-memory__empty'>--</span>;
  }
  return (
    <div class='process-table-memory'>
      <div class='process-table-memory__row'>
        <span class='process-table-memory__value'>{formatMemRss(row.memRss)}</span>
        <span class='process-table-memory__percent'>{`${row.memUsage}%`}</span>
      </div>
      <div class='process-table-memory__bar'>
        <div
          style={{
            width: `${Math.min(row.memUsage, 100)}%`,
            backgroundColor: getMemBarColor(row.cpuUsage),
          }}
          class='process-table-memory__bar-inner'
        />
      </div>
    </div>
  );
};

/**
 * @description 连接数列渲染
 * @param {ProcessItem} row - 当前行进程数据
 * @returns {SlotReturnValue} 连接数列 JSX
 */
const renderConnectionCountCell = (row: ProcessItem) => (
  <span>{row.connectionCount >= 0 ? row.connectionCount : '--'}</span>
);

/**
 * @description 文件句柄列渲染（数值 + 使用率 + 进度条）
 * @param {ProcessItem} row - 当前行进程数据
 * @returns {SlotReturnValue} 文件句柄列 JSX
 */
const renderFileHandleCell = (row: ProcessItem) => {
  if (!(row.fileHandleCount >= 0)) {
    return <span class='process-table-file-handle__empty'>--</span>;
  }
  return (
    <div class='process-table-file-handle'>
      <div class='process-table-file-handle__row'>
        <span class='process-table-file-handle__value'>{row.fileHandleCount.toLocaleString()}</span>
        <span class='process-table-file-handle__percent'>{`${row.fileHandleUsagePercent}%`}</span>
      </div>
      <div class='process-table-file-handle__bar'>
        <div
          style={{
            width: `${Math.min(row.fileHandleUsagePercent, 100)}%`,
            backgroundColor: getFileHandleBarColor(row.cpuUsage),
          }}
          class='process-table-file-handle__bar-inner'
        />
      </div>
    </div>
  );
};

/**
 * @description 运行时长列渲染
 * @param {ProcessItem} row - 当前行进程数据
 * @returns {SlotReturnValue} 运行时长列 JSX
 */
const renderUptimeCell = (row: ProcessItem) => <span>{row.uptimeRange || '--'}</span>;

/**
 * @description 进程表格列渲染器 hook，负责将列配置与各列的自定义渲染逻辑合并
 * @param {ProcessColumnsRendererCtx} rendererCtx - 渲染上下文，包含行点击等交互回调
 * @returns {{ buildColumn: (config: IProcessColumnConfig) => Record<string, unknown> }} 列构建函数
 */
export const useProcessColumnsRenderer = (rendererCtx: ProcessColumnsRendererCtx) => {
  const { t } = useI18n();

  /**
   * @description 构建某一列的 tdesign 配置
   * @param {IProcessColumnConfig} config - 列配置
   * @returns {Record<string, unknown>} tdesign 列定义对象
   */
  const buildColumn = (config: IProcessColumnConfig) => {
    const base: Record<string, unknown> = {
      colKey: config.id,
      title: t(config.name),
      minWidth: config.minWidth,
      sorter: config.sortable,
      ellipsis: config.type === 'text' || config.type === 'port',
    };
    /**
     * @description 单元格渲染函数
     * @param {unknown} _ - 单元格原始值（未使用）
     * @param {{ row: ProcessItem }} param1 - 行数据对象
     * @returns {SlotReturnValue} 单元格 JSX
     */
    base.cell = (_: unknown, { row }: { row: ProcessItem }) => {
      switch (config.type) {
        case 'name':
          return renderNameCell(row, rendererCtx.onRowClick);
        case 'instanceCount':
          return renderInstanceCountCell(row);
        case 'port':
          return renderPortCell(row);
        case 'host':
          return renderHostCell(row);
        case 'cpu':
          return renderCpuCell(row);
        case 'memory':
          return renderMemoryCell(row);
        case 'connectionCount':
          return renderConnectionCountCell(row);
        case 'fileHandle':
          return renderFileHandleCell(row);
        case 'uptime':
          return renderUptimeCell(row);
        case 'uptimeRange':
          return renderUptimeCell(row);
        default:
          return <span>{(row[config.id as keyof ProcessItem] ?? '--') as string}</span>;
      }
    };
    return base;
  };

  return { buildColumn };
};
