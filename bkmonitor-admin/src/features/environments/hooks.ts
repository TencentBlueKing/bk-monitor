import { useContext } from 'react';

import { EnvironmentContext } from './EnvironmentProvider';

export function useEnvironmentConfig() {
  const context = useContext(EnvironmentContext);

  if (!context) {
    throw new Error('useEnvironmentConfig must be used within EnvironmentProvider.');
  }

  return context;
}
