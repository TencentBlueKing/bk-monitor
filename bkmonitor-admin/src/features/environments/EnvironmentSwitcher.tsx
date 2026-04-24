import { useNavigate, useSearch } from '@tanstack/react-router';

import { Label } from '../../shared/components/ui/label';
import { Select } from '../../shared/components/ui/select';
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

  const handleChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    void navigate({
      to: '/datasources',
      search: createEnvironmentSearch(event.target.value, selectedTenantId)
    });
  };

  return (
    <div className="grid gap-1.5">
      <Label htmlFor="environment-switcher">环境</Label>
      <Select
        id="environment-switcher"
        value={selectedEnvironmentId}
        onChange={handleChange}
        aria-label="切换环境"
      >
        {environments.map((environment) => (
          <option value={environment.id} key={environment.id}>
            {environment.name}
          </option>
        ))}
      </Select>
    </div>
  );
}
