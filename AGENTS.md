# AGENTS.md

## Repository Overview

Deployment wrapper for [tus](https://tus.io/) resumable uploads in MOSIP — **no Go source here**. tus protocol logic (hooks, storage, upload handling) lives upstream in `tus/tusd`; only file issues/PRs here for the Docker/Helm/deploy-script wrapping.

- `Dockerfile`: `FROM tusproject/tusd:v1.8` (mutable tag, not digest-pinned), adds labels + entrypoint only.
- `helm/tusd`: Helm chart deploying that image (Istio routing, ConfigMaps, PVC, ServiceMonitor, service account).
- `deploy/tusd/*.sh`: install/restart/delete the Helm release via `kubectl`/`helm`.

## Technology Stack

- Containerization: Docker. Deployment: Helm 3 (`helm/tusd`), depends on Bitnami `common` (not vendored — build it, see below).
- Cluster tooling: `kubectl`, `helm`, Istio (`VirtualService`/`Gateway` gated on `.Values.istio.enabled`).
- CI: GitHub Actions via MOSIP's reusable `mosip/kattu` workflows.

## Build & Test Commands

No app source to compile — CI builds/publishes the Docker image. Locally:

```shell
docker build -t tusd-server:local ./tusd-server
```

Build chart deps first (required before lint/template, `helm/tusd/charts/` isn't committed):

```shell
helm dependency build ./helm/tusd
helm lint ./helm/tusd
helm template tusd-service ./helm/tusd
```

No test suites exist (no `pom.xml`/`package.json`/Go module) — don't invent test commands.

## Configuration

- `helm/tusd/values.yaml`: image repo/tag, `containerPort` (1080), probes, persistence (`persistence.mountDir: /srv/tusd-hooks`, `storageClass: longhorn`, `size: 8G`), Istio (`istio.tusdPrefix: /files`). `extraEnvVarsCM: [config-server-share]` means most runtime config comes from a cluster ConfigMap, not this file.
- `helm/tusd/templates/configmaps.yaml` renders `.Values.configuration` (unset by default) into `tusd.conf` — set it in a values override to ship a static config.
- `deploy/tusd/copy_cm.sh` copies ConfigMaps (`global`, `artifactory-share`, `config-server-share`) into the `tusd` namespace pre-install (via `mosip-infra`'s `copy_cm_func.sh`). No Secrets handling exists — don't add a secrets file; don't commit real hostnames/tokens/kubeconfigs into `values.yaml` or `deploy/tusd` scripts.
- `auth_url_env`/`key_url_env` are hardcoded plain `http://` URLs in `helm/tusd/templates/deployment.yaml` (not `values.yaml`) — this chart doesn't configure mTLS itself; traffic is only as encrypted as the mesh-wide Istio policy applied elsewhere (typically `istio-system`). Don't assume encryption in transit.

## Project Structure Notes

```text
tusd-server/
  Dockerfile              # FROM tusproject/tusd:v1.8 (mutable tag), adds labels + entrypoint
deploy/tusd/
  install.sh / restart.sh / delete.sh / copy_cm.sh
helm/tusd/
  Chart.yaml               # name "tusd", version 0.0.1-develop
  values.yaml               # see Configuration
  templates/                # Deployment, Service, PVC, ConfigMap, Istio Gateway/VirtualService, ServiceMonitor, RBAC
.github/workflows/
  push-trigger.yml          # builds/pushes the Docker image
  chart-lint-publish.yml    # lints/publishes the Helm chart (gh-pages)
  release-changes.yml / tag.yml   # manual release/tagging
```

- `deploy/tusd/README.md` still reads "MOSIP Print Service" — stale boilerplate from another repo's template, not accurate. Root `README.md` is a single line.
- `Chart.yaml`'s `version` and `CHART_VERSION=` in `install.sh`/`restart.sh` must be kept in sync manually — check drift with:
  ```shell
  rg -n '^(version:|CHART_VERSION=)' helm/tusd/Chart.yaml deploy/tusd/install.sh deploy/tusd/restart.sh
  ```

## Pull Request Guidelines

- Target `develop`, not `master` (GitHub reports `master` as default, but active work happens on `develop`).
- `push-trigger.yml` builds/pushes the Docker image automatically on PRs and on pushes to `develop`/`master`/`MOSIP*`/`1.*` — don't publish it yourself.
- `chart-lint-publish.yml` only triggers on changes under `helm/**`. No CI lints Markdown or shell scripts — reviewers check those manually.
- Sign off commits (`git commit -s`) for DCO.

## Agent rules

### Do

1. Verify any Docker tag or Helm chart version change against the actual upstream registry/chart before proposing it (`https://hub.docker.com/r/tusproject/tusd/tags`) — don't guess.
2. Keep `values.yaml`, `templates/deployment.yaml`, and `deploy/tusd/*.sh` consistent (namespace `tusd`, release `tusd-service`, chart version) when changing any one.
3. Run `helm lint`/`helm template` after editing anything under `helm/tusd`, and bump `Chart.yaml`'s `version` if rendered output changes.

### Do not

1. Do not add Go source to "implement" tus protocol behavior here — that's upstream in `tusproject/tusd`.
2. Do not commit secrets/hostnames/tokens/kubeconfigs anywhere in this repo.
3. Do not target `master` for PRs, or assume CI lints anything outside Docker builds and `helm/**` changes.
4. Do not run `deploy/tusd/delete.sh` unattended — it has an interactive `Y/n` confirmation prompt and will hang without one.
5. Do not treat `deploy/tusd/README.md`'s "Print Service" wording as accurate.
