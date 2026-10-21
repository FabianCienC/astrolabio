import type { CSSProperties } from "react";

import { KIND, type ObjectKind, type Shape } from "../scene/symbology";

/** Size in px of the symbol for an object of relative size 1. */
const SYMBOL_UNIT = 8;

type Props = { shape: Shape; color: string; size?: number };

/** A small CSS copy of a scene shape, for the legend and the sidebar. */
export function Symbol({ shape, color, size = 1.2 }: Props) {
  const px = Math.max(5, Math.round(SYMBOL_UNIT * size));
  const style = { width: px, height: px, "--symbol": color } as CSSProperties;
  return (
    <span className="symbol-slot" aria-hidden="true">
      <span className={`symbol symbol-${shape}`} style={style} />
    </span>
  );
}

/** The symbol of an object kind, exactly as the scene draws it. */
export function KindSymbol({ kind, size }: { kind: ObjectKind; size?: number }) {
  const info = KIND[kind];
  return <Symbol shape={info.shape} color={info.color} size={size ?? Math.min(info.size, 2)} />;
}
