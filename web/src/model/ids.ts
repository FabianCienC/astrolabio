/**
 * Ids of objects the contract has no id for. Workloads, replica sets, pods,
 * services and routes already carry unique ids from the API.
 */

export const namespaceId = (namespace: string) => `${namespace}/namespace`;
export const componentId = (component: string) => `core/${component}`;
export const nodeId = (node: string) => `node/${node}`;
