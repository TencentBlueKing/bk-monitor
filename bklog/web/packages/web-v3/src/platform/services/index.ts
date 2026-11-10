/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import type definitions from '@/app/bootstrap/service-definitions';
import { createServices, type ServiceModules } from './runtime/service-client';

export type ApplicationServices = ServiceModules<typeof definitions>;
/** The composition root installs the domain clients before application modules
 * initialize. There is no runtime dependency from transport to business code. */
export const ServicesInstance = {} as ApplicationServices;
export function installServiceModules(modules: typeof definitions): void {
  Object.assign(ServicesInstance, createServices(modules));
}
/** Components and composition functions share the same service instances. */
export function useServices(): ApplicationServices {
  return ServicesInstance;
}
