{
  lib,
  buildNpmPackage,
  nodejs_24,
  makeWrapper,
  python3,
}:
let
  manifest = builtins.fromJSON (builtins.readFile ./package.json);
in
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
    for command in oracle oracle-mcp; do
      entry="$command"
      if [ "$command" = oracle ]; then
        entry=oracle-cli
      fi
      makeWrapper ${nodejs_24}/bin/node "$out/bin/$command" \
        --add-flags "$out/lib/oracle/node_modules/@steipete/oracle/dist/bin/$entry.js" \
        --set-default ORACLE_ENGINE api
    done
    runHook postInstall
  '';

  doInstallCheck = true;
  nativeInstallCheckInputs = [ python3 ];
  installCheckPhase = ''
    runHook preInstallCheck
    python3 ${../tests/smoke.py} "$out" '${manifest.version}'
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
