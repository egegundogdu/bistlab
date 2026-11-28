import { redirect } from "next/navigation";

export default async function Search({ searchParams }: { searchParams: Promise<{ ticker?: string }> }) {
  const { ticker } = await searchParams;
  const code = (ticker ?? "").trim().toUpperCase();
  redirect(/^[A-Z0-9.]{1,16}$/.test(code) ? `/company/${encodeURIComponent(code)}` : "/company/THYAO");
}
