type ScrollDirection = 'up' | 'down' | 'none';

class LazyTaskManager {
  private static instance: LazyTaskManager;
  tasks: Map<number, (isInBuffer: boolean, direction: ScrollDirection) => void> = new Map();
  visibleIndexes: Set<number> = new Set();
  bufferCount: number = 20;
  batchSize: number = 10;
  observer: IntersectionObserver;
  scheduledTasks: Map<number, number> = new Map();
  debounceTimeout: number | null = null;
  maxVisibleIndex: number = -Infinity;
  minVisibleIndex: number = Infinity;

  private constructor() {
    this.observer = new IntersectionObserver(this.handleIntersections.bind(this), {
      rootMargin: '200px',
    });
  }

  static getInstance() {
    if (!LazyTaskManager.instance) {
      LazyTaskManager.instance = new LazyTaskManager();
    }
    return LazyTaskManager.instance;
  }

  private handleIntersections(entries: IntersectionObserverEntry[]) {
    entries.forEach(entry => {
      const index = parseInt((entry.target as HTMLElement).dataset.index || '-1');
      if (index !== -1) {
        if (entry.isIntersecting) {
          this.visibleIndexes.add(index);
        } else {
          this.visibleIndexes.delete(index);
          const scheduledTaskId = this.scheduledTasks.get(index);
          if (scheduledTaskId !== undefined) {
            cancelAnimationFrame(scheduledTaskId);
            this.scheduledTasks.delete(index);
          }
        }
      }
    });

    // Determine the new direction based on updated visible indexes
    const visibleArray = Array.from(this.visibleIndexes);
    const newMax = Math.max(...visibleArray);
    const newMin = Math.min(...visibleArray);
    let newDirection: ScrollDirection = 'none';

    if (this.visibleIndexes.size > 0) {
      if (newMax > this.maxVisibleIndex) {
        newDirection = 'down';
      } else if (newMin < this.minVisibleIndex) {
        newDirection = 'up';
      }

      // Update the max and min visible indices
      this.maxVisibleIndex = newMax;
      this.minVisibleIndex = newMin;
    }

    if (newDirection !== 'none') {
      this.executeBufferTasks(newDirection);
    }
  }

  observeElement(element: HTMLElement, index: number) {
    element.dataset.index = index.toString();
    this.observer.observe(element);
  }

  unobserveElement(element: HTMLElement) {
    this.observer.unobserve(element);
  }

  addTask(index: number, task: (isInBuffer: boolean, direction: ScrollDirection) => void) {
    if (!this.tasks.has(index)) {
      this.tasks.set(index, task);
    }
  }

  executeBufferTasks(direction: ScrollDirection) {
    const indexes = Array.from(this.tasks.keys()).sort((a, b) => a - b);
    const visibleIndexes = Array.from(this.visibleIndexes).sort((a, b) => a - b);
    if (visibleIndexes.length === 0) return;

    const minIndex = visibleIndexes[0];
    const maxIndex = visibleIndexes[visibleIndexes.length - 1];

    let currentBatchStart = 0;

    const executeBatch = () => {
      const batchEnd = Math.min(currentBatchStart + this.batchSize, indexes.length);

      for (let i = currentBatchStart; i < batchEnd; i++) {
        const index = indexes[i];
        const isInBuffer = index >= minIndex - this.bufferCount && index <= maxIndex + this.bufferCount;

        if (!isInBuffer && this.scheduledTasks.has(index)) {
          cancelAnimationFrame(this.scheduledTasks.get(index)!);
          this.scheduledTasks.delete(index);
          continue;
        }

        const task = this.tasks.get(index);
        if (task) {
          const taskId = requestAnimationFrame(() => {
            task(isInBuffer, direction);
            this.scheduledTasks.delete(index);
          });
          this.scheduledTasks.set(index, taskId);
        }
      }

      currentBatchStart += this.batchSize;

      if (currentBatchStart < indexes.length) {
        requestAnimationFrame(executeBatch);
      }
    };

    requestAnimationFrame(executeBatch);
  }

  removeTask(index: number) {
    this.tasks.delete(index);
    const scheduledTaskId = this.scheduledTasks.get(index);
    if (scheduledTaskId !== undefined) {
      cancelAnimationFrame(scheduledTaskId);
      this.scheduledTasks.delete(index);
    }
  }
}

// 获取全局 LazyTaskManager 实例
const lazyTaskManager = LazyTaskManager.getInstance();
export default lazyTaskManager;
