import type {Metadata} from "next";
import {Activity, Boxes, Clapperboard, Gauge, Info, Search, ShieldCheck} from "lucide-react";
import "./globals.css";

export const metadata: Metadata = {title: "VisionGuard AI", description: "Offline research video analysis and human review"};

const nav = [
  ["Overview", "/", Gauge], ["Video Workspace", "/videos", Clapperboard],
  ["Semantic Search", "/search", Search], ["Safety Analysis", "/safety", ShieldCheck],
  ["Incident Review", "/review", Activity], ["Models & System", "/system", Info],
] as const;

export default function RootLayout({children}: Readonly<{children: React.ReactNode}>) {
  return <html lang="en"><body><div className="shell">
    <aside className="sidebar">
      <a className="brand" href="/"><span className="brand-mark"><Boxes size={21}/></span><span>VisionGuard AI<small>RESEARCH CONSOLE</small></span></a>
      <nav className="nav">{nav.map(([label,href,Icon])=><a key={href} href={href}><Icon size={17}/>{label}</a>)}</nav>
      <div className="sidebar-foot">LOCAL MODE · NO LIVE CCTV<br/>No facial recognition or identity tracking.<br/>All events require human review.</div>
    </aside>
    <main className="main">{children}</main>
  </div></body></html>;
}

