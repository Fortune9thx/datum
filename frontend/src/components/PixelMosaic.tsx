/**
 * The DATUM pixel motif: plain SVG rectangles, drawn only on dark bands.
 *
 * The pattern is derived from a deterministic integer hash rather than
 * Math.random, so the server and client render byte-identical markup and
 * there is no hydration mismatch.
 */

function hash(x: number, y: number, seed: number): number {
  let n = (x * 374761393 + y * 668265263 + seed * 1274126177) | 0;
  n = (n ^ (n >>> 13)) | 0;
  n = Math.imul(n, 1274126177) | 0;
  return ((n ^ (n >>> 16)) >>> 0) / 4294967296;
}

export function PixelMosaic({
  rows = 14,
  cols = 88,
  cell = 12,
  seed = 7,
  height = 168,
  flip = false,
}: {
  rows?: number;
  cols?: number;
  cell?: number;
  seed?: number;
  height?: number;
  flip?: boolean;
}) {
  const w = cols * cell;
  const h = rows * cell;
  const rects: React.ReactElement[] = [];

  for (let y = 0; y < rows; y++) {
    for (let x = 0; x < cols; x++) {
      const fx = flip ? 1 - x / (cols - 1) : x / (cols - 1);
      // Density is high at the leading edge and dissolves across the strip,
      // with a soft vertical taper so the cluster reads as a cloud, not a bar.
      const taper = 1 - Math.abs(y / (rows - 1) - 0.5) * 0.65;
      const p = Math.pow(Math.max(0, 1 - fx * 1.22), 1.55) * taper;
      if (hash(x, y, seed) > p) continue;

      const tone = hash(x, y, seed + 991);
      const opacity = tone > 0.84 ? 1 : tone > 0.56 ? 0.7 : tone > 0.3 ? 0.44 : 0.22;
      rects.push(
        <rect
          key={`${x}-${y}`}
          x={x * cell}
          y={y * cell}
          width={cell - 1}
          height={cell - 1}
          fill="var(--pixel)"
          opacity={opacity}
        />
      );
    }
  }

  return (
    <div style={{ height, overflow: "hidden", lineHeight: 0 }} aria-hidden="true">
      <svg
        viewBox={`0 0 ${w} ${h}`}
        width="100%"
        height={height}
        preserveAspectRatio="xMidYMid slice"
        role="presentation"
      >
        {rects}
      </svg>
    </div>
  );
}
