import Link from "next/link";

export default function NotFound() {
  return (
    <div className="card">
      <h2>Bulunamadı</h2>
      <p style={{ margin: 0 }}>Bu kod için fiyat verisi yok. <Link href="/sirket/THYAO">THYAO&apos;ya dön</Link></p>
    </div>
  );
}
