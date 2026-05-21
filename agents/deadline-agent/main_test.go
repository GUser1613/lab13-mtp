package main

import "testing"

func TestProcessDeadlineSetsRisk(t *testing.T) {
	msg := Msg{"id": "2"}
	out := processDeadline(msg)
	if out["deadline_risk"] != "medium" {
		t.Fatalf("expected deadline_risk=medium, got %v", out["deadline_risk"])
	}
}

func TestGetenvFallback(t *testing.T) {
	v := getenv("NOT_SET_DEADLINE_AGENT", "fallback")
	if v != "fallback" {
		t.Fatalf("expected fallback, got %s", v)
	}
}
