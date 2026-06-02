# Config Bind Mount Design

> For agentic workers: after this spec is approved by the user, the next step is to use the writing-plans skill to create the implementation plan. Do not implement directly from this document.

## Goal

Make `config.yaml` a single runtime configuration source managed on the host filesystem and mounted read-only into the Dockerized `llmbase` and `llmbase-worker` services, so local configuration changes no longer require rebuilding the image.

## Scope

This design covers only the Docker packaging and Compose runtime wiring for `config.yaml`.

In scope:

- remove the baked-in `config.yaml` copy from the image build
- mount the host `./config.yaml` file into `/app/config.yaml` for `llmbase`
- mount the host `./config.yaml` file into `/app/config.yaml` for `llmbase-worker`
- apply the same behavior to both `docker-compose.yml` and `compose.build.yaml`
- keep the mount read-only inside the containers
- update surrounding comments where needed so the runtime expectation is explicit

Out of scope:

- application-level config hot reload
- changing how `llmbase` discovers its config path
- introducing fallback config paths or environment-based config indirection
- changing `.env` handling

## Recommended Approach

Use bind mounts in both Compose files and remove `config.yaml` from the Docker build context copy step.

This keeps one source of truth for runtime configuration, avoids stale config baked into images, and keeps the change small. It also matches the existing deployment style where `raw/` and `wiki/` are already host-mounted runtime assets.

## Alternatives Considered

### 1. Keep a fallback `config.yaml` inside the image

Rejected because it preserves two possible runtime config sources and weakens the operational contract. The user explicitly wants the host-mounted file to be the authoritative version.

### 2. Add an environment variable for a custom config path

Rejected because it adds flexibility without solving a real requirement. The existing runtime already expects `/app/config.yaml`, so mounting directly there is simpler and easier to reason about.

### 3. Mount only in `compose.build.yaml`

Rejected because it creates inconsistent behavior between local build-based and registry-image deployments. Both Compose entry points should behave the same way.

## File Changes

### `Dockerfile`

- remove `config.yaml` from the `COPY` instruction that stages application files into `/app`
- keep the rest of the image build unchanged

Result: the image no longer contains a project config fallback.

### `docker-compose.yml`

- add `./config.yaml:/app/config.yaml:ro` to `llmbase.volumes`
- add `./config.yaml:/app/config.yaml:ro` to `llmbase-worker.volumes`
- update nearby comments if necessary to make the host-side config requirement explicit

### `compose.build.yaml`

- add `./config.yaml:/app/config.yaml:ro` to `llmbase.volumes`
- add `./config.yaml:/app/config.yaml:ro` to `llmbase-worker.volumes`
- update nearby comments if necessary to make the host-side config requirement explicit

## Runtime Behavior

At runtime, both application services read the same mounted file from `/app/config.yaml`.

Operational contract:

- `config.yaml` must exist on the host next to the Compose files
- changing `config.yaml` on the host does not require rebuilding the image
- changes take effect after restarting the affected containers
- the containers cannot modify the mounted config because the mount is read-only

## Failure Modes

The system should fail fast when the config file is unavailable or invalid.

Expected outcomes:

- if `./config.yaml` is missing, Compose startup should fail instead of silently using a stale embedded file
- if `config.yaml` content is invalid, container startup should fail the same way it would today when reading a bad config
- `nginx` is unaffected because it does not read the application config file

This failure mode is intentional because it makes configuration problems visible early.

## Testing Strategy

Validation should stay focused on packaging and runtime wiring:

1. run `docker compose config` and confirm both `llmbase` and `llmbase-worker` resolve the read-only bind mount for `/app/config.yaml`
2. run `docker compose -f compose.build.yaml config` and confirm the same mount resolution there
3. inspect the final diff to confirm `Dockerfile` no longer copies `config.yaml`

No application test changes are required because the runtime config path is unchanged.

## Risks And Mitigations

- Risk: operators forget to keep `config.yaml` present beside the Compose files.
  Mitigation: document the expectation in Compose comments and rely on fail-fast startup.

- Risk: users expect config edits to apply immediately.
  Mitigation: keep the operational guidance explicit that a container restart is required.

## Acceptance Criteria

- `Dockerfile` does not copy `config.yaml` into the image
- `docker-compose.yml` mounts `./config.yaml` read-only into `/app/config.yaml` for both application services
- `compose.build.yaml` mounts `./config.yaml` read-only into `/app/config.yaml` for both application services
- runtime configuration is sourced from the host-mounted file instead of a baked image file
- Compose config rendering shows the expected mounts