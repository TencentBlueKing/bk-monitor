import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { PropsWithChildren } from 'react';
import { useState } from 'react';

import { TooltipProvider } from '../shared/components/ui/tooltip';
import { EnvironmentProvider } from '../features/environments/EnvironmentProvider';

export function AppProviders({ children }: PropsWithChildren) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            refetchOnWindowFocus: false,
            retry: 1,
            staleTime: 30_000
          }
        }
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <EnvironmentProvider>{children}</EnvironmentProvider>
      </TooltipProvider>
    </QueryClientProvider>
  );
}
