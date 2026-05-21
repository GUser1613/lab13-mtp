package main

import (
  "context"
  "encoding/json"
  "log"
  "os"
  "github.com/nats-io/nats.go"
  "github.com/redis/go-redis/v9"
)

type Msg map[string]any

func processResource(in Msg, cnt string) Msg {
  in["resource_plan"] = "team-A"
  in["resource_counter"] = cnt
  return in
}

func main() {
  nc, err := nats.Connect(getenv("NATS_URL", "nats://localhost:4222"))
  if err != nil { log.Fatal(err) }
  defer nc.Close()
  rdb := redis.NewClient(&redis.Options{Addr: getenv("REDIS_ADDR", "localhost:6379")})
  ctx := context.Background()

  _, err = nc.Subscribe("tasks.resource", func(m *nats.Msg) {
    var in Msg
    _ = json.Unmarshal(m.Data, &in)
    _ = rdb.Incr(ctx, "resource_agent_count").Err()
    cnt, _ := rdb.Get(ctx, "resource_agent_count").Result()
    outMsg := processResource(in, cnt)
    out,_ := json.Marshal(outMsg)
    _ = nc.Publish("results.resource", out)
  })
  if err != nil { log.Fatal(err) }
  log.Println("resource-agent started")
  select{}
}
func getenv(k,d string) string { v:=os.Getenv(k); if v=="" {return d}; return v }
