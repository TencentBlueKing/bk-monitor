import { existsSync, mkdirSync, realpathSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, isAbsolute, relative, resolve, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const repository = realpathSync(fileURLToPath(new URL('../../../../', import.meta.url)));
const inside = (root, path) => {
  const part = relative(root, path);
  return part === '' || (part !== '..' && !part.startsWith(`..${sep}`) && !isAbsolute(part));
};

/** Resolve existing ancestors too, so a symlink cannot redirect private output into Git. */
export function assertExternalPath(path) {
  const absolute = resolve(path);
  let ancestor = absolute;
  while (!existsSync(ancestor)) ancestor = dirname(ancestor);
  const actual = resolve(realpathSync(ancestor), relative(ancestor, absolute));
  if (inside(repository, absolute) || inside(repository, actual)) throw Error('PRIVATE_ARTIFACT_PATH_INSIDE_REPOSITORY');
  return actual;
}

export function localArtifactPath(path = '') {
  const root = assertExternalPath(process.env.BKLOG_LOCAL_ARTIFACTS_DIR || resolve(tmpdir(), 'bklog-migration-local'));
  const candidate = resolve(root, path);
  if (!inside(root, candidate)) throw Error('PRIVATE_ARTIFACT_PATH_ESCAPES_ROOT');
  const target = assertExternalPath(candidate);
  mkdirSync(root, { recursive: true, mode: 0o700 });
  mkdirSync(dirname(target), { recursive: true, mode: 0o700 });
  if (path.endsWith('/')) mkdirSync(target, { recursive: true, mode: 0o700 });
  return target;
}

export function localArtifactUrl(path = '') {
  const target = localArtifactPath(path);
  return pathToFileURL(path.endsWith('/') ? target + sep : target);
}
