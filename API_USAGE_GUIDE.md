# Grocery Intelligence API Usage Guide

## Start the API in the Multipass VM

From inside the VM:

```bash
cd /home/ubuntu/grocery-data-lake
grocery serve run-server --port 8000
```

The server binds to all VM interfaces:

```text
http://0.0.0.0:8000
```

Current VM address:

```text
http://192.168.2.4:8000/docs
```

## Access From Home Network

The Mac Studio is on:

```text
192.168.0.15
```

The Multipass VM is on:

```text
192.168.2.4
```

Because these are different subnets, home devices on `192.168.0.x` usually cannot reach `192.168.2.4` directly. Forward the API through the Mac.

On the Mac, install `socat` if needed:

```bash
brew install socat
```

Then run:

```bash
socat TCP-LISTEN:8000,fork,bind=0.0.0.0 TCP:192.168.2.4:8000
```

From any device on the home network, open:

```text
http://192.168.0.15:8000/docs
```

If port `8000` is already in use on the Mac, forward another Mac-side port:

```bash
socat TCP-LISTEN:18000,fork,bind=0.0.0.0 TCP:192.168.2.4:8000
```

Then open:

```text
http://192.168.0.15:18000/docs
```

## Check Whether Port 8000 Is In Use On Mac

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
```

If nothing prints, port `8000` is free.

## Core API Examples

Stats:

```bash
curl "http://192.168.0.15:8000/api/stats"
```

Search products:

```bash
curl "http://192.168.0.15:8000/api/products?q=brood&limit=5"
```

Product detail:

```bash
curl "http://192.168.0.15:8000/api/products/6401"
```

Categories:

```bash
curl "http://192.168.0.15:8000/api/categories"
```

Price history overview:

```bash
curl "http://192.168.0.15:8000/api/price-history"
```

## Analytics API Examples

Price metrics:

```bash
curl "http://192.168.0.15:8000/api/analytics/price-metrics?limit=10"
```

Unit prices:

```bash
curl "http://192.168.0.15:8000/api/analytics/unit-prices?unit=g&limit=10"
```

Category inflation:

```bash
curl "http://192.168.0.15:8000/api/analytics/category-inflation?limit=10"
```

Brand inflation:

```bash
curl "http://192.168.0.15:8000/api/analytics/brand-inflation?limit=10"
```

Bonus analytics by brand:

```bash
curl "http://192.168.0.15:8000/api/analytics/bonus?group_by=brand&limit=10"
```

## Dashboard-Ready Serving APIs

Refresh derived and serving tables first:

```bash
grocery jobs rebuild-derived
```

Then query:

```bash
curl "http://192.168.0.15:8000/api/analytics/serving/category-metrics?limit=10"
```

```bash
curl "http://192.168.0.15:8000/api/analytics/serving/brand-metrics?limit=10"
```

```bash
curl "http://192.168.0.15:8000/api/analytics/serving/bonus-metrics?group_by=brand&limit=10"
```

## Daily Pipeline

Run full scrape, rebuild derived tables, rebuild serving tables, and run health checks:

```bash
grocery jobs daily-snapshot
```

Run the same workflow without scraping:

```bash
grocery jobs daily-snapshot --skip-scrape
```

## Troubleshooting

If `http://192.168.0.15:8000/docs` does not open:

1. Confirm the API is running inside the VM.
2. Confirm `socat` is running on the Mac.
3. Confirm the Mac is still `192.168.0.15`.
4. Check whether macOS firewall is blocking inbound connections.
5. Try a different forwarded port, such as `18000`.

