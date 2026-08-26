# AGENTS.md

## Repository Overview

This repo packages [tus](https://tus.io/) resumable-upload support for MOSIP.
`tusd` is the open-source Go server that implements the tus protocol
(`https://github.com/tus/tusd`). This repository does **not** contain a
from-scratch Go implementation — there is no Go source code here at all. It
is a thin deployment wrapper:

- A `Dockerfile` that starts `FROM tusproject/tusd:v1.8` (a mutable tag,
  not a digest pin, tracking the upstream vendored binary) and only adds
  build-metadata labels and an entrypoint.
- A Helm chart that deploys that image into a MOSIP Kubernetes cluster
  (Istio routing, config maps, PVC, service monitor, service account).
- Shell scripts under `deploy/tusd` that install/restart/delete the Helm
  release via `kubectl`/`helm`.

If you are looking for tus protocol logic (hooks, storage backends,
resumable-upload handling), that code lives upstream in `tus/tusd`, not in
this repository.

## Technology Stack

- **Runtime**: upstream `tusproject/tusd` Docker image, tagged `v1.8` in
  `tusd-server/Dockerfile` (Go binary, built by the tus project — not
  built from source here; the tag is mutable, not digest-pinned).
- **Containerization**: Docker (`tusd-server/Dockerfile`).
- **Deployment**: Helm 3 chart (`helm/tusd`), depending on the Bitnami
  `common` chart (`https://charts.bitnami.com/bitnami`, tag
  `bitnami-common`).
- **Cluster tooling**: `kubectl`, `helm`, Istio (`VirtualService`/`Gateway`
  templates gate on `.Values.istio.enabled`).
- **CI**: GitHub Actions, using MOSIP's shared reusable workflows from
  `mosip/kattu`.

## Build & Test Commands

There is no application source to compile — "build" here means building and
publishing the Docker image, which CI does for you. Locally you can still
build/inspect it:

```shell
docker build -t tusd-server:local ./tusd-server
```

Build the chart's dependencies (it declares Bitnami `common` as a
dependency; `helm/tusd/charts/` is not vendored/committed) before linting
or templating, otherwise both commands below fail:

```shell
helm dependency build ./helm/tusd
```

Lint the Helm chart before submitting chart changes:

```shell
helm lint ./helm/tusd
```

Render the chart templates to check output without installing:

```shell
helm template tusd-service ./helm/tusd
```

There are no unit/integration test suites in this repository (no `pom.xml`,
no `package.json`, no Go module). Do not invent test commands.

## Configuration

- `helm/tusd/values.yaml` holds the deployable defaults: image
  repository/tag, `containerPort` (1080), probes, persistence
  (`persistence.mountDir: /srv/tusd-hooks`, default `storageClass:
  longhorn`, `size: 8G`), and Istio routing (`istio.tusdPrefix: /files`).
- `helm/tusd/values.yaml` also sets `extraEnvVarsCM: [config-server-share]`,
  so most runtime configuration is expected to come from a
  cluster-provisioned ConfigMap, not hardcoded here.
- `helm/tusd/templates/configmaps.yaml` renders `.Values.configuration`
  (currently unset in `values.yaml`) into a `tusd.conf` file mounted into
  the pod — set `configuration:` in a values override if you need to ship a
  static `tusd.conf`.
- `deploy/tusd/copy_cm.sh` copies ConfigMaps (`global`, `artifactory-share`,
  `config-server-share`) from other namespaces into the `tusd` namespace
  before install, using a helper script fetched from
  `mosip/mosip-infra` (`copy_cm_func.sh`). It does not handle Secrets —
  there is no secret-copying step in this repo's scripts.
- Container environment variables `auth_url_env`
  (`http://authmanager.kernel`) and `key_url_env`
  (`http://keymanager.keymanager`) are hardcoded in
  `helm/tusd/templates/deployment.yaml`; change them there, not in
  `values.yaml`, if the in-cluster service names differ. These are plain
  `http://` in-cluster URLs — this repo/chart does not itself configure
  Istio `PeerAuthentication`/`DestinationRule` mTLS enforcement, so they
  are only as safe as the mesh-wide mTLS policy applied elsewhere in the
  cluster (typically in `istio-system`). Do not assume traffic is
  encrypted in transit unless you've confirmed that policy is in place.
- No `.env`, secrets file, or credentials file exists in this repository —
  do not add one. Do not commit real hostnames, tokens, or kubeconfigs into
  `values.yaml` or the `deploy/tusd` scripts.

## Project Structure Notes

```text
tusd-server/
  Dockerfile              # FROM tusproject/tusd:v1.8 (mutable tag), adds labels + entrypoint
deploy/tusd/
  README.md               # stub doc (copied from a print-service template)
  install.sh              # helm install of the tusd-service release
  restart.sh              # kubectl rollout restart for the tusd deployment
  delete.sh               # helm uninstall, with a Y/n confirmation prompt
  copy_cm.sh              # copies ConfigMaps into the tusd namespace pre-install
helm/tusd/
  Chart.yaml               # chart name "tusd", version 0.0.1-develop
  values.yaml               # all configurable defaults (see Configuration)
  templates/                # Deployment, Service, PVC, ConfigMap, Istio
                             # Gateway/VirtualService, ServiceMonitor, RBAC
.github/workflows/
  push-trigger.yml          # builds/pushes the Docker image (mosip/kattu reusable workflow)
  chart-lint-publish.yml    # lints/publishes the Helm chart to mosip-helm (gh-pages)
  release-changes.yml       # manual release/pre-release branch preparation
  tag.yml                   # manual repo tagging/release publishing
```

Notes on the above:

- Both `deploy/tusd/README.md` and `helm/tusd/README.md` are minimal;
  `deploy/tusd/README.md` in particular still reads "MOSIP Print Service"
  and describes it as a sample/reference service — treat that wording as
  boilerplate left over from another repo, not as accurate documentation of
  what tusd does.
- The root `README.md` is a single line (`# tusd`) — there is no top-level
  narrative documentation beyond this file.
- The chart's `version` in `Chart.yaml` (`0.0.1-develop`) and the version
  pinned in `deploy/tusd/install.sh`/`restart.sh` (`CHART_VERSION=0.0.1-develop`)
  must be kept in sync manually; there is no automation tying them together.
  Check for drift with:

  ```shell
  rg -n '^(version:|CHART_VERSION=)' helm/tusd/Chart.yaml deploy/tusd/install.sh deploy/tusd/restart.sh
  ```

## Development Workflow

1. Fork the repository and clone your fork.
2. Add the upstream remote and fetch `develop` (this repo's active
   integration branch — the reported "default" branch is `master`, but
   ongoing work happens on `develop`):

   ```shell
   git remote add upstream https://github.com/mosip/tusd-server.git
   git fetch upstream develop
   git checkout -b my-change upstream/develop
   ```

3. Make your change:
   - Dockerfile/image changes: verify the tag against
     `https://hub.docker.com/r/tusproject/tusd/tags` before updating
     `tusd-server/Dockerfile`'s `FROM tusproject/tusd:<tag>` line, and, if
     the container entrypoint/port changes, `helm/tusd/values.yaml`
     (`containerPort`) and `helm/tusd/templates/deployment.yaml` in
     tandem.
   - Helm chart changes: run `helm lint ./helm/tusd` and
     `helm template tusd-service ./helm/tusd` locally before pushing.
   - Deploy-script changes: keep `deploy/tusd/install.sh`,
     `restart.sh`, and `delete.sh` consistent in namespace (`tusd`) and
     release name (`tusd-service`).
4. Push to your fork and open a pull request against `mosip/tusd-server`'s
   `develop` branch (not `master`).

## Pull Request Guidelines

- Target `develop`, not `master`.
- Docker image pushes are triggered automatically by
  `.github/workflows/push-trigger.yml` on pull requests and on pushes to
  `develop`, `master`, `MOSIP*`, and `1.*` branches (via the reusable
  `mosip/kattu` `docker-build.yml` workflow) — you do not need to publish
  the image yourself.
- Helm chart linting/publishing
  (`.github/workflows/chart-lint-publish.yml`) runs on pull requests that
  touch `helm/**`, and on pushes to `develop`/`MOSIP*`/`release*`/version
  branches that touch `./helm/**`. Changes outside `helm/` will not trigger
  this workflow.
- There is no CI gate that lints Markdown or shell scripts in this repo;
  reviewers check those changes manually.
- Follow MOSIP's usual commit sign-off convention (`git commit -s`) so the
  DCO check some MOSIP org workflows expect is satisfied.

## Repository-Specific Considerations

- This is a deployment/config repository, not an application repository —
  most "development" here is editing YAML/shell, not writing Go, Java, or
  JS code.
- Because the runtime binary is pulled from `tusproject/tusd`, functional
  bugs in the tus protocol handling itself belong upstream in
  `tus/tusd`, not in this repo. Only file issues/PRs here for MOSIP's
  Docker/Helm/deploy-script wrapping.
- `deploy/tusd/delete.sh` is interactive (prompts `Are you sure you want to
  delete tusd helm chart?(Y/n)`) — it will hang if run non-interactively
  without piping an answer in.
- Chart version bumps in `helm/tusd/Chart.yaml` are not automatic; remember
  to bump `version` when the chart's rendered output changes, since
  `chart-lint-publish.yml` publishes chart versions to the `mosip-helm`
  `gh-pages` repository.

## Agent rules

### Do

1. Verify any Docker tag or Helm chart version change against the actual
   upstream registry/chart before proposing it — do not guess version
   numbers.
2. Keep `helm/tusd/values.yaml`, `helm/tusd/templates/deployment.yaml`, and
   the `deploy/tusd/*.sh` scripts consistent (namespace `tusd`, release
   name `tusd-service`, chart version) when changing any one of them.
3. Run `helm lint ./helm/tusd` (and `helm template` to sanity-check
   rendered output) after editing anything under `helm/tusd`.
4. Target the `develop` branch for pull requests, and use `git commit -s`
   to sign off commits.
5. Treat `deploy/tusd/README.md`'s "Print Service" wording as stale
   boilerplate — do not copy it forward or treat it as a source of truth
   about what this repo does.

### Do not

1. Do not add or edit Go source in this repository to "implement" tus
   protocol behavior — the server binary is vendored from
   `tusproject/tusd`; protocol-level changes belong upstream.
2. Do not commit real hostnames, tokens, kubeconfigs, or other secrets into
   `values.yaml` or the `deploy/tusd` scripts; there is no secrets file in
   this repo to add them to, and none should be created.
3. Do not assume CI lints Markdown, shell scripts, or non-`helm/`
   changes — only Docker image builds and `helm/**`-scoped changes are
   covered by the workflows in `.github/workflows`.
4. Do not target `master` for pull requests even though GitHub reports it
   as the default branch — active development happens on `develop`.
5. Do not run `deploy/tusd/delete.sh` unattended in automation without
   accounting for its interactive `Y/n` confirmation prompt.
