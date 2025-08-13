/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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
interface ICollectConfig {
  [propName: string]: {
    // id  custom_${id} || collect_${id}
    [propName: string]: {
      activeName?: string[]; // 图表展开记录
      // 场景名
      variables?: { [propName: string]: string[] }; // 变量值输入记录
    };
  };
}

// 变量配置保存位置
const collectStorageKey = 'collectVariablesConfig';

// 保存变量值
const setCollectVariable: Function = (
  collectId: string, // 采集id 或者自定义指标id
  sceneName: string, // 场景名
  data: { active?: string[]; type: 'dashboard' | 'variables'; variables?: { id: string; value: string[] }[] }, // 存储检查视图变量或者图表分组展开记录 type:variables对应variables 'dashboard'对应active
  type = 'collect' // 区分是采集还是其他地方的检查视图
) => {
  const id = `${type}_${collectId}`;
  const collectConfig: ICollectConfig = JSON.parse(localStorage.getItem(collectStorageKey)) || {};
  if (data.type === 'variables') {
    const variablesMap = {};
    data.variables.forEach(item => {
      variablesMap[item.id] = item.value;
    });
    if (collectConfig?.[id]?.[sceneName]) {
      collectConfig[id][sceneName].variables = variablesMap;
    } else {
      if (collectConfig[id]) {
        collectConfig[id][sceneName] = {
          variables: variablesMap || {},
        };
      } else {
        collectConfig[id] = {
          [sceneName]: { variables: variablesMap },
        };
      }
    }
  }
  if (data.type === 'dashboard') {
    if (collectConfig?.[id]?.[sceneName]) {
      collectConfig[id][sceneName].activeName = data.active;
    } else {
      if (collectConfig[id]) {
        collectConfig[id][sceneName] = {
          activeName: data.active,
        };
      } else {
        collectConfig[id] = {
          [sceneName]: { activeName: data.active },
        };
      }
    }
  }
  localStorage.setItem(collectStorageKey, JSON.stringify(collectConfig));
};
// 查询变量值
const getCollectVariable: Function = (
  collectId: string, // 采集id 或者自定义指标id
  sceneName: string, // 场景名
  dataType: 'dashboard' | 'variables', // 存储检查视图变量或者图表分组展开记录
  type = 'collect' // 区分是采集还是其他地方的检查视图
) => {
  const id = `${type}_${collectId}`;
  const collectConfig: ICollectConfig = JSON.parse(localStorage.getItem(collectStorageKey));
  if (collectConfig?.[id]?.[sceneName]) {
    if (dataType === 'variables') {
      return collectConfig[id][sceneName]?.variables || {};
    }
    if (dataType === 'dashboard') {
      return collectConfig[id][sceneName]?.activeName || [];
    }
  }
};

// 删除场景
const delCollectScene: Function = (
  collectId: string, // 采集id 或者自定义指标id
  sceneName: string, // 场景名
  type = 'collect' // 区分是采集还是其他地方的检查视图
) => {
  const id = `${type}_${collectId}`;
  const collectConfig: ICollectConfig = JSON.parse(localStorage.getItem(collectStorageKey));
  if (collectConfig?.[id]?.[sceneName]) {
    delete collectConfig[id][sceneName];
  }
  localStorage.setItem(collectStorageKey, JSON.stringify(collectConfig));
};

// 根据采集id删除记录
const delCollectRecord: Function = (
  collectId: string, // 采集列表id或者自定义指标id
  type = 'collect' // 区分是采集还是其他地方的检查视图
) => {
  const id = `${type}_${collectId}`;
  const collectConfig: ICollectConfig = JSON.parse(localStorage.getItem(collectStorageKey));
  if (collectConfig?.[id]) {
    delete collectConfig[id];
  }
  localStorage.setItem(collectStorageKey, JSON.stringify(collectConfig));
};

// 根据采集列表批量删除记录
const batchDelCollectRecord: Function = (
  collectIds: string[], // 采集列表id合集
  type = 'collect' // 区分是采集还是其他地方的检查视图
) => {
  const collectIdsObj = {};
  collectIds.forEach(id => {
    collectIdsObj[String(id)] = true;
  });
  const patt = new RegExp(type);
  const ids = [];
  const collectConfig: ICollectConfig = JSON.parse(localStorage.getItem(collectStorageKey)) || {};
  Object.keys(collectConfig).forEach(key => {
    if (patt.test(String(key))) {
      ids.push(key.replace(`${type}_`, ''));
    }
  });
  ids.forEach(id => {
    if (!collectIdsObj[id]) {
      delete collectConfig[`${type}_${id}`];
    }
  });
  localStorage.setItem(collectStorageKey, JSON.stringify(collectConfig));
};

export { batchDelCollectRecord, delCollectRecord, delCollectScene, getCollectVariable, setCollectVariable };
