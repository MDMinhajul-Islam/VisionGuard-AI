"use client";

import Link from "next/link";
import {useEffect, useMemo, useState} from "react";
import {usePathname, useRouter} from "next/navigation";
import {Activity, Boxes, Clapperboard, ClipboardCheck, Database, Gauge, Info, LogIn, LogOut, Search, ShieldCheck} from "lucide-react";
import {announceTenantScopeReady,request} from "@/lib/api";

type Site = {id:string;name:string;status:string};
type Organization = {id:string;name:string;workspace_type:string;membership_role:string;sites:Site[]};
type User = {display_name:string;role:string};

const commonNav = [
  ["Overview", "/", Gauge], ["Video Workspace", "/videos", Clapperboard],
  ["Safety Analysis", "/safety", ShieldCheck], ["Incident Review", "/review", Activity],
  ["Models & System", "/system", Info],
] as const;
const researchNav = [
  ["Semantic Search", "/search", Search], ["Validation", "/validation", ClipboardCheck],
  ["Dataset Evaluation", "/datasets", Database],
] as const;

export function TenantSidebar() {
  const router=useRouter(); const pathname=usePathname();
  const [organizations,setOrganizations]=useState<Organization[]>([]);
  const [user,setUser]=useState<User|null>(null);
  const [organizationId,setOrganizationId]=useState("");
  const [siteId,setSiteId]=useState("");
  useEffect(()=>{
    Promise.all([request<User>("/api/auth/me"),request<Organization[]>("/api/organizations")])
      .then(([me,items])=>{
        setUser(me); setOrganizations(items);
        const savedOrg=localStorage.getItem("visionguard_org_id");
        const selected=items.find(item=>item.id===savedOrg)??items[0];
        if(selected){
          const savedSite=localStorage.getItem("visionguard_site_id");
          const site=selected.sites.find(item=>item.id===savedSite)??selected.sites[0];
          setOrganizationId(selected.id); localStorage.setItem("visionguard_org_id",selected.id); localStorage.setItem("visionguard_workspace_type",selected.workspace_type);
          if(site){setSiteId(site.id);localStorage.setItem("visionguard_site_id",site.id)}
          announceTenantScopeReady();
        }
      }).catch(()=>{if(pathname!=="/login")router.replace("/login?reason=session_expired")});
  },[pathname,router]);
  const organization=useMemo(()=>organizations.find(item=>item.id===organizationId),[organizations,organizationId]);
  const nav=organization?.workspace_type==="research"?[...commonNav,...researchNav]:commonNav;
  function selectOrganization(value:string){
    const selected=organizations.find(item=>item.id===value); const site=selected?.sites[0];
    localStorage.setItem("visionguard_org_id",value); localStorage.setItem("visionguard_workspace_type",selected?.workspace_type??""); setOrganizationId(value);
    if(site){localStorage.setItem("visionguard_site_id",site.id);setSiteId(site.id)} else {localStorage.removeItem("visionguard_site_id");setSiteId("")}
    window.location.reload();
  }
  function selectSite(value:string){localStorage.setItem("visionguard_site_id",value);setSiteId(value);window.location.reload()}
  async function logout(){await request("/api/auth/logout",{method:"POST"});localStorage.removeItem("visionguard_org_id");localStorage.removeItem("visionguard_site_id");router.replace("/login")}
  return <aside className="sidebar">
    <Link className="brand" href="/"><span className="brand-mark"><Boxes size={21}/></span><span>VisionGuard AI<small>SECURE REVIEW CONSOLE</small></span></Link>
    {user&&<div className="tenant-picker">
      <div className="user-summary"><span aria-hidden="true">{user.display_name.trim().charAt(0).toUpperCase()}</span><small>{user.display_name}</small></div>
      <select aria-label="Current organization" value={organizationId} onChange={event=>selectOrganization(event.target.value)}>{organizations.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select>
      <select aria-label="Current site" value={siteId} onChange={event=>selectSite(event.target.value)}>{organization?.sites.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select>
      <small>{organization?.membership_role.replaceAll("_"," ")}</small>
    </div>}
    <nav className="nav" aria-label="Primary navigation">{nav.map(([label,href,Icon])=>{const active=href==="/"?pathname==="/":pathname.startsWith(href);return <Link key={href} href={href} className={active?"active":""} aria-current={active?"page":undefined}><Icon size={17}/>{label}</Link>})}{user?<button className="nav-action" onClick={()=>void logout()}><LogOut size={17}/>Sign out</button>:<Link href="/login"><LogIn size={17}/>Sign in</Link>}</nav>
    <div className="sidebar-foot">LOCAL MODE · NO LIVE CCTV<br/>Organization and site isolation enforced by the API.<br/>All events require human review.</div>
  </aside>;
}
