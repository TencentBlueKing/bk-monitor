// 定义懒加载任务接口
interface LazyTask {
  key: string;
  execute: (rowData: RowData) => void;
  cleanup?: (rowData: RowData) => void; // 可选的清理函数
}

// 定义行数据结构
export interface RowData {
  row: any;
  rowIndex: number;
  tasks: LazyTask[];
  isPreprocessed: boolean;
  isOutOfView: boolean;
  offsetTop: () => number;
  height: () => number;
  getDomElement: () => HTMLElement | null;
}

// 任务调度器类
class TaskScheduler {
  private taskMap: Map<number, RowData>; // Use rowIndex as the key
  private parentSelector: string | null = null;
  private scrollSelector: string | null = null;
  private buffer: number = 600; // 控制可视范围的缓冲区
  private lastVisibleStartIndex: number = 0; // 上次可视区域的起始索引
  private lastVisibleEndIndex: number = 0; // 上次可视区域的结束索引

  constructor() {
    this.taskMap = new Map();
  }

  // 设置父选择器，用于获取行元素
  public setParentSelector(selector: string): void {
    this.parentSelector = selector;
  }

  // 设置滚动容器的选择器
  public setScrollSelector(selector: string): void {
    this.scrollSelector = selector;
  }

  // 设置缓冲区大小
  public setBuffer(buffer: number): void {
    this.buffer = buffer;
  }

  // 向某行注入任务
  public injectTasks(rowIndex: number, tasks: LazyTask[] = [], row: any): void {
    const getDomElement = (): HTMLElement | null => {
      if (!this.parentSelector) {
        return null;
      }
      const parentElement = document.querySelector(this.parentSelector);
      if (parentElement) {
        return parentElement.querySelector(`[data-row-index="${rowIndex}"]`);
      }
      return null;
    };

    const rowData: RowData = {
      row,
      rowIndex,
      tasks,
      isPreprocessed: false,
      isOutOfView: false,
      offsetTop: () => getDomElement()?.offsetTop ?? 0,
      height: () => getDomElement()?.offsetHeight ?? 0,
      getDomElement,
    };
    this.taskMap.set(rowIndex, rowData);
  }

  public setTasks(rowIndex: number, tasks: LazyTask[] = []) {
    const target = this.taskMap.get(rowIndex);
    if (target) {
      tasks.forEach(task => {
        const exist = target.tasks.find(t => t.key === task.key);
        if (exist) {
          exist.execute = task.execute;
        } else {
          target.tasks.push(task);
        }
      });
    }
  }

  // 计算元素相对偏移量
  private calculateOffsetTop(): number {
    let currentElement = document.querySelector(this.parentSelector) as HTMLElement;
    const relativeTo = document.querySelector(this.scrollSelector) as HTMLElement;
    let offsetTop = 0;
    while (currentElement && currentElement !== relativeTo) {
      offsetTop += currentElement.offsetTop;
      currentElement = currentElement.offsetParent as HTMLElement;
    }
    return offsetTop;
  }

  // 更新行状态，仅更新可视区域内的行
  public updateRowStates(): void {
    if (!this.scrollSelector) {
      console.error('Scroll selector not set.');
      return;
    }

    const scrollElement = document.querySelector(this.scrollSelector) as HTMLElement;
    if (!scrollElement) {
      console.error('Scroll element not found.');
      return;
    }

    const calcTop = this.calculateOffsetTop();
    const scrollTop = scrollElement.scrollTop > calcTop ? scrollElement.scrollTop - calcTop : 0;
    const viewportHeight =
      scrollElement.clientHeight - (calcTop > scrollElement.scrollTop ? calcTop - scrollElement.scrollTop : 0);

    // 计算新的可视区域
    const newVisibleStartIndex = this.findFirstVisibleIndex(scrollTop);
    const newVisibleEndIndex = this.findLastVisibleIndex(scrollTop + viewportHeight + 200);

    // 对新进入可视区域的行进行处理
    for (let i = newVisibleStartIndex; i <= newVisibleEndIndex; i++) {
      const rowData = this.taskMap.get(i);
      if (rowData && (!rowData.isPreprocessed || rowData.isOutOfView)) {
        this.executeTasks(rowData);
        rowData.isPreprocessed = true;
        rowData.isOutOfView = false; // 重置离开可视区域标志
      }
    }

    // 对离开可视区域的行进行处理
    for (let i = this.lastVisibleStartIndex; i < newVisibleStartIndex; i++) {
      const rowData = this.taskMap.get(i);
      if (rowData && !rowData.isOutOfView) {
        this.cleanupTasks(rowData);
        rowData.isOutOfView = true;
      }
    }
    for (let i = newVisibleEndIndex + 1; i <= this.lastVisibleEndIndex; i++) {
      const rowData = this.taskMap.get(i);
      if (rowData && !rowData.isOutOfView) {
        this.cleanupTasks(rowData);
        rowData.isOutOfView = true;
      }
    }

    // 更新上次可视区域的索引
    this.lastVisibleStartIndex = newVisibleStartIndex;
    this.lastVisibleEndIndex = newVisibleEndIndex;
  }

  // 使用二分查找找到第一个可视行的索引
  private findFirstVisibleIndex(scrollTop: number): number {
    let low = 0;
    let high = this.taskMap.size - 1;
    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      const rowData = this.taskMap.get(mid);
      if (rowData && rowData.offsetTop() + rowData.height() >= scrollTop - this.buffer) {
        high = mid - 1;
      } else {
        low = mid + 1;
      }
    }
    return low;
  }

  // 使用二分查找找到最后一个可视行的索引
  private findLastVisibleIndex(scrollBottom: number): number {
    let low = 0;
    let high = this.taskMap.size - 1;
    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      const rowData = this.taskMap.get(mid);
      if (rowData && rowData.offsetTop() <= scrollBottom + this.buffer) {
        low = mid + 1;
      } else {
        high = mid - 1;
      }
    }
    return high;
  }

  // 执行行中所有任务
  private executeTasks(rowData: RowData): void {
    rowData.tasks.forEach(task => {
      try {
        requestAnimationFrame(() => {
          task.execute(rowData);
        });
      } catch (error) {
        console.error(`Error executing task ${task.key}:`, error);
      }
    });
  }

  // 清理行中所有任务
  private cleanupTasks(rowData: RowData): void {
    rowData.tasks.forEach(task => {
      if (task.cleanup) {
        try {
          task.cleanup(rowData);
        } catch (error) {
          console.error(`Error cleaning up task ${task.key}:`, error);
        }
      }
    });
  }

  // 移除某个行中的指定任务
  public removeTask(rowIndex: number, taskKey: string): void {
    const rowData = this.taskMap.get(rowIndex);
    if (rowData) {
      rowData.tasks = rowData.tasks.filter(task => task.key !== taskKey);
    }
  }

  public destroy() {
    this.taskMap.clear();
  }

  public calcRowHeight(onRowTaskCallback: (rowData: RowData) => void) {
    this.taskMap.forEach(onRowTaskCallback);
  }
}

export default TaskScheduler;

const LazyTaskScheduler = new TaskScheduler();
export { LazyTaskScheduler };
