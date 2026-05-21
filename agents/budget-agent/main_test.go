package main

import "testing"

func TestProcessBudgetSetsStatus(t *testing.T) {
	msg := Msg{"id": "3"}
	out := processBudget(msg)
	if out["budget_status"] != "within-limit" {
		t.Fatalf("expected budget_status=within-limit, got %v", out["budget_status"])
	}
}

func TestGetenvFallback(t *testing.T) {
	v := getenv("NOT_SET_BUDGET_AGENT", "fallback")
	if v != "fallback" {
		t.Fatalf("expected fallback, got %s", v)
	}
}
