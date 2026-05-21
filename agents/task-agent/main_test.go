package main

import "testing"

func TestProcessTaskSetsScore(t *testing.T) {
	msg := Msg{"id": "1"}
	out := processTask(msg)
	if out["task_score"] != "priority-high" {
		t.Fatalf("expected task_score=priority-high, got %v", out["task_score"])
	}
}

func TestGetenvFallback(t *testing.T) {
	v := getenv("NOT_SET_TASK_AGENT", "fallback")
	if v != "fallback" {
		t.Fatalf("expected fallback, got %s", v)
	}
}
