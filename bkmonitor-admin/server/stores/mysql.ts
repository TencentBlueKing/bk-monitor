import mysql from 'mysql2/promise';

import {
  adminEnvironmentSchema,
  type AdminConfig,
  type AdminEnvironment
} from '../../src/features/environments/schemas';
import type { ServerConfig } from '../config';
import { DEFAULT_ENVIRONMENT_SETTING_KEY, type EnvironmentStore } from '../store';

export class MysqlEnvironmentStore implements EnvironmentStore {
  private readonly pool: mysql.Pool;

  constructor(config: ServerConfig['mysql']) {
    this.pool = config.uri
      ? mysql.createPool(config.uri)
      : mysql.createPool({
          host: config.host,
          port: config.port,
          user: config.user,
          password: config.password,
          database: config.database,
          connectionLimit: 10,
          namedPlaceholders: true
        });
  }

  async init(): Promise<void> {
    await this.pool.execute(`
      CREATE TABLE IF NOT EXISTS admin_environments (
        id VARCHAR(128) PRIMARY KEY,
        payload TEXT NOT NULL,
        created_at DATETIME(6) NOT NULL,
        updated_at DATETIME(6) NOT NULL
      )
    `);

    await this.pool.execute(`
      CREATE TABLE IF NOT EXISTS admin_settings (
        \`key\` VARCHAR(128) PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at DATETIME(6) NOT NULL
      )
    `);
  }

  async getConfig(): Promise<AdminConfig> {
    const [rows] = await this.pool.query<mysql.RowDataPacket[]>(
      'SELECT payload FROM admin_environments ORDER BY id ASC'
    );
    const environments = rows.map((row) =>
      adminEnvironmentSchema.parse(JSON.parse(String(row.payload)))
    );
    const defaultEnvironmentId = await this.getDefaultEnvironmentId(environments);

    return { environments, defaultEnvironmentId };
  }

  async upsertEnvironment(environment: AdminEnvironment): Promise<AdminConfig> {
    const now = new Date();
    await this.pool.execute(
      `
      INSERT INTO admin_environments (id, payload, created_at, updated_at)
      VALUES (?, ?, ?, ?)
      ON DUPLICATE KEY UPDATE payload = VALUES(payload), updated_at = VALUES(updated_at)
    `,
      [environment.id, JSON.stringify(environment), now, now]
    );

    return this.getConfig();
  }

  async deleteEnvironment(environmentId: string): Promise<AdminConfig> {
    await this.pool.execute('DELETE FROM admin_environments WHERE id = ?', [environmentId]);
    const nextConfig = await this.getConfig();

    if (nextConfig.defaultEnvironmentId === environmentId && nextConfig.environments[0]) {
      await this.setDefaultEnvironment(nextConfig.environments[0].id);
    } else if (nextConfig.environments.length === 0) {
      await this.pool.execute('DELETE FROM admin_settings WHERE `key` = ?', [
        DEFAULT_ENVIRONMENT_SETTING_KEY
      ]);
    }

    return this.getConfig();
  }

  async setDefaultEnvironment(environmentId: string): Promise<AdminConfig> {
    const [rows] = await this.pool.query<mysql.RowDataPacket[]>(
      'SELECT id FROM admin_environments WHERE id = ? LIMIT 1',
      [environmentId]
    );

    if (rows.length === 0) {
      throw new Error(`环境不存在: ${environmentId}`);
    }

    const now = new Date();
    await this.pool.execute(
      `
      INSERT INTO admin_settings (\`key\`, value, updated_at)
      VALUES (?, ?, ?)
      ON DUPLICATE KEY UPDATE value = VALUES(value), updated_at = VALUES(updated_at)
    `,
      [DEFAULT_ENVIRONMENT_SETTING_KEY, environmentId, now]
    );

    return this.getConfig();
  }

  async close(): Promise<void> {
    await this.pool.end();
  }

  private async getDefaultEnvironmentId(environments: AdminEnvironment[]): Promise<string> {
    const [rows] = await this.pool.query<mysql.RowDataPacket[]>(
      'SELECT value FROM admin_settings WHERE `key` = ? LIMIT 1',
      [DEFAULT_ENVIRONMENT_SETTING_KEY]
    );
    const defaultEnvironmentId = rows[0]?.value ? String(rows[0].value) : undefined;

    if (
      defaultEnvironmentId &&
      environments.some((environment) => environment.id === defaultEnvironmentId)
    ) {
      return defaultEnvironmentId;
    }

    return environments[0]?.id ?? '';
  }
}
