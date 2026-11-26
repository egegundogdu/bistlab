import { redirect } from "next/navigation";

export default async function Search({ searchParams }: { searchParams: Promise<{ kod?: string }> }) {
  const { kod } = await searchParams;
  const code = (kod ?? "").trim().toUpperCase();
  redirect(/^[A-Z0-9.]{1,16}$/.test(code) ? `/sirket/${encodeURIComponent(code)}` : "/sirket/THYAO");
}
