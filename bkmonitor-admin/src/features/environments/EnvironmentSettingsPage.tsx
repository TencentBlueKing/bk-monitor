import { Eye, EyeOff, Plus, RefreshCw, Save, Trash2 } from 'lucide-react';
import type { ReactNode } from 'react';
import { useEffect, useMemo, useState } from 'react';

import { Badge } from '../../shared/components/Badge';
import { Button } from '../../shared/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from '../../shared/components/ui/card';
import { Input } from '../../shared/components/ui/input';
import { Label } from '../../shared/components/ui/label';
import { Textarea } from '../../shared/components/ui/textarea';
import type { AdminEnvironment } from './schemas';
import { useEnvironmentConfig } from './hooks';

type EnvironmentForm = Record<keyof AdminEnvironment, string | boolean | string[]>;

export function EnvironmentSettingsPage() {
  const {
    environments,
    currentEnvironment,
    defaultEnvironmentId,
    source,
    error,
    reloadConfig,
    createEnvironment,
    saveEnvironment,
    removeEnvironment,
    setDefaultEnvironmentId
  } = useEnvironmentConfig();
  const [selectedEnvironmentId, setSelectedEnvironmentId] = useState(currentEnvironment?.id ?? '');
  const selectedEnvironment = useMemo(
    () => environments.find((environment) => environment.id === selectedEnvironmentId) ?? null,
    [environments, selectedEnvironmentId]
  );
  const [form, setForm] = useState<EnvironmentForm>(() =>
    toForm(selectedEnvironment ?? newEnvironmentTemplate())
  );
  const [secretVisible, setSecretVisible] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const isNew = !selectedEnvironment;

  useEffect(() => {
    if (!selectedEnvironmentId && currentEnvironment) {
      setSelectedEnvironmentId(currentEnvironment.id);
    }
  }, [currentEnvironment, selectedEnvironmentId]);

  useEffect(() => {
    setForm(toForm(selectedEnvironment ?? newEnvironmentTemplate()));
  }, [selectedEnvironment]);

  const updateForm = (key: keyof AdminEnvironment, value: string | boolean) => {
    setForm((previous) => ({ ...previous, [key]: value }));
  };

  const handleSave = async () => {
    const environment = fromForm(form);
    setMessage(null);

    try {
      if (isNew) {
        await createEnvironment(environment);
        setSelectedEnvironmentId(environment.id);
        setMessage(`已创建环境 ${environment.id}`);
        return;
      }

      await saveEnvironment(environment);
      setMessage(`已保存环境 ${environment.id}`);
    } catch (nextError) {
      setMessage(`保存失败：${String(nextError)}`);
    }
  };

  const handleDelete = async () => {
    if (!selectedEnvironment || environments.length <= 1) {
      return;
    }

    try {
      await removeEnvironment(selectedEnvironment.id);
      setSelectedEnvironmentId(
        environments.find((environment) => environment.id !== selectedEnvironment.id)?.id ?? ''
      );
      setMessage(`已删除环境 ${selectedEnvironment.id}`);
    } catch (nextError) {
      setMessage(`删除失败：${String(nextError)}`);
    }
  };

  const handleSetDefault = async () => {
    try {
      await setDefaultEnvironmentId(String(form.id));
      setMessage(`已设置默认环境 ${String(form.id)}`);
    } catch (nextError) {
      setMessage(`设置默认环境失败：${String(nextError)}`);
    }
  };

  return (
    <section className="page-panel">
      <div className="page-heading">
        <div>
          <div className="eyebrow">Admin Settings</div>
          <h2>环境配置</h2>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone={source === 'database' ? 'success' : 'warning'}>
            {source === 'database' ? '数据库配置' : source === 'file' ? '静态文件配置' : '默认配置'}
          </Badge>
          <Button variant="secondary" onClick={() => void reloadConfig()}>
            <RefreshCw aria-hidden="true" />
            刷新
          </Button>
        </div>
      </div>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {message ? <p className="text-sm text-emerald-700">{message}</p> : null}
      {environments.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>还没有可用环境</CardTitle>
            <CardDescription>
              先添加一个 bkmonitor 环境，再进入 DataSource 和 ResultTable 资源页面。
            </CardDescription>
          </CardHeader>
        </Card>
      ) : null}

      <div className="settings-grid">
        <Card>
          <CardHeader>
            <CardTitle>环境列表</CardTitle>
            <CardDescription>选择一个环境查看或修改 APIGW / RPC 连接信息。</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-2">
            {environments.length > 0 ? (
              environments.map((environment) => (
                <button
                  className={`environment-list-item ${environment.id === selectedEnvironmentId ? 'active' : ''}`}
                  key={environment.id}
                  onClick={() => {
                    setSelectedEnvironmentId(environment.id);
                    setMessage(null);
                  }}
                >
                  <span>
                    <strong>{environment.name}</strong>
                    <small>{environment.id}</small>
                  </span>
                  {environment.id === defaultEnvironmentId ? (
                    <Badge tone="success">默认</Badge>
                  ) : null}
                </button>
              ))
            ) : (
              <div className="empty-guide">暂无环境配置，请添加第一个环境。</div>
            )}
            <Button
              variant="outline"
              onClick={() => {
                setSelectedEnvironmentId('');
                setMessage(null);
              }}
            >
              <Plus aria-hidden="true" />
              新建环境
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{isNew ? '新建环境' : `编辑 ${selectedEnvironment.name}`}</CardTitle>
            <CardDescription>
              app_code / secret_key 会保存在 bkmonitor-admin 的配置数据库中，并由 Admin API
              在后台请求 APIGW 时使用。
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="form-grid">
              <Field label="环境 ID">
                <Input
                  value={String(form.id)}
                  disabled={!isNew}
                  onChange={(event) => updateForm('id', event.target.value)}
                />
              </Field>
              <Field label="名称">
                <Input
                  value={String(form.name)}
                  onChange={(event) => updateForm('name', event.target.value)}
                />
              </Field>
              <Field label="认证模式">
                <Input value="apigw" disabled />
              </Field>
              <Field label="APIGW / API 地址">
                <Input
                  value={String(form.apiBaseUrl)}
                  onChange={(event) => updateForm('apiBaseUrl', event.target.value)}
                />
              </Field>
              <Field label="Kernel RPC Path">
                <Input
                  value={String(form.kernelRpcPath)}
                  onChange={(event) => updateForm('kernelRpcPath', event.target.value)}
                />
              </Field>
              <Field label="app_code">
                <Input
                  value={String(form.appCode)}
                  onChange={(event) => updateForm('appCode', event.target.value)}
                />
              </Field>
              <Field label="secret_key">
                <div className="flex gap-2">
                  <Input
                    type={secretVisible ? 'text' : 'password'}
                    value={String(form.secretKey)}
                    onChange={(event) => updateForm('secretKey', event.target.value)}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={() => setSecretVisible((value) => !value)}
                    aria-label={secretVisible ? '隐藏 secret_key' : '显示 secret_key'}
                  >
                    {secretVisible ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
                  </Button>
                </div>
              </Field>
              <Field label="标签">
                <Input
                  value={String(form.tags)}
                  onChange={(event) => updateForm('tags', event.target.value)}
                  placeholder="dev, readonly"
                />
              </Field>
              <Field label="描述">
                <Textarea
                  value={String(form.description)}
                  onChange={(event) => updateForm('description', event.target.value)}
                />
              </Field>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={Boolean(form.readonly)}
                  onChange={(event) => updateForm('readonly', event.target.checked)}
                />
                只读环境
              </label>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={Boolean(form.mockFallback)}
                  onChange={(event) => updateForm('mockFallback', event.target.checked)}
                />
                RPC 失败时使用 mock fallback（仅开发演示）
              </label>
            </div>
            <div className="mt-5 flex flex-wrap gap-2">
              <Button onClick={() => void handleSave()}>
                <Save aria-hidden="true" />
                保存
              </Button>
              {!isNew ? (
                <Button
                  variant="secondary"
                  onClick={() => void handleSetDefault()}
                  disabled={String(form.id) === defaultEnvironmentId}
                >
                  设为默认
                </Button>
              ) : null}
              {!isNew ? (
                <Button
                  variant="destructive"
                  onClick={() => void handleDelete()}
                  disabled={environments.length <= 1}
                >
                  <Trash2 aria-hidden="true" />
                  删除
                </Button>
              ) : null}
            </div>
          </CardContent>
        </Card>
      </div>
    </section>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <Label>{label}</Label>
      {children}
    </div>
  );
}

function newEnvironmentTemplate(): AdminEnvironment {
  return {
    id: '',
    name: '',
    description: '',
    apiBaseUrl: 'https://bkmonitor.example.com',
    kernelRpcPath: '/app/kernel_rpc/call/',
    gatewayBaseUrl: '',
    appCode: '',
    secretKey: '',
    authMode: 'apigw',
    readonly: true,
    tags: [],
    mockFallback: false
  };
}

function toForm(environment: AdminEnvironment): EnvironmentForm {
  return {
    ...environment,
    description: environment.description ?? '',
    gatewayBaseUrl: environment.gatewayBaseUrl ?? '',
    appCode: environment.appCode ?? '',
    secretKey: environment.secretKey ?? '',
    tags: environment.tags.join(', ')
  };
}

function fromForm(form: EnvironmentForm): AdminEnvironment {
  const environment: AdminEnvironment = {
    id: String(form.id).trim(),
    name: String(form.name).trim(),
    apiBaseUrl: String(form.apiBaseUrl).trim(),
    kernelRpcPath: String(form.kernelRpcPath).trim(),
    authMode: 'apigw',
    readonly: Boolean(form.readonly),
    tags: String(form.tags)
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean),
    mockFallback: Boolean(form.mockFallback)
  };

  setOptional(environment, 'description', String(form.description));
  setOptional(environment, 'gatewayBaseUrl', String(form.gatewayBaseUrl));
  setOptional(environment, 'appCode', String(form.appCode));
  setOptional(environment, 'secretKey', String(form.secretKey));

  return environment;
}

function setOptional<T extends keyof AdminEnvironment>(
  environment: AdminEnvironment,
  key: T,
  value: string
) {
  const trimmed = value.trim();

  if (trimmed) {
    Object.assign(environment, { [key]: trimmed });
  }
}
