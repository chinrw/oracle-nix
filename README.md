# oracle-nix

Install the Oracle CLI and MCP server with Nix, using a locked npm release and dependency hash. The package provides `oracle` and `oracle-mcp` and defaults to the API engine. It does not install skills, register MCP clients, decrypt secrets or start a service.

## Build and run

From this checkout:

```sh
nix build
./result/bin/oracle --version
nix run . -- --help
nix run .#oracle-mcp
```

The declared build targets are x86_64 Linux, aarch64 Linux and Apple Silicon macOS. Builds run offline CLI, material-preview and MCP checks; they do not call a model or open a browser. `package/package.json` is the version source of truth.

For API calls, provide `OPENAI_API_KEY` at runtime. Keep it out of Nix expressions and the store. `--engine` can explicitly override the wrapper's API default. Model, reasoning mode and effort remain Oracle CLI options.

## Home Manager

Use `github:chinrw/oracle-nix` as a flake input:

```nix
inputs.oracle-nix = {
  url = "github:chinrw/oracle-nix";
  inputs.nixpkgs.follows = "nixpkgs";
};
```

Import the module into the selected Home Manager configuration:

```nix
{
  imports = [ inputs.oracle-nix.homeManagerModules.default ];
  programs.oracle.enable = true;
}
```

### Runtime API key files and sops-nix

The module accepts a runtime file path. sops-nix owns decryption and file permissions; Oracle reads the resulting file when it starts:

```nix
{ config, ... }:
{
  sops.secrets.openai-api-key = {
    sopsFile = ./secrets/openai.yaml;
    key = "api_key";
  };
  programs.oracle = {
    enable = true;
    apiKeyFile = config.sops.secrets.openai-api-key.path;
  };
}
```

Import and configure sops-nix in the consuming Home Manager configuration. This flake does not need a sops input and does not take ownership of age keys or encryption recipients. Other secret managers can supply the same runtime path.

`apiKeyFile` defaults to null and must be an absolute string outside the Nix store, not a Nix path literal or a `builtins.readFile` result. Only the path enters the store; the file is read by the `oracle` and `oracle-mcp` launchers. A nonempty caller-exported `OPENAI_API_KEY` wins. If the optional file is missing or unreadable, Oracle retains its usual credential handling, so help and browser-only use remain available. Once the launcher has loaded the host key into the environment, an unexported cwd `.env` cannot override it.

Package consumers can also use `oracle.override { apiKeyFile = "/run/secrets/openai-api-key"; }`. A custom `programs.oracle.package` must support this override when `apiKeyFile` is set.

The module builds against the consumer's `pkgs`. `programs.oracle.package` can override that package. For consumers that prefer an overlay, `overlays.default` exposes `pkgs.oracle`; direct flake consumers can use `packages.<system>.oracle` or `.default`.

## Updates

Check npm without modifying the checkout:

```sh
nix develop -c python3 scripts/update.py --check
```

Prepare the current stable npm release and verify it locally:

```sh
nix develop -c python3 scripts/update.py
nix flake check --print-build-logs
```

`--version 0.23.0` selects a particular stable release. `--refresh` resolves and hashes dependencies even when the version is unchanged. The updater preserves the existing lock where npm can reuse it; failed metadata resolution or dependency hashing leaves the repository files unchanged. It does not commit, push, update nixpkgs or deploy a machine.

The scheduled workflow checks npm every hour at minute 41, subject to GitHub scheduling delays. It prepares one candidate patch and tests that exact patch on all three declared targets. Preparation and validation have only `contents: read`; only the final publication job receives `contents: write`.

After every target succeeds, publication applies the same candidate on its original base, verifies main has not advanced, then creates a signed-off commit and pushes without force. Publication only runs for the main branch. If main changed, the next scheduled run must prepare a new candidate; untested rebases are not published. The workflow uses the repository GITHUB_TOKEN and needs permission to update main. No OpenAI or binary-cache secret is required.

A downstream `nix flake update` follows a wrapper commit only after it is published. Home Manager must still be activated to install the new version. Updating a lock alone does not change a running user environment. This repository does not publish a binary cache; downstream builders can cache their normal builds.

## Development checks

```sh
nix develop -c python3 -m unittest discover -s tests -v
nix develop -c actionlint
nix fmt -- --check flake.nix package/default.nix
nix flake check --print-build-logs
```

`tests/smoke.py` checks the installed version, CLI help, file rendering, API parameter preview and an MCP initialize/list-tools/sessions exchange. The updater tests cover no-change behavior, check-only mode, resolution failure, hash failure and a complete candidate update.

Upstream Oracle source and documentation: https://github.com/steipete/oracle.
