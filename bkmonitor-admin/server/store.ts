import type { AdminConfig, AdminEnvironment } from '../src/features/environments/schemas';

export interface EnvironmentStore {
  init(): Promise<void>;
  getConfig(): Promise<AdminConfig>;
  upsertEnvironment(environment: AdminEnvironment): Promise<AdminConfig>;
  deleteEnvironment(environmentId: string): Promise<AdminConfig>;
  setDefaultEnvironment(environmentId: string): Promise<AdminConfig>;
  close(): Promise<void>;
}

export const DEFAULT_ENVIRONMENT_SETTING_KEY = 'default_environment_id';
