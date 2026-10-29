import type {Metadata} from "next";
import {TenantSidebar} from "@/components/tenant-sidebar";
import "./globals.css";

export const metadata: Metadata = {title: "VisionGuard AI", description: "Offline research video analysis and human review"};

export default function RootLayout({children}: Readonly<{children: React.ReactNode}>) {
  return <html lang="en"><body><div className="shell">
    <TenantSidebar/>
    <main className="main">{children}</main>
  </div></body></html>;
}

