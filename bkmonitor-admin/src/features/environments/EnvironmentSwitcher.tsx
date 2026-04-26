import { Globe } from 'lucide-react';
import { useLocation, useNavigate, useSearch } from '@tanstack/react-router';

import { ChoiceInput } from '../../shared/components/ChoiceInput';
import { Label } from '../../shared/components/ui/label';
import { useEnvironmentConfig } from './hooks';
import { createEnvironmentSearch, getSearchEnvironmentId, getSearchTenantId } from './search';

export function EnvironmentSwitcher() {
  const navigate = useNavigate();
  const location = useLocation();
  const search = useSearch({ strict: false });
  const { environments, currentEnvironment, currentTenantId, defaultEnvironmentId } =
    useEnvironmentConfig();
  const selectedEnvironmentId =
    getSearchEnvironmentId(search) ?? currentEnvironment?.id ?? defaultEnvironmentId;
  const selectedTenantId = getSearchTenantId(search) ?? currentTenantId;

  const handleChange = (value: string | string[]) => {
    const nextEnvironmentId = Array.isArray(value) ? value[0] : value;
    if (!nextEnvironmentId) return;

    void navigate({
      to: location.pathname,
      search: (prev) => ({ ...prev, env: nextEnvironmentId, tenant: selectedTenantId }),
      replace: true
    });
  };

  return (
    <div className="grid gap-1.5">
      <Label htmlFor="environment-switcher" className="flex items-center gap-1.5">
        <Globe aria-hidden="true" size={14} />
        环境
      </Label>
      <ChoiceInput
        value={selectedEnvironmentId}
        options={environments.map((environment) => ({
          label: environment.name,
          value: environment.id
        }))}
        ariaLabel="切换环境"
        onChange={handleChange}
      />
    </div>
  );
}
