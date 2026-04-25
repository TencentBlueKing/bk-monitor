import { useNavigate, useSearch } from '@tanstack/react-router';

import { ChoiceInput } from '../../shared/components/ChoiceInput';
import { Label } from '../../shared/components/ui/label';
import { useEnvironmentConfig } from './hooks';
import { createEnvironmentSearch, getSearchEnvironmentId, getSearchTenantId } from './search';

export function EnvironmentSwitcher() {
  const navigate = useNavigate();
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
      to: '/datasources',
      search: createEnvironmentSearch(nextEnvironmentId, selectedTenantId)
    });
  };

  return (
    <div className="grid gap-1.5">
      <Label htmlFor="environment-switcher">环境</Label>
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
