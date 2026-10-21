import type { ReactNode } from "react";

import type { Pod, Service, Workload } from "../contract/galaxy";
import type { GalaxyIndex } from "../model/galaxyIndex";
import { HEALTH_LABEL } from "../model/health";
import { componentId, namespaceId, nodeId } from "../model/ids";
import { KIND, type ObjectKind } from "../scene/symbology";
import { KindSymbol } from "./KindSymbol";

type Props = {
  index: GalaxyIndex;
  selectedId: string | null;
  onSelect: (id: string) => void;
  /** Why the list replaces the scene, when it is not the visitor's choice. */
  notice?: string;
};

/**
 * The same content as the scene, as nested lists: for screen readers, keyboards
 * and devices without WebGL. Nesting follows ownership, like positions do in the
 * scene; picking an item selects it exactly as a click in the scene would.
 */
export function ListView({ index, selectedId, onSelect, notice }: Props) {
  const { constellations, core } = index.galaxy;
  const bySystem = new Map<string, typeof core.components>();
  for (const c of core.components) bySystem.set(c.system, [...(bySystem.get(c.system) ?? []), c]);

  const item = (id: string, kind: ObjectKind, children: ReactNode[] = [], kindLabel?: string) => (
    <li key={id}>
      <button type="button" aria-current={id === selectedId || undefined} onClick={() => onSelect(id)}>
        <KindSymbol kind={kind} />
        <span className="tree-name">{index.label(id)}</span>
        <span className="tree-kind">{kindLabel ?? KIND[kind].label}</span>
        <Health index={index} id={id} />
      </button>
      {children.length > 0 && <ul>{children}</ul>}
    </li>
  );
  const pods = (list: Pod[]) => list.map((p) => item(p.id, "pod"));
  const services = (list: Service[]) => list.map((s) => item(s.id, "service"));
  const workload = (w: Workload) =>
    item(
      w.id,
      "workload",
      [...w.replica_sets.map((rs) => item(rs.id, "replicaset", pods(rs.pods))), ...pods(w.pods)],
      w.kind,
    );

  return (
    <section id="lista" className="list-view fade-in" aria-label="El clúster como lista">
      {notice && <p className="note">{notice}</p>}

      <h2>Proyectos</h2>
      <ul className="tree">
        {constellations.map((c) =>
          item(namespaceId(c.id), "namespace", [
            ...c.workloads.map(workload),
            ...services(c.services),
            ...c.routes.map((r) => item(r.id, "route")),
          ]),
        )}
      </ul>

      <h2>Infraestructura</h2>
      {[...bySystem].map(([system, components]) => (
        <section key={system} aria-label={system}>
          <h3>{system}</h3>
          <ul className="tree">
            {components.map((c) =>
              item(componentId(c.id), "component", [...pods(c.pods), ...services(c.services)]),
            )}
          </ul>
        </section>
      ))}

      <h2>Nodos</h2>
      <ul className="tree">{core.nodes.map((n) => item(nodeId(n.id), "node"))}</ul>
    </section>
  );
}

function Health({ index, id }: { index: GalaxyIndex; id: string }) {
  const health = index.health(id);
  return health ? <span className={`badge badge-${health}`}>{HEALTH_LABEL[health]}</span> : null;
}
