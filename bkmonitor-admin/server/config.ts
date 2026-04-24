import { mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

import dotenv from 'dotenv';

dotenv.config();

export type AdminDbClient = 'sqlite' | 'mysql';

export interface ServerConfig {
  host: string;
  port: number;
  dbClient: AdminDbClient;
  sqlitePath: string;
  mysql: {
    uri?: string | undefined;
    host: string;
    port: number;
    user: string;
    password: string;
    database: string;
  };
}

const sqlitePath = resolve(
  process.cwd(),
  process.env.BKMONITOR_ADMIN_SQLITE_PATH ?? '.data/bkmonitor-admin.sqlite'
);

export const serverConfig: ServerConfig = {
  host: process.env.BKMONITOR_ADMIN_HOST ?? '127.0.0.1',
  port: Number(process.env.BKMONITOR_ADMIN_PORT ?? 5174),
  dbClient: parseDbClient(process.env.BKMONITOR_ADMIN_DB_CLIENT),
  sqlitePath,
  mysql: {
    uri: process.env.BKMONITOR_ADMIN_MYSQL_URL,
    host: process.env.BKMONITOR_ADMIN_MYSQL_HOST ?? '127.0.0.1',
    port: Number(process.env.BKMONITOR_ADMIN_MYSQL_PORT ?? 3306),
    user: process.env.BKMONITOR_ADMIN_MYSQL_USER ?? 'root',
    password: process.env.BKMONITOR_ADMIN_MYSQL_PASSWORD ?? '',
    database: process.env.BKMONITOR_ADMIN_MYSQL_DATABASE ?? 'bkmonitor_admin'
  }
};

if (serverConfig.dbClient === 'sqlite') {
  mkdirSync(dirname(serverConfig.sqlitePath), { recursive: true });
}

function parseDbClient(value: string | undefined): AdminDbClient {
  return value === 'mysql' ? 'mysql' : 'sqlite';
}
