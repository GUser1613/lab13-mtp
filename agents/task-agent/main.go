package main

import (
  "encoding/json"
  "log"
  "os"
  "github.com/nats-io/nats.go"
)

type Msg map[string]any

func processTask(in Msg) Msg {
  in["task_score"] = "priority-high"
  return in
}

func main() {
  url := getenv("NATS_URL", "nats://localhost:4222")
  nc, err := nats.Connect(url)
  if err != nil { log.Fatal(err) }
  defer nc.Close()

  _, err = nc.Subscribe("tasks.task", func(m *nats.Msg) {
    var in Msg
    _ = json.Unmarshal(m.Data, &in)
    outMsg := processTask(in)
    out, _ := json.Marshal(outMsg)
    _ = nc.Publish("results.task", out)
  })
  if err != nil { log.Fatal(err) }
  log.Println("task-agent started")
  select{}
}

func getenv(k,d string) string { v:=os.Getenv(k); if v=="" {return d}; return v }
