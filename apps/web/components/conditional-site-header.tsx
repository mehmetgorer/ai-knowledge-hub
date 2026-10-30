"use client";

import { usePathname } from "next/navigation";

import { SiteHeader } from "@/components/site-header";

/** Public routes only — authenticated dashboard uses its own app chrome. */
export function ConditionalSiteHeader() {
  const pathname = usePathname();
  if (pathname === "/dashboard" || pathname?.startsWith("/dashboard/")) {
    return null;
  }
  return <SiteHeader />;
}
