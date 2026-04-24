import { existsSync, readFileSync, writeFileSync } from 'node:fs';

import initSqlJs, { type Database as SqlJsDatabase, type SqlValue } from 'sql.js';

import {
  adminEnvironmentSchema,
  type AdminConfig,
  type AdminEnvironment
} from '../../src/features/environments/schemas';
import { DEFAULT_ENVIRONMENT_SETTING_KEY, type EnvironmentStore } from '../store';

export class SqliteEnvironmentStore implements EnvironmentStore {
  private db: SqlJsDatabase | null = null;

  constructor(private readonly path: string) {}

  async init(): Promise<void> {
    const SQL = await initSqlJs();
    this.db = existsSync(this.path)
      ? new SQL.Database(readFileSync(this.path))
      : new SQL.Database();

    this.database.exec(`
      CREATE TABLE IF NOT EXISTS admin_environments (
        id TEXT PRIMARY KEY,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );

      CREATE TABLE IF NOT EXISTS admin_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );
    `);

    this.persist();
  }

  getConfig(): Promise<AdminConfig> {
    const rows = this.selectAll<{ payload: string }>(
      'SELECT payload FROM admin_environments ORDER BY id ASC'
    );
    const environments = rows.map((row) => adminEnvironmentSchema.parse(JSON.parse(row.payload)));
    const defaultEnvironmentId = this.getDefaultEnvironmentId(environments);

    return Promise.resolve({ environments, defaultEnvironmentId });
  }

  async upsertEnvironment(environment: AdminEnvironment): Promise<AdminConfig> {
    const now = new Date().toISOString();
    this.database.run(
      `
      INSERT INTO admin_environments (id, payload, created_at, updated_at)
      VALUES (?, ?, ?, ?)
      ON CONFLICT(id) DO UPDATE SET payload = excluded.payload, updated_at = excluded.updated_at
    `,
      [environment.id, JSON.stringify(environment), now, now]
    );
    this.persist();

    return this.getConfig();
  }

  async deleteEnvironment(environmentId: string): Promise<AdminConfig> {
    this.database.run('DELETE FROM admin_environments WHERE id = ?', [environmentId]);
    this.persist();
    const nextConfig = await this.getConfig();

    if (nextConfig.defaultEnvironmentId === environmentId && nextConfig.environments[0]) {
      await this.setDefaultEnvironment(nextConfig.environments[0].id);
    } else if (nextConfig.environments.length === 0) {
      this.database.run('DELETE FROM admin_settings WHERE key = ?', [
        DEFAULT_ENVIRONMENT_SETTING_KEY
      ]);
      this.persist();
    }

    return this.getConfig();
  }

  async setDefaultEnvironment(environmentId: string): Promise<AdminConfig> {
    const exists = this.selectOne<{ id: string }>(
      'SELECT id FROM admin_environments WHERE id = ?',
      [environmentId]
    );

    if (!exists) {
      throw new Error(`环境不存在: ${environmentId}`);
    }

    const now = new Date().toISOString();
    this.database.run(
      `
      INSERT INTO admin_settings (key, value, updated_at)
      VALUES (?, ?, ?)
      ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
    `,
      [DEFAULT_ENVIRONMENT_SETTING_KEY, environmentId, now]
    );
    this.persist();

    return this.getConfig();
  }

  close(): Promise<void> {
    this.persist();
    this.database.close();
    this.db = null;

    return Promise.resolve();
  }

  private get database(): SqlJsDatabase {
    if (!this.db) {
      throw new Error('SQLite store has not been initialized.');
    }

    return this.db;
  }

  private getDefaultEnvironmentId(environments: AdminEnvironment[]): string {
    const row = this.selectOne<{ value: string }>(
      'SELECT value FROM admin_settings WHERE key = ?',
      [DEFAULT_ENVIRONMENT_SETTING_KEY]
    );

    if (row && environments.some((environment) => environment.id === row.value)) {
      return row.value;
    }

    return environments[0]?.id ?? '';
  }

  private selectOne<T extends Record<string, unknown>>(
    sql: string,
    params: SqlValue[] = []
  ): T | null {
    return this.selectAll<T>(sql, params)[0] ?? null;
  }

  private selectAll<T extends Record<string, unknown>>(sql: string, params: SqlValue[] = []): T[] {
    const statement = this.database.prepare(sql, params);
    const rows: T[] = [];

    try {
      while (statement.step()) {
        rows.push(statement.getAsObject() as T);
      }
    } finally {
      statement.free();
    }

    return rows;
  }

  private persist() {
    writeFileSync(this.path, Buffer.from(this.database.export()));
  }
}
