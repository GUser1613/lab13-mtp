FROM golang:1.22-alpine AS build
WORKDIR /src
COPY . .
RUN go mod tidy && go build -o app main.go
FROM alpine:3.20
WORKDIR /app
COPY --from=build /src/app .
CMD ["/app/app"]
