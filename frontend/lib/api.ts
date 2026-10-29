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

export type DatasetAsset = {
  id:string;video_id:string;dataset_name:string;original_recording_id:string;
  evaluation_label:"fall"|"non_fall";detailed_label:string|null;source_url:string;
  source_license:string;annotation_status:string;manifest_record:Record<string,unknown>;imported_at:string;
  video:Video|null;latest_job:{id:string;status:string;progress:number;stage:string;metrics_json:string}|null;
  predicted_fall:boolean;predicted_event_count:number;predicted_events:EventCandidate[];
};

export type DatasetEvaluation = {
  dataset_name:string;protocol:string;event_level_warning:string;
  metrics:{videos:number;true_positives:number;false_positives:number;true_negatives:number;false_negatives:number;precision:number|null;recall:number|null;f1:number|null;false_positive_ids:string[];false_negative_ids:string[];undefined_metrics:string[]};
  records:{asset_id:string;record_id:string;video_id:string;ground_truth:string;predicted_fall:boolean;event_count:number;candidate_timestamps:number[];processing_status:string;processing_metrics:Record<string,unknown>;duration_seconds:number|null;annotation_status:string}[];
};

export type PoseDiagnosticPoint = {
  timestamp_seconds:number;state:string;torso_angle_degrees:number;aspect_ratio:number;
  hip_y:number|null;bbox_center_y:number|null;bbox_width:number|null;bbox_height:number|null;vertical_drop_from_recent_upright:number|null;visibility:number;
  missing_landmarks:number[];missing_lower_body:number[];frame_id:string;image_url:string;overlay_url:string;
};

export type DatasetDiagnostic = {
  asset_id:string;record_id:string;video_id:string;ground_truth:string;annotation_status:string;
  summary:{pose_samples:number;valid_pose_samples:number;unknown_pose_samples:number;pose_availability:number;max_valid_gap_seconds:number;max_torso_angle_degrees:number;max_aspect_ratio:number;max_vertical_drop_from_recent_upright:number|null;state_counts:Record<string,number>};
  timeline:PoseDiagnosticPoint[];
  source_intervals:{id:string;start_seconds:number;end_seconds:number;label:string;source:string}[];
  stored_baseline_events:EventCandidate[];
  profiles:Record<"baseline"|"improved"|"motion_fusion",{thresholds:Record<string,number|string>;events:{start_seconds:number;end_seconds:number;confidence_signal:number;evidence:Record<string,unknown>}[]}>;
  warning:string;
};

export function asset(path?: string | null) {
  if (!path) return "";
  return path.startsWith("http") ? path : `${API_BASE}${path}`;
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {cache: "no-store", credentials: "include", ...init});
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

