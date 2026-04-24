import type { AdminConfig } from './schemas';

export function resolveDefaultEnvironmentId(config: AdminConfig): string {
  const configuredId = config.defaultEnvironmentId;

  if (configuredId && config.environments.some((environment) => environment.id === configuredId)) {
    return configuredId;
  }

  return config.environments[0]?.id ?? '';
}
