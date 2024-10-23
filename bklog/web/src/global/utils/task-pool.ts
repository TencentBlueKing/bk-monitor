import {debounce} from 'lodash';

const poolList = [];
let isRunning = false;

const executePoolTask = () => {
  const task = poolList.shift();
  if (task) {
    return new Promise((resolve, reject) => {
      setTimeout(() => {
        try {
          Reflect.apply(task[0], null, task[1]);
          resolve(true);
        } catch (e) {
          reject(false);
        }
      });
    });
  }

  return Promise.reject(false);
};

const runningTask = debounce(() => {
  console.log('-----runningTask', isRunning);
  if (!isRunning) {
    isRunning = true;
    const deepRunning = () => {
      const result = executePoolTask();
      result
        ?.then(() => {
          deepRunning();
        })
        .catch(() => {
          isRunning = false;
        });
    };

    deepRunning();
  }
});

export default (task, ...args) => {
  poolList.push([task, args]);
  runningTask();
};
