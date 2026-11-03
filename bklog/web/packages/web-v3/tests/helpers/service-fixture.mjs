/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
/** Keep source-vs-target payload assertions on the same mocked HTTP boundary.
 * These proxies are test doubles only; production services are concrete clients. */
export function createServiceFixture(request) {
  return new Proxy({}, {
    get(_target, namespace) {
      return new Proxy({}, {
        get(_module, operation) {
          return (...args) => request(`${namespace}/${operation}`, ...args);
        },
      });
    },
  });
}
