"use client";

import {AlertTriangle, CheckCircle2, LoaderCircle, ShieldAlert} from "lucide-react";
import {Video} from "@/lib/api";

export function ResearchBanner() {
  return <div className="research-banner"><ShieldAlert size={17}/><span><strong>Controlled research mode.</strong> Authorized recorded footage only. AI outputs are candidates for human review—not safety findings or calibrated probabilities.</span></div>;
}

export function Card({children, className=""}: {children: React.ReactNode; className?: string}) {
  return <section className={`panel ${className}`}>{children}</section>;
}

export function Metric({label, value, detail}: {label: string; value: string | number; detail?: string}) {
  return <Card className="metric"><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</Card>;
}

export function Status({value}: {value: string}) {
  const normalized = value.toLowerCase();
  const good = ["completed", "indexed", "confirmed_by_reviewer"].includes(normalized);
  const bad = ["failed", "false_positive"].includes(normalized);
  return <span className={`status ${good ? "status-good" : bad ? "status-bad" : "status-warn"}`}>{good ? <CheckCircle2 size={13}/> : bad ? <AlertTriangle size={13}/> : normalized === "running" ? <LoaderCircle className="spin" size={13}/> : null}{value.replaceAll("_", " ")}</span>;
}

export function Empty({title, detail}: {title: string; detail: string}) {
  return <div className="empty"><div className="empty-icon">◇</div><h3>{title}</h3><p>{detail}</p></div>;
}

export function ErrorBox({message}: {message: string}) {
  return <div className="error-box"><AlertTriangle size={18}/>{message}</div>;
}

export function VideoSelect({videos, value, onChange}: {videos: Video[]; value: string; onChange: (value: string) => void}) {
  return <select value={value} onChange={event => onChange(event.target.value)} aria-label="Select video">
    <option value="">Select a processed video…</option>
    {videos.map(video => <option key={video.id} value={video.id}>{video.original_filename} — {video.status}</option>)}
  </select>;
}

