"use client";

import {FormEvent, useState} from "react";
import {useRouter} from "next/navigation";
import {API_BASE} from "@/lib/api";
import {Card, ErrorBox, ResearchBanner} from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const [email,setEmail]=useState("");
  const [password,setPassword]=useState("");
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  async function submit(event:FormEvent) {
    event.preventDefault();setBusy(true);setError("");
    try {
      const response=await fetch(`${API_BASE}/api/auth/login`,{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({email,password})});
      if(!response.ok) throw new Error(response.status===401?"Invalid email or password.":"Sign-in failed.");
      router.push("/");router.refresh();
    } catch(error) {setError((error as Error).message)} finally {setBusy(false)}
  }
  return <><header className="page-head"><div><div className="eyebrow">Protected local workspace</div><h1>Sign in</h1><p>Use an administrator or reviewer account created by the local operator.</p></div><ResearchBanner/></header><div className="grid grid-2"><Card><form onSubmit={submit}><label>Email<input aria-label="Email" type="email" autoComplete="username" required value={email} onChange={event=>setEmail(event.target.value)}/></label><label>Password<input aria-label="Password" type="password" autoComplete="current-password" minLength={12} required value={password} onChange={event=>setPassword(event.target.value)}/></label>{error&&<ErrorBox message={error}/>}<button type="submit" disabled={busy}>{busy?"Signing in…":"Sign in"}</button></form></Card><Card><h2>Access policy</h2><p>Reviewers may inspect evidence, record human review decisions, and export approved clips. Administrators additionally manage uploads, processing, zones, annotations, and users.</p><p className="muted">Sessions are stored in an HttpOnly cookie. This local foundation is not a substitute for enterprise SSO or MFA.</p></Card></div></>;
}
