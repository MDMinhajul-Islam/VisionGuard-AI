"use client";

import {useEffect,useMemo,useRef,useState} from "react";
import {Box,ChevronLeft,ChevronRight,Maximize2,ScanLine,Shapes,UserRound} from "lucide-react";
import {AnalysisSample,AnalysisTimeline,EventCandidate,asset,formatTime} from "@/lib/api";

const POSE_CONNECTIONS=[[0,1],[1,2],[2,3],[3,7],[0,4],[4,5],[5,6],[6,8],[9,10],[11,12],[11,13],[13,15],[15,17],[15,19],[15,21],[17,19],[12,14],[14,16],[16,18],[16,20],[16,22],[11,23],[12,24],[23,24],[23,25],[25,27],[27,29],[29,31],[24,26],[26,28],[28,30],[30,32]];

export function nearestSample(samples:AnalysisSample[],time:number,maxGap:number){
 if(!samples.length)return null;let lo=0,hi=samples.length-1;
 while(lo<hi){const mid=Math.floor((lo+hi)/2);if(samples[mid].timestamp_seconds<time)lo=mid+1;else hi=mid}
 const candidates=[samples[lo],samples[Math.max(0,lo-1)]].filter(Boolean);
 const nearest=candidates.reduce((a,b)=>Math.abs(a.timestamp_seconds-time)<=Math.abs(b.timestamp_seconds-time)?a:b);
 return Math.abs(nearest.timestamp_seconds-time)<=maxGap?nearest:null;
}

function contentRect(width:number,height:number,videoWidth:number,videoHeight:number){
 const scale=Math.min(width/videoWidth,height/videoHeight);const w=videoWidth*scale,h=videoHeight*scale;
 return{x:(width-w)/2,y:(height-h)/2,width:w,height:h};
}

export function VideoAnalysisPlayer({timeline,initialTime=0,onEventSelect}:{timeline:AnalysisTimeline;initialTime?:number;onEventSelect?:(event:EventCandidate)=>void}){
 const playerRef=useRef<HTMLDivElement>(null),videoRef=useRef<HTMLVideoElement>(null),canvasRef=useRef<HTMLCanvasElement>(null),frameRequest=useRef<number|null>(null);
 const [boxes,setBoxes]=useState(true),[tracks,setTracks]=useState(true),[pose,setPose]=useState(false),[zones,setZones]=useState(true),[highlights,setHighlights]=useState(true),[rate,setRate]=useState(1),[matched,setMatched]=useState<AnalysisSample|null>(null);
 const samples=timeline.samples;const maxGap=Math.min(.5,Math.max(.08,.55/(timeline.provenance.analysis_fps||2)));
 const sorted=useMemo(()=>[...samples].sort((a,b)=>a.timestamp_seconds-b.timestamp_seconds),[samples]);
 function draw(mediaTime:number){
  const video=videoRef.current,canvas=canvasRef.current;if(!video||!canvas||!video.videoWidth)return;
  const bounds=video.getBoundingClientRect(),dpr=window.devicePixelRatio||1,w=bounds.width,h=bounds.height;
  if(canvas.width!==Math.round(w*dpr)||canvas.height!==Math.round(h*dpr)){canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);canvas.style.width=`${w}px`;canvas.style.height=`${h}px`}
  const ctx=canvas.getContext("2d");if(!ctx)return;ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
  const rect=contentRect(w,h,video.videoWidth,video.videoHeight);const sample=nearestSample(sorted,mediaTime,maxGap);
  if(sample?.frame_id!==matched?.frame_id)setMatched(sample);
  if(zones){ctx.lineWidth=2;ctx.font="600 12px system-ui";for(const zone of timeline.zones){ctx.strokeStyle="#f6b84a";ctx.fillStyle="#f6b84a22";ctx.beginPath();zone.polygon.forEach(([x,y],i)=>{const px=rect.x+x*rect.width,py=rect.y+y*rect.height;if(i)ctx.lineTo(px,py);else ctx.moveTo(px,py)});ctx.closePath();ctx.fill();ctx.stroke();const [x,y]=zone.polygon[0];ctx.fillStyle="#fbd38d";ctx.fillText(zone.name,rect.x+x*rect.width+6,rect.y+y*rect.height-7)}}
  if(!sample)return;
  if(boxes){for(const d of sample.detections){const [x1,y1,x2,y2]=d.bbox,x=rect.x+x1*rect.width,y=rect.y+y1*rect.height,bw=(x2-x1)*rect.width,bh=(y2-y1)*rect.height;ctx.strokeStyle="#4de0c2";ctx.lineWidth=2;ctx.strokeRect(x,y,bw,bh);const label=`${d.label.toUpperCase()} · ${Math.round(d.confidence*100)}%${tracks&&d.track_id!=null?` · #${d.track_id}`:""}`;ctx.font="700 12px system-ui";const tw=ctx.measureText(label).width+12;ctx.fillStyle="#07110fe8";ctx.fillRect(x,Math.max(rect.y,y-23),tw,22);ctx.fillStyle="#8ff5df";ctx.fillText(label,x+6,Math.max(rect.y+15,y-8))}}
  if(pose){const observation=sample.poses[0];if(observation){const points=new Map(observation.landmarks.map(p=>[p.index,p]));ctx.lineWidth=2;ctx.strokeStyle="#68a8ff";for(const [a,b] of POSE_CONNECTIONS){const p=points.get(a),q=points.get(b);if(!p||!q||p.visibility<.4||q.visibility<.4)continue;ctx.beginPath();ctx.moveTo(rect.x+p.x*rect.width,rect.y+p.y*rect.height);ctx.lineTo(rect.x+q.x*rect.width,rect.y+q.y*rect.height);ctx.stroke()}for(const p of points.values()){if(p.visibility<.4)continue;ctx.fillStyle="#b9d6ff";ctx.beginPath();ctx.arc(rect.x+p.x*rect.width,rect.y+p.y*rect.height,3,0,Math.PI*2);ctx.fill()}}}
 }
 // eslint-disable-next-line react-hooks/exhaustive-deps
 useEffect(()=>{const video=videoRef.current;if(!video)return;video.currentTime=Math.min(initialTime,video.duration||initialTime);let stopped=false;const tick=(_:number,metadata?:VideoFrameCallbackMetadata)=>{if(stopped)return;draw(metadata?.mediaTime??video.currentTime);if("requestVideoFrameCallback" in video)frameRequest.current=video.requestVideoFrameCallback(tick);else frameRequest.current=requestAnimationFrame(tick as FrameRequestCallback)};tick(0);const redraw=()=>draw(video.currentTime);video.addEventListener("seeked",redraw);video.addEventListener("loadedmetadata",redraw);return()=>{stopped=true;video.removeEventListener("seeked",redraw);video.removeEventListener("loadedmetadata",redraw);if(frameRequest.current!=null){if("cancelVideoFrameCallback" in video)video.cancelVideoFrameCallback(frameRequest.current);else cancelAnimationFrame(frameRequest.current)}}},[timeline,boxes,tracks,pose,zones,maxGap,initialTime]);
 useEffect(()=>{if(videoRef.current)videoRef.current.playbackRate=rate},[rate]);
 function seek(time:number,event?:EventCandidate){if(videoRef.current){videoRef.current.currentTime=Math.max(0,time);draw(time)}if(event)onEventSelect?.(event)}
 function step(direction:number){const video=videoRef.current;if(!video||!sorted.length)return;video.pause();const found=sorted.findIndex(s=>s.timestamp_seconds>=video.currentTime);const index=found<0?sorted.length-1:found;const target=sorted[Math.max(0,Math.min(sorted.length-1,index+direction))];if(target)seek(target.timestamp_seconds)}
 async function enterFullscreen(){if(playerRef.current?.requestFullscreen)await playerRef.current.requestFullscreen()}
 return <div ref={playerRef} className="analysis-player" onKeyDown={e=>{if(e.key===" "){e.preventDefault();const video=videoRef.current;if(video){if(video.paused)void video.play();else video.pause()}}if(e.key==="ArrowLeft")step(-1);if(e.key==="ArrowRight")step(1)}} tabIndex={0}>
  <div className="analysis-stage"><video ref={videoRef} src={asset(timeline.video.media_url)} controls playsInline/><canvas ref={canvasRef} aria-label="Synchronized computer vision overlay"/><div className="analysis-hud"><span className="live-dot"/> Recorded analysis · sampled at {timeline.provenance.analysis_fps??"unknown"} FPS</div><div className="sample-state">{matched?<>Sample {formatTime(matched.timestamp_seconds)} · {matched.detections.length?`${matched.detections.length} genuine detections`:"analyzed sample: no detections"}</>:"No analyzed sample near this frame"}</div></div>
  <div className="player-tools"><button className={boxes?"toggle active":"toggle"} onClick={()=>setBoxes(!boxes)}><Box size={14}/>Boxes</button><button className={tracks?"toggle active":"toggle"} onClick={()=>setTracks(!tracks)}><ScanLine size={14}/>Track IDs</button><button className={pose?"toggle active":"toggle"} onClick={()=>setPose(!pose)}><UserRound size={14}/>Pose</button><button className={zones?"toggle active":"toggle"} onClick={()=>setZones(!zones)}><Shapes size={14}/>Zones</button><button className={highlights?"toggle active":"toggle"} onClick={()=>setHighlights(!highlights)}>Events</button><button className="toggle" onClick={()=>step(-1)} aria-label="Previous analyzed sample"><ChevronLeft size={14}/></button><button className="toggle" onClick={()=>step(1)} aria-label="Next analyzed sample"><ChevronRight size={14}/></button><button className="toggle" onClick={()=>void enterFullscreen()} aria-label="Enter fullscreen analysis"><Maximize2 size={14}/>Fullscreen</button><label>Speed <select value={rate} onChange={e=>setRate(Number(e.target.value))}><option value=".5">0.5×</option><option value="1">1×</option><option value="1.5">1.5×</option><option value="2">2×</option></select></label></div>
  <div className="event-timeline"><div className="timeline-track">{highlights&&timeline.events.map(event=><button key={event.id} className={`event-marker ${event.review_status}`} style={{left:`${100*event.start_seconds/(timeline.video.duration_seconds||1)}%`,width:`${Math.max(.5,100*(event.end_seconds-event.start_seconds)/(timeline.video.duration_seconds||1))}%`}} onClick={()=>seek(event.start_seconds,event)} title={`${event.label} · ${formatTime(event.start_seconds)}`}/>)}</div><div className="timeline-labels"><span>0:00</span><span>{formatTime(timeline.video.duration_seconds||0)}</span></div></div>
  <div className="provenance-strip"><strong>{timeline.provenance.detector_architecture}</strong><span>{timeline.provenance.detector_version}</span><span>{timeline.provenance.pose_model}</span><span>No interpolation</span></div>
 </div>
}
