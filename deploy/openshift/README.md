# ChoreSync — OpenShift Deployment

## Prerequisites
- `oc` CLI installed and logged in to your cluster
- Docker / Podman to build the image
- A project (namespace) created: `oc new-project choresync`

---

## 1. Build and push the image

OpenShift has an internal registry. Expose it first (one-time, admin may need to do this):
```bash
oc patch configs.imageregistry.operator.openshift.io/cluster --patch '{"spec":{"defaultRoute":true}}' --type=merge
```

Log Docker into the registry and build:
```bash
REGISTRY=$(oc get route default-route -n openshift-image-registry --template='{{ .spec.host }}')
docker login -u $(oc whoami) -p $(oc whoami -t) $REGISTRY

cd backend/
docker build -t $REGISTRY/<YOUR_NAMESPACE>/choresync:latest .
docker push $REGISTRY/<YOUR_NAMESPACE>/choresync:latest
```

Replace `<YOUR_NAMESPACE>` with your OpenShift project name (e.g. `choresync`).
Then update the `image:` field in all three deployment files to match.

---

## 2. Configure secrets

Edit `secret.yaml` and fill in every `<REPLACE_ME>` value.

Once filled in, apply it:
```bash
oc apply -f secret.yaml
```

Do NOT commit `secret.yaml` with real values to git.

---

## 3. Apply everything

```bash
oc apply -f pvc-media.yaml
oc apply -f service.yaml
oc apply -f route.yaml
oc apply -f deployment-web.yaml
oc apply -f deployment-worker.yaml
oc apply -f deployment-beat.yaml
```

Or apply the whole directory at once:
```bash
oc apply -f .
```

---

## 4. Get your URL

```bash
oc get route choresync
```

Copy the HOST value and put it in `secret.yaml` as `ALLOWED_HOSTS`, then redeploy:
```bash
oc rollout restart deployment/choresync-web
```

---

## 5. Seed badges (one-time)

```bash
oc exec deployment/choresync-web -- python manage.py loaddata badges.json
```

---

## Useful commands

```bash
# View logs
oc logs deployment/choresync-web -f
oc logs deployment/choresync-worker -f
oc logs deployment/choresync-beat -f

# Open a shell in the running container
oc exec -it deployment/choresync-web -- /bin/sh

# Force a fresh deploy after pushing a new image
oc rollout restart deployment/choresync-web deployment/choresync-worker deployment/choresync-beat

# Check pod status
oc get pods
```

---

## Redis and Postgres

If your uni's OpenShift subscription includes a service catalog, you can provision
Postgres and Redis directly from the console under **+Add → From Catalog**.

The service names will become your hostnames:
- `DATABASE_URL=postgres://user:pass@postgresql:5432/choresync`
- `CELERY_BROKER_URL=redis://redis:6379/0`

Otherwise use an external DB (Supabase free tier for Postgres, Upstash for Redis).
