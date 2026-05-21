package main

import (
  "encoding/json"
  "log"
  "os"
  "github.com/nats-io/nats.go"
)

type Msg map[string]any

func processBudget(in Msg) Msg {
  in["budget_status"] = "within-limit"
  return in
}

func main() {
  nc, err := nats.Connect(getenv("NATS_URL", "nats://localhost:4222"))
  if err != nil { log.Fatal(err) }
  defer nc.Close()
  _, err = nc.Subscribe("tasks.budget", func(m *nats.Msg) {
    var in Msg
    _ = json.Unmarshal(m.Data, &in)
    outMsg := processBudget(in)
    out,_ := json.Marshal(outMsg)
    _ = nc.Publish("results.budget", out)
  })
  if err != nil { log.Fatal(err) }
  log.Println("budget-agent started")
  select{}
}
func getenv(k,d string) string { v:=os.Getenv(k); if v=="" {return d}; return v }
