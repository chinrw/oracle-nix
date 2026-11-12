{
  lib,
  buildNpmPackage,
  nodejs_24,
  makeWrapper,
  python3,
  coreutils,
  apiKeyFile ? null,
}:
let
  manifest = builtins.fromJSON (builtins.readFile ./package.json);
  keyLoader = lib.optionalString (apiKeyFile != null) ''
    if [ -z "''${OPENAI_API_KEY-}" ] && [ -r ${lib.escapeShellArg apiKeyFile} ]; then
      OPENAI_API_KEY="$(${coreutils}/bin/cat ${lib.escapeShellArg apiKeyFile})"
      export OPENAI_API_KEY
    fi
  '';
in
assert lib.assertMsg (
  apiKeyFile == null
  || (
    builtins.isString apiKeyFile
    && lib.hasPrefix "/" apiKeyFile
    && !(lib.hasPrefix "${builtins.storeDir}/" apiKeyFile)
  )
) "apiKeyFile must be an absolute runtime path string outside the Nix store";
buildNpmPackage {
  pname = "oracle";
  inherit (manifest) version;
  src = lib.fileset.toSource {
    root = ./.;
    fileset = lib.fileset.unions [
      ./package.json
      ./package-lock.json
    ];
  };
  nodejs = nodejs_24;
  npmDepsHash = lib.removeSuffix "\n" (builtins.readFile ./npm-deps-hash);
  dontNpmBuild = true;
  nativeBuildInputs = [ makeWrapper ];

  installPhase = ''
    runHook preInstall
    mkdir -p "$out/lib/oracle" "$out/bin"
    cp -r node_modules "$out/lib/oracle/"
    chmod -R u+w "$out/lib/oracle/node_modules/@steipete/oracle"
    patch -d "$out/lib/oracle/node_modules/@steipete/oracle" -p1 < ${./reasoning-defaults.patch}
    for command in oracle oracle-mcp; do
      entry="$command"
      if [ "$command" = oracle ]; then
        entry=oracle-cli
      fi
      makeWrapper ${nodejs_24}/bin/node "$out/bin/$command" \
        --add-flags "$out/lib/oracle/node_modules/@steipete/oracle/dist/bin/$entry.js" \
        --set-default NODE_USE_ENV_PROXY 1 \
        --set-default ORACLE_ENGINE api ${
          lib.optionalString (apiKeyFile != null) "--run ${lib.escapeShellArg keyLoader}"
        }
    done
    runHook postInstall
  '';

  doInstallCheck = true;
  nativeInstallCheckInputs = [ python3 ];
  installCheckPhase = ''
    runHook preInstallCheck
    python3 ${../tests/smoke.py} "$out" '${manifest.version}'
    python3 ${../tests/defaults.py} "$out"
    runHook postInstallCheck
  '';

  meta = {
    description = "CLI and MCP server for file-grounded model consultations";
    homepage = "https://github.com/steipete/oracle";
    license = lib.licenses.mit;
    mainProgram = "oracle";
    platforms = [
      "x86_64-linux"
      "aarch64-linux"
      "aarch64-darwin"
    ];
  };
}
