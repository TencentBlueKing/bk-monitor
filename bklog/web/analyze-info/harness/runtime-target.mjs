/** Bind reviewed endpoint templates to one explicit target; never broaden the allowlist. */
export function bindTargetContracts(contracts, target) {
  const route = new URL(target).hash.slice(1).split('?')[0];
  const indexId = /^\/retrieve\/(\d+)$/.exec(route)?.[1];
  return contracts.flatMap(contract => {
    if (!contract.path.includes('{indexId}')) return [{ ...contract }];
    return indexId ? [{ ...contract, path: contract.path.replaceAll('{indexId}', indexId) }] : [];
  });
}
