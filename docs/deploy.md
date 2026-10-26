# Deploy Lensor with Dokploy

This guide puts Lensor on your own server with [Dokploy](https://dokploy.com). Dokploy runs the
same Compose file that you use on your laptop, and it gives the site an HTTPS certificate.

## Before you start

- A server with Dokploy installed, and a domain that points to the server.
- An OpenRouter API key for production only. Do not use your development key.
- An S3-compatible bucket for the database backups.

## 1. Set a credit limit on the OpenRouter key

> **Warning:** The demo is public. Without a limit, a person can run up a large bill.

1. On openrouter.ai, open **Keys** and select the production key.
2. Set a credit limit of $10 for each month.

## 2. Create the Compose app

1. In Dokploy, create a project, then a **Compose** service.
2. Set the provider to the public GitHub repository and the branch to `main`.
3. Set the Compose path to `docker-compose.yml`.

> **Caution:** `docker-compose.override.yml` publishes host ports for local work. Make sure that
> Dokploy runs only `docker-compose.yml`. After the first deploy, run `docker ps` on the server and
> make sure that no Lensor container publishes port 5432, 6333, 8000, or 8080.

## 3. Set the environment

In the **Environment** tab, set each key of `.env.example`. Use these values on the server:

| Key | Value |
| --- | --- |
| `OPENROUTER_API_KEY` | The production key from step 1 |
| `POSTGRES_PASSWORD` | A long random value, for example from `openssl rand -hex 24` |
| `VECTOR_STORE` | `pgvector` |

> **Caution:** Postgres reads `POSTGRES_PASSWORD` only when it creates the volume. To change the
> password later, change it in Postgres first, then in Dokploy.

Keep the other keys at their values in `.env.example`.

## 4. Attach the domain

1. In the **Domains** tab, add your domain.
2. Set the service to `web` and the port to `80`.
3. Turn on HTTPS. Dokploy gets the certificate.

The `web` container serves the app and sends `/api` to the `api` container.

## 5. Deploy and load the demo contracts

1. Select **Deploy**. Wait until the `api` container is healthy.
2. Open a terminal in the `api` container and load the CUAD data and the demo set:

   ```bash
   python - <<'PY'
   import io, urllib.request, zipfile
   data = urllib.request.urlopen("https://github.com/TheAtticusProject/cuad/raw/main/data.zip").read()
   zipfile.ZipFile(io.BytesIO(data)).extract("CUADv1.json", "/tmp/cuad")
   PY
   python -m lensor.ingest.load_cuad --set demo --json /tmp/cuad/CUADv1.json
   ```

   Expected: 50 lines that start with `ready`. The run costs less than $1.

## 6. Back up the database every day

1. In Dokploy, open **Settings**, then **S3 Destinations**, and add your bucket.
2. Open the `postgres` service, then **Backups**, and add a daily backup to that bucket.
3. Run the backup one time by hand and make sure that the file is in the bucket.

## 7. Check the deploy

1. Open `https://<your domain>/api/health`. Expected: `{"status":"ok"}`.
2. Send 25 quick questions. Expected: at least one `429` response, because the limit is 20 for
   each minute for each client address.

   ```bash
   for i in $(seq 25); do
     curl -s -o /dev/null -w "%{http_code}\n" -X POST "https://<your domain>/api/chat" \
       -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"hi"}]}'
   done | sort | uniq -c
   ```

   > **Caution:** Each `200` response calls the agent model and costs a small amount.

3. Open the site. Upload `web/public/sample-contract.txt` and make sure that the viewer opens.
