package main

import (
  "encoding/json"
  "log"
  "os"
  "github.com/nats-io/nats.go"
)

type Msg map[string]any

func processDeadline(in Msg) Msg {
  in["deadline_risk"] = "medium"
  return in
}

func main() {
  nc, err := nats.Connect(getenv("NATS_URL", "nats://localhost:4222"))
  if err != nil { log.Fatal(err) }
  defer nc.Close()
  _, err = nc.Subscribe("tasks.deadline", func(m *nats.Msg) {
    var in Msg
    _ = json.Unmarshal(m.Data, &in)
    outMsg := processDeadline(in)
    out,_ := json.Marshal(outMsg)
    _ = nc.Publish("results.deadline", out)
  })
  if err != nil { log.Fatal(err) }
  log.Println("deadline-agent started")
  select{}
}
func getenv(k,d string) string { v:=os.Getenv(k); if v=="" {return d}; return v }
