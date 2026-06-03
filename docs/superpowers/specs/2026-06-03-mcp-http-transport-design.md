# MCP Dual Transport With Nginx-Authenticated HTTP Proxy

## Summary

LLMBase will support two MCP transports:

- `stdio`, the default transport, intended for local MCP clients that launch `llmbase mcp` directly.
- `streamable-http`, intended for HTTP access behind an Nginx reverse proxy on the same host, exposed at `/mcp`.

The HTTP mode will use a dedicated MCP service, separate from the main `llmbase` web service and worker. Nginx will always enforce `X-API-Key` against `MCP_API_KEY` before forwarding `/mcp` traffic to the MCP upstream. The MCP server itself will not implement HTTP authentication.

Configuration will be available from both `.env` and CLI flags, with precedence `CLI > env > defaults`. Backward compatibility with the current `stdio` behavior is not required; the command surface may change if needed for a cleaner transport model.

## Goals

- Support MCP over both `stdio` and `streamable-http`.
- Keep the MCP tool surface generated from `llmwiki.operations.py`.
- Expose MCP HTTP on the same public host as the existing app, under `/mcp`.
- Enforce HTTP authentication at the Nginx proxy only.
- Support both Docker Compose deployment and manual local startup.
- Keep the local default path straightforward without requiring a fully specified upstream URL.

## Non-Goals

- Implement authentication inside the MCP upstream service.
- Move MCP traffic through the main `llmbase` Flask app as an application-layer proxy.
- Introduce a separate public host or public port for MCP.
- Add fallback behavior that silently switches between transports when configuration is invalid.

## Alternatives Considered

### 1. Dedicated MCP HTTP service behind Nginx

Recommended.

This keeps authentication and edge concerns in Nginx, while the MCP runtime stays focused on protocol handling and operation dispatch. It fits the repository's existing Nginx and Compose topology and supports both containerized and manual startup.

### 2. Internal Python proxy inside LLMBase

Rejected.

This would reduce the number of runtime components, but it would mix application logic with reverse proxy responsibilities and blur the requirement that `X-API-Key` validation happens at the proxy.

### 3. Proxy only to a fully external MCP URL

Rejected as the default path.

Keeping `MCP_HTTP_URL` as an override is useful, but requiring it for normal local or Compose use would make the common path harder to operate and document.

## Architecture

The implementation will have two MCP runtime modes:

- `stdio`: `llmbase mcp` launches the MCP server and communicates directly over standard input and output.
- `streamable-http`: `llmbase mcp` launches an HTTP MCP server listening on an internal address and port.

For HTTP mode, a dedicated MCP process or Compose service will run separately from `llmbase` and `llmbase-worker`. Nginx will expose `/mcp` on the same public host already used by the UI and HTTP API, validate `X-API-Key`, and proxy matching requests to the MCP upstream.

The MCP upstream remains unaware of HTTP authentication. Security for HTTP access is defined entirely at the Nginx edge.

## Components

### MCP runtime

`llmwiki/mcp_server.py` will remain the protocol entrypoint and continue to derive its tool surface from `llmwiki.operations`. It will gain transport-aware startup so the same runtime can be launched in either `stdio` or `streamable-http` mode.

### CLI entrypoint

`llmwiki/cli.py` will expose MCP transport selection and HTTP overrides through CLI flags. Expected inputs include transport selection, HTTP listen port, and complete upstream URL override where needed.

### MCP config resolver

A small resolver layer will normalize configuration from CLI flags, environment variables, and defaults. It will read:

- `MCP_TRANSPORT`
- `MCP_HTTP_PORT`
- `MCP_HTTP_URL`
- `MCP_API_KEY`

The effective precedence will be `CLI > env > defaults`.

### Dedicated MCP service

Compose will gain a dedicated MCP service separate from `llmbase` and `llmbase-worker`. Manual startup outside Docker will use the same runtime entrypoint and configuration contract.

### Nginx proxy

`nginx/nginx.conf` will add a dedicated `/mcp` location. That location will:

- require `X-API-Key`
- compare it against `MCP_API_KEY`
- reject unauthorized requests without forwarding upstream
- proxy authorized requests to the configured MCP HTTP upstream

### Documentation

`docs/mcp-server.md` will be updated to describe both transports, `.env` variables, CLI overrides, the Compose topology, and the same-host `/mcp` reverse proxy path.

## Configuration Contract

The MCP environment variables are:

- `MCP_TRANSPORT`: `stdio` or `streamable-http`, default `stdio`
- `MCP_HTTP_PORT`: local listen port for the MCP HTTP service, default `8100`
- `MCP_HTTP_URL`: optional full upstream URL override used by the proxy target selection
- `MCP_API_KEY`: shared secret validated by Nginx against incoming `X-API-Key`

CLI flags will override environment values. The CLI contract is:

```bash
llmbase mcp --transport streamable-http --http-port 8100
```

The supported MCP CLI flags are:

- `--transport`
- `--http-port`
- `--http-url`

## Runtime Flow

### stdio flow

1. An MCP client launches `llmbase mcp`.
2. The command resolves the effective transport as `stdio`.
3. The MCP runtime starts over standard input and output.
4. Tool requests dispatch through `llmwiki.operations` exactly as they do today.

### streamable-http flow

1. The MCP process starts in `streamable-http` mode.
2. It binds to the configured internal address and port.
3. Nginx exposes `/mcp` on the same public host as the rest of the application.
4. A client sends an HTTP MCP request to `/mcp` with `X-API-Key`.
5. Nginx validates `X-API-Key` against `MCP_API_KEY`.
6. If validation succeeds, Nginx proxies the request to the MCP upstream.
7. The MCP upstream handles the request and dispatches the selected tool through `llmwiki.operations`.

If `MCP_HTTP_URL` is not set, the deployment uses the standard local upstream target derived from the dedicated MCP service and configured port. If `MCP_HTTP_URL` is set, that full URL replaces the default upstream target.

## Error Handling

- Invalid `MCP_TRANSPORT` values cause immediate startup failure with an explicit allowed-values message.
- Invalid or unavailable HTTP listen ports cause startup failure in `streamable-http` mode.
- No implicit fallback to another transport occurs after configuration errors.
- Requests to `/mcp` without `X-API-Key`, or with a non-matching key, are rejected by Nginx before proxying.
- If the MCP upstream is unavailable, the proxy returns a clear gateway error.
- Malformed `MCP_HTTP_URL` values fail explicitly rather than being corrected silently.
- Sensitive values such as `MCP_API_KEY` must never be emitted in logs.

## Testing Strategy

Implementation should cover the following checks:

- unit tests for transport configuration resolution and precedence
- unit tests for invalid transport and invalid HTTP config paths
- CLI tests for `llmbase mcp` in both `stdio` and `streamable-http` modes
- HTTP startup tests for the MCP runtime in `streamable-http` mode
- targeted integration or smoke tests verifying Nginx `/mcp` rejection and success paths based on `X-API-Key`
- regression coverage confirming the `stdio` flow still works for local MCP clients

The minimum mandatory automated coverage is the Python-side config and bootstrap tests. Nginx coverage can be satisfied with focused smoke or integration checks rather than a large infrastructure-heavy suite.

## Implementation Notes

- The public tool contract remains `llmwiki.operations.py`.
- The HTTP implementation should favor current MCP Python SDK support for streamable HTTP rather than building a custom protocol layer.
- The MCP upstream should bind only to an internal network or local interface in HTTP mode.
- Compose support and manual local startup must share the same env and CLI contract so documentation stays consistent.

## Open Decisions Resolved By This Spec

- Proxy technology: Nginx
- Public exposure: same host, path `/mcp`
- HTTP auth location: always at the proxy
- Supported runtimes: Docker Compose and manual local startup
- Config inputs: both `.env` and CLI overrides
- Transport model: `stdio` and `streamable-http`
- Backward compatibility constraint: no requirement to preserve the current default behavior exactly if a cleaner interface is needed