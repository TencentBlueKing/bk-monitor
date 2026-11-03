/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { readFileSync, existsSync } from 'node:fs';
import { resolve, relative, isAbsolute } from 'node:path';
import { fileURLToPath } from 'node:url';
import { currentRouteContract, scanRouteContracts } from './acceptance-route-contract.mjs';
import { monitorBuildIdentity } from '../../packages/web-v3/tools/verify-monitor-build.mjs';
const webRoot = fileURLToPath(new URL('../..', import.meta.url));
export const criticalScenarios = [
  'application-auth-space-navigation',
  'sealed-v1-query-refresh-return',
  'retrieve-single',
  'retrieve-union',
  'retrieve-scene',
  'history-restoration',
  'date-time-and-refresh',
  'ui-sql-conditions',
  'ai-generation-cancel-error',
  'fields-trends-and-results',
  'details-context-realtime',
  'downloads-and-export-history',
  'favorites-groups-and-sharing',
  'clustering-full-workflow',
  'client-logs',
  'share-expiration-and-authorization',
  'monitor-apm-trace-hosts',
  'collection-host',
  'collection-container-file',
  'collection-container-stdout',
  'collection-windows-event',
  'custom-report-and-sdk',
  'index-sets-log',
  'index-sets-bkdata',
  'index-sets-es',
  'cleaning-and-templates',
  'grok',
  'masking',
  'extraction-and-links',
  'archives-and-restore',
  'clusters-subscriptions-tracking',
  'dashboards',
  'permission-errors-cancel-retry',
  'clean-checkout-subpath-and-rollback',
];
const key = route => JSON.stringify([route.name, route.path]);
export function evaluateFullBusinessAcceptance(report, { routes, identity, evidenceExists = () => false }) {
  const failures = [];
  if (report.sourceRoot !== 'packages/web-v3/src') failures.push({ gate: 'source-root' });
  if (report.sourceDigest !== identity.sourceDigest || report.buildConfigDigest !== identity.buildConfigDigest)
    failures.push({ gate: 'snapshot', reason: 'Evidence is not bound to current source/build configuration' });
  if (report.strictTypeDiagnostics !== 0)
    failures.push({ gate: 'strict-types', diagnostics: report.strictTypeDiagnostics });
  if (report.remainingJavascript !== 0)
    failures.push({ gate: 'typescript-migration', remaining: report.remainingJavascript });
  const fullEvidence = item =>
    item?.businessAccepted === true &&
    item?.visualAccepted === true &&
    item?.evidenceScope === 'full-business-and-ui-states' &&
    item?.evidence?.length > 0 &&
    item.evidence.every(evidenceExists);
  const unacceptedRoutes = routes.filter(route => !fullEvidence(report.routes?.find(item => key(item) === key(route))));
  if (unacceptedRoutes.length)
    failures.push({
      gate: 'route-business-and-visual',
      count: unacceptedRoutes.length,
      routes: unacceptedRoutes.map(route => ({ name: route.name, path: route.path })),
    });
  const unacceptedScenarios = criticalScenarios.filter(
    id => !fullEvidence(report.scenarios?.find(item => item.id === id)),
  );
  if (unacceptedScenarios.length)
    failures.push({ gate: 'critical-scenarios', count: unacceptedScenarios.length, scenarios: unacceptedScenarios });
  if (!Array.isArray(report.unresolvedHighImpactDifferences) || report.unresolvedHighImpactDifferences.length)
    failures.push({ gate: 'high-impact-differences', issues: report.unresolvedHighImpactDifferences });
  if (
    !report.resources ||
    report.resources.existingResourcesModified !== false ||
    !report.resources.allOwnedResourcesCleaned
  )
    failures.push({ gate: 'test-resource-isolation-and-cleanup' });
  for (const name of ['tests', 'applicationBuild', 'monitorBuilds', 'staticLegacyDelivery', 'sourceRouteParity'])
    if (report.checks?.[name]?.status !== 'PASSED') failures.push({ gate: name });
  return {
    status: failures.length ? 'REJECTED' : 'ACCEPTED',
    failedGates: failures,
    coverage: {
      routeTotal: routes.length,
      businessAndVisualAccepted: routes.length - unacceptedRoutes.length,
      criticalScenarioTotal: criticalScenarios.length,
      criticalScenariosAccepted: criticalScenarios.length - unacceptedScenarios.length,
    },
  };
}
export function validateCurrentAcceptance(report) {
  const contract = currentRouteContract();
  const result = evaluateFullBusinessAcceptance(report, {
    routes: scanRouteContracts(resolve(webRoot, 'packages/web-v2/src/router')),
    identity: monitorBuildIdentity(),
    evidenceExists: file => {
      const path = resolve(webRoot, file),
        candidate = relative(webRoot, path);
      return !isAbsolute(candidate) && candidate !== '..' && !candidate.startsWith('../') && existsSync(path);
    },
  });
  if (contract.missing.length || contract.extra.length || contract.metadataDifferences.length) {
    result.status = 'REJECTED';
    result.failedGates.push({ gate: 'current-source-route-contract', contract });
  }
  return result;
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const state = JSON.parse(readFileSync(resolve(webRoot, 'migration-project/artifacts/tasks/execution-status.json')));
  const reportFile = process.argv[2] || state.fullBusinessAcceptance?.report;
  if (!reportFile) throw Error('No current full-business acceptance report is registered');
  const result = validateCurrentAcceptance(JSON.parse(readFileSync(resolve(webRoot, reportFile))));
  console.log(JSON.stringify(result, null, 2));
  process.exitCode = result.status === 'ACCEPTED' ? 0 : 1;
}
