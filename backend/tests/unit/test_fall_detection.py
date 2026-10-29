import pytest

from app.vision.fall_detection import PoseObservation, detect_fall_events, pose_signals
from app.vision.pose_diagnostics import BASELINE_PROFILE, IMPROVED_PROFILE, diagnostic_series, run_profile


def upright(t, hip_y=.45, frame=""):
    return PoseObservation(t, (.5, hip_y - .22), (.5, hip_y), (.38, .12, .62, .9), .95, frame)


def horizontal(t, hip_y=.7, frame=""):
    return PoseObservation(t, (.3, hip_y), (.52, hip_y), (.15, .55, .85, .82), .95, frame)


def test_upright_walking_does_not_trigger():
    observations = [upright(i * .25, .44 + (i % 2) * .01) for i in range(12)]
    assert detect_fall_events(observations) == []


def test_sudden_transition_persisting_horizontal_triggers_review_candidate():
    observations = [upright(0, frame="u0"), upright(.4, frame="u1"), horizontal(.9, frame="h1"), horizontal(1.2, frame="h2"), horizontal(1.5, frame="h3")]
    events = detect_fall_events(observations)
    assert len(events) == 1
    assert events[0].state == "Potential Fall — Review Required"
    assert "h2" in events[0].supporting_frames


def test_sitting_and_crouching_do_not_trigger():
    sitting = [upright(0), PoseObservation(.5, (.5, .35), (.5, .58), (.35, .2, .65, .82), .95), PoseObservation(1, (.5, .36), (.5, .6), (.34, .22, .66, .84), .95)]
    assert detect_fall_events(sitting) == []


def test_missing_and_partial_pose_is_unknown():
    missing = PoseObservation(0, None, None, None, 0.0)
    partial = PoseObservation(1, (.5, .2), (.5, .5), (.4, .1, .6, .9), .3)
    assert pose_signals(missing)["state"] == "unknown"
    assert pose_signals(partial)["state"] == "unknown"
    assert detect_fall_events([upright(0), missing, partial]) == []


def test_recovery_does_not_create_second_event():
    sequence = [upright(0), horizontal(.6), horizontal(1.0), upright(1.8), upright(2.4)]
    assert len(detect_fall_events(sequence)) <= 1


def test_long_pose_tracking_interruption_cancels_candidate():
    sequence = [upright(0), horizontal(.4), PoseObservation(1.2, None, None, None, 0), horizontal(1.4), horizontal(2.1)]
    assert detect_fall_events(sequence, max_pose_gap=.5) == []


def test_event_end_extends_while_horizontal_and_evidence_explains_trigger():
    sequence = [upright(0, frame="u"), horizontal(.5, frame="h1"), horizontal(1.1, frame="h2"), horizontal(1.6, frame="h3")]
    event = detect_fall_events(sequence)[0]
    assert event.end_seconds == 1.6
    assert event.evidence["trigger_conditions"]["vertical_drop_met"] is True
    assert event.evidence["horizontal_persistence_seconds"] == pytest.approx(1.1)


def test_shape_gate_suppresses_torso_only_bending_false_alarm():
    lean = lambda t: PoseObservation(t, (.42, .68), (.62, .68), (.4, .35, .68, .85), .8, missing_landmarks=list(range(25, 33)))
    sequence = [upright(0, .45), upright(.4, .46), lean(.8), lean(.92), lean(1.04)]
    assert detect_fall_events(sequence, horizontal_persistence=.08)
    assert detect_fall_events(sequence, horizontal_persistence=.08, min_horizontal_aspect=.8) == []


def test_improved_profile_recovers_short_shape_supported_transition_without_changing_baseline():
    sequence = [upright(0), upright(.4), horizontal(.8), horizontal(.92), horizontal(1.04)]
    assert run_profile(sequence, BASELINE_PROFILE) == []
    assert len(run_profile(sequence, IMPROVED_PROFILE)) == 1


def test_diagnostic_series_reports_measured_missing_landmarks_and_drop():
    sequence = [upright(0, .45), horizontal(.5, .7)]
    sequence[1].missing_landmarks.extend([27, 28])
    series = diagnostic_series(sequence)
    assert series[1]["vertical_drop_from_recent_upright"] == pytest.approx(.25)
    assert series[1]["missing_lower_body"] == [27, 28]

