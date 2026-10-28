export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type Video = {
  id: string; original_filename: string; size_bytes: number; duration_seconds: number | null;
  width: number | null; height: number | null; fps: number | null; codec: string | null;
  status: string; is_demo: boolean; created_at: string; thumbnail_url: string | null; media_url: string;
};

export type EventCandidate = {
  id: string; video_id: string; event_type: string; label: string; start_seconds: number;
  end_seconds: number; processing_method: string; model_version: string;
  raw_scores: Record<string, unknown>; thresholds: Record<string, unknown>;
  supporting_frames: string[]; review_status: string; reviewer_note: string;
  synthetic_fixture: boolean; created_at: string;
};

export type EvidenceFrame = {
  id: string; timestamp_seconds: number; is_supporting: boolean;
  image_url: string; overlay_url: string; evidence_url: string;
};

export type EventEvidence = {event: EventCandidate; frames: EvidenceFrame[]};

export type FrameEvidence = {
  frame_id: string; timestamp_seconds: number; image_url: string; overlay_url: string;
  detections: {id:string;label:string;confidence:number;bbox:number[];track_id:number|null}[];
  pose_samples: {timestamp_seconds:number;frame_timestamp_seconds:number;sync_error_seconds:number;landmarks:Record<string,number>[];signals:Record<string,unknown>;sufficient_evidence:boolean}[];
  zones: {id:string;name:string;polygon:number[][]}[];
};

export type ValidationAnnotation = {
  id:string;video_id:string;event_type:string;start_seconds:number;end_seconds:number;
  ground_truth_label:string;annotation_source:string;reviewer_note:string;
  query_text:string|null;split:string;created_at:string;
};

export function asset(path?: string | null) {
  if (!path) return "";
  return path.startsWith("http") ? path : `${API_BASE}${path}`;
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {cache: "no-store", ...init});
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      message = typeof body.detail === "string" ? body.detail : body.detail?.message ?? body.error?.message ?? message;
    } catch {}
    throw new Error(message);
  }
  return response.json();
}

export function formatTime(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${(seconds % 60).toFixed(1).padStart(4, "0")}`;
}

