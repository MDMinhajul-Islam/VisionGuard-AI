"use client";

import {useEffect, useState} from "react";
import Link from "next/link";
import {ArrowRight, Database, Film, Search, ShieldCheck} from "lucide-react";
import {Card, ErrorBox, Metric, ResearchBanner} from "@/components/ui";
import {request} from "@/lib/api";

type Overview = {videos:number;jobs:number;indexed_videos:number;candidate_events:number;pending_review:number;processing_failures:number};

export default function OverviewPage() {
  const [data,setData]=useState<Overview|null>(null); const [error,setError]=useState("");
  useEffect(()=>{request<Overview>("/api/overview").then(setData).catch(e=>setError(e.message))},[]);
  return <>
    <header className="page-head"><div><div className="eyebrow">Offline video intelligence</div><h1>Operations overview</h1><p>Measured state from the local PostgreSQL workspace—no placeholder production statistics.</p></div><ResearchBanner/></header>
    {error&&<ErrorBox message={error}/>}<div className="grid metrics">
      <Metric label="Uploaded videos" value={data?.videos??"—"}/><Metric label="Processing jobs" value={data?.jobs??"—"}/><Metric label="Indexed videos" value={data?.indexed_videos??"—"}/><Metric label="Candidate events" value={data?.candidate_events??"—"}/><Metric label="Pending review" value={data?.pending_review??"—"}/><Metric label="Failures" value={data?.processing_failures??"—"}/>
    </div>
    <div className="grid grid-3">
      <Card><Film color="#4de0c2"/><h2 style={{marginTop:14}}>Ingest & process</h2><p>Validate recorded MP4 footage, extract timestamped frames, and run bounded local jobs.</p><Link className="button secondary" href="/videos">Open workspace <ArrowRight size={15}/></Link></Card>
      <Card><Search color="#68a8ff"/><h2 style={{marginTop:14}}>Semantic retrieval</h2><p>Use actual CLIP ViT-B/32 embeddings to find candidate moments with temporal suppression.</p><Link className="button secondary" href="/search">Search indexed video <ArrowRight size={15}/></Link></Card>
      <Card><ShieldCheck color="#f6b84a"/><h2 style={{marginTop:14}}>Human-reviewed safety</h2><p>Inspect experimental pose and zone events. The system never confirms an incident automatically.</p><Link className="button secondary" href="/review">Review candidates <ArrowRight size={15}/></Link></Card>
    </div>
    <Card className="" ><div style={{display:"flex",gap:14,alignItems:"center"}}><Database color="#8f9bad"/><div><h3>Data boundary</h3><p style={{margin:0}}>Uploads, embeddings, detections, reviews, and exports stay on this machine. Runtime artifacts are excluded from Git.</p></div></div></Card>
  </>;
}

