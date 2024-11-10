class LazyTaskManager {
  private static instance: LazyTaskManager;
  tasks: Map<number, (isInBuffer: boolean) => void> = new Map();
  visibleIndexes: Set<number> = new Set();
  bufferCount: number = 10;

  private constructor() {}

  static getInstance() {
    if (!LazyTaskManager.instance) {
      LazyTaskManager.instance = new LazyTaskManager();
    }
    return LazyTaskManager.instance;
  }

  addTask(index: number, task: (isInBuffer: boolean) => void) {
    if (!this.tasks.has(index)) {
      this.tasks.set(index, task);
    }
  }

  updateVisibleIndexes(index: number, isVisible: boolean) {
    if (isVisible) {
      this.visibleIndexes.add(index);
    } else {
      this.visibleIndexes.delete(index);
    }

    this.executeBufferTasks();
  }

  executeBufferTasks() {
    const indexes = Array.from(this.visibleIndexes).sort((a, b) => a - b);
    const minIndex = indexes[0];
    const maxIndex = indexes[indexes.length - 1];

    setTimeout(() => {
      this.tasks.forEach((task, index) => {
        const isInBuffer =
          index >= minIndex - this.bufferCount && index <= maxIndex + this.bufferCount;
        task(isInBuffer);
      });
    }, 100);
  }

  removeTask(index: number) {
    this.tasks.delete(index);
  }
}

// 获取全局 LazyTaskManager 实例
const lazyTaskManager = LazyTaskManager.getInstance();
export default lazyTaskManager;