import { num } from "@/lib/format";

type Point = { date: string; close: number };

export function PriceChart({ points }: { points: Point[] }) {
  const width = 800;
  const height = 260;
  if (points.length < 2) return <p className="note">No prices in this range.</p>;
  const closes = points.map((p) => p.close);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const span = max - min || 1;
  const x = (i: number) => (i / (points.length - 1)) * width;
  const y = (v: number) => 16 + (1 - (v - min) / span) * (height - 40);
  const line = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(p.close).toFixed(1)}`).join(" ");
  const ticks = [max, min + span * 0.5, min];
  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: "100%", height: "auto" }} role="img"
      aria-label={`Price chart from ${points[0].date} to ${points[points.length - 1].date}`}>
      <g stroke="var(--border)" strokeWidth="1">
        {ticks.map((t) => <line key={t} x1="0" x2={width} y1={y(t)} y2={y(t)} />)}
      </g>
      <path d={`${line} L${width} ${height} L0 ${height} Z`} fill="#4C9AFF" fillOpacity="0.08" />
      <path d={line} fill="none" stroke="#4C9AFF" strokeWidth="2" />
      <g fill="var(--faint)" fontSize="11" className="mono">
        {ticks.map((t) => <text key={t} x="4" y={y(t) - 4}>{num(t)}</text>)}
        <text x="4" y={height - 4}>{points[0].date}</text>
        <text x={width - 4} y={height - 4} textAnchor="end">{points[points.length - 1].date}</text>
      </g>
    </svg>
  );
}
