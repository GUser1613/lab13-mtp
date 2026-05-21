package main

import "testing"

func TestProcessResourceSetsFields(t *testing.T) {
	msg := Msg{"id": "4"}
	out := processResource(msg, "10")
	if out["resource_plan"] != "team-A" {
		t.Fatalf("expected resource_plan=team-A, got %v", out["resource_plan"])
	}
	if out["resource_counter"] != "10" {
		t.Fatalf("expected resource_counter=10, got %v", out["resource_counter"])
	}
}

func TestGetenvFallback(t *testing.T) {
	v := getenv("NOT_SET_RESOURCE_AGENT", "fallback")
	if v != "fallback" {
		t.Fatalf("expected fallback, got %s", v)
	}
}
