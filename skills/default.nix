{
  lib,
  stdenvNoCC,
  fetchzip,
}:
let
  manifest = builtins.fromJSON (builtins.readFile ../package/package.json);
  source = builtins.fromJSON (builtins.readFile ../package/skill-source.json);
in
assert lib.assertMsg (
  source.version == manifest.version
) "Oracle CLI and skill source versions must match";
stdenvNoCC.mkDerivation {
  pname = "oracle-advisor";
  inherit (manifest) version;
  src = fetchzip { inherit (source) url hash; };
  dontBuild = true;
  installPhase = ''
    runHook preInstall
    test -f skills/oracle-advisor/SKILL.md
    grep -Fx 'name: oracle-advisor' skills/oracle-advisor/SKILL.md
    mkdir -p "$out"
    cp -r skills/oracle-advisor/. "$out/"
    cp LICENSE "$out/LICENSE"
    runHook postInstall
  '';
  meta = {
    description = "Upstream Oracle advisor skill for coding agents";
    homepage = "https://github.com/steipete/oracle/tree/v${manifest.version}/skills/oracle-advisor";
    license = lib.licenses.mit;
    platforms = lib.platforms.unix;
  };
}
