import type { GalaxyIndex } from "../model/galaxyIndex";
import { HEALTH_LABEL } from "../model/health";
import { componentId, namespaceId, nodeId } from "../model/ids";
import { KindSymbol } from "./KindSymbol";
import { ObjectDetails } from "./ObjectDetails";

type Props = {
  index: GalaxyIndex;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
};

/**
 * Always-visible panel on the right. With a selection it describes that object
 * (this is where health lives); without one it summarizes the cluster and lets
 * you jump to any project, component or node.
 */
export function Sidebar({ index, selectedId, onSelect }: Props) {
  const entry = selectedId ? index.get(selectedId) : undefined;

  return (
    <aside className="sidebar" aria-label="Detalle">
      {entry ? (
        // Keyed by id, so switching objects replays the fade-in.
        <div key={entry.id} className="fade-in">
          <button type="button" className="back" onClick={() => onSelect(null)}>
            ← Vista general
          </button>
          <ObjectDetails entry={entry} index={index} onSelect={onSelect} />
        </div>
      ) : (
        <div className="fade-in">
          <Overview index={index} onSelect={onSelect} />
        </div>
      )}
    </aside>
  );
}

function Overview({ index, onSelect }: { index: GalaxyIndex; onSelect: (id: string) => void }) {
  const { constellations, core } = index.galaxy;
  const projectPods = constellations.flatMap((c) =>
    c.workloads.flatMap((w) => [...w.pods, ...w.replica_sets.flatMap((r) => r.pods)]),
  );
  const platformPods = core.components.flatMap((c) => c.pods);
  const bySystem = new Map<string, typeof core.components>();
  for (const c of core.components) bySystem.set(c.system, [...(bySystem.get(c.system) ?? []), c]);
  const systems = [...bySystem];

  return (
    <div className="overview">
      <h2>El clúster</h2>
      <p className="hint">Haz clic en cualquier objeto de la escena para ver su detalle.</p>

      <dl className="stats">
        <div><dt>Proyectos</dt><dd>{constellations.length}</dd></div>
        <div><dt>Nodos</dt><dd>{core.nodes.length}</dd></div>
        <div><dt>Pods</dt><dd>{projectPods.length + platformPods.length}</dd></div>
      </dl>

      <h3>Proyectos</h3>
      <ul className="picker">
        {constellations.map((c) => (
          <li key={c.id}>
            <button type="button" onClick={() => onSelect(namespaceId(c.id))}>
              <KindSymbol kind="namespace" size={1.2} />
              <span>{c.project}</span>
              <span className={`badge badge-${c.health}`}>{HEALTH_LABEL[c.health]}</span>
            </button>
          </li>
        ))}
      </ul>

      {systems.map(([system, components]) => (
        <section key={system}>
          <h3>{system}</h3>
          <ul className="picker">
            {components.map((c) => (
              <li key={c.id}>
                <button type="button" onClick={() => onSelect(componentId(c.id))}>
                  <KindSymbol kind="component" />
                  <span>{c.name}</span>
                  <span className={`badge badge-${c.health}`}>{HEALTH_LABEL[c.health]}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}

      <h3>Nodos</h3>
      <ul className="picker">
        {core.nodes.map((n) => (
          <li key={n.id}>
            <button type="button" onClick={() => onSelect(nodeId(n.id))}>
              <KindSymbol kind="node" size={1.2} />
              <span>{n.name}</span>
              <span className={`badge badge-${n.health}`}>{HEALTH_LABEL[n.health]}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
