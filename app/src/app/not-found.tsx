import Link from "next/link";

export default function NotFound() {
  return (
    <div className="card">
      <h2>Not found</h2>
      <p style={{ margin: 0 }}>
        No price data for this ticker. <Link href="/company/THYAO">Back to THYAO</Link>
      </p>
    </div>
  );
}
