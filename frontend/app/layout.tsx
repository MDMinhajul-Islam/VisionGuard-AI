import type {Metadata} from "next";
import {TenantSidebar} from "@/components/tenant-sidebar";
import "./globals.css";

export const metadata: Metadata = {title: "VisionGuard AI", description: "Offline research video analysis and human review"};

export default function RootLayout({children}: Readonly<{children: React.ReactNode}>) {
  return <html lang="en"><body><div className="shell">
    <a className="skip-link" href="#main-content">Skip to main content</a>
    <TenantSidebar/>
    <main className="main" id="main-content" tabIndex={-1}>{children}</main>
  </div></body></html>;
}

