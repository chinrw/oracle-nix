{
  pkgs,
  module,
  skill,
}:
let
  inherit (pkgs) lib;
  evaluate =
    settings:
    lib.evalModules {
      specialArgs = { inherit pkgs; };
      modules = [
        module
        {
          options.home.packages = lib.mkOption {
            type = lib.types.listOf lib.types.package;
            default = [ ];
          };
          options.home.file = lib.mkOption {
            type = lib.types.attrsOf lib.types.anything;
            default = { };
          };
        }
        { programs.oracle = settings; }
      ];
    };
  disabled = (evaluate { enable = true; }).config;
  enabled =
    (evaluate {
      enable = true;
      skills.enable = true;
    }).config;
  parentDisabled = (evaluate { skills.enable = true; }).config;
in
assert disabled.home.file == { };
assert parentDisabled.home.file == { };
assert
  builtins.attrNames enabled.home.file == [
    ".agents/skills/oracle-advisor"
    ".claude/skills/oracle-advisor"
  ];
assert toString enabled.home.file.".agents/skills/oracle-advisor".source == toString skill;
assert toString enabled.home.file.".claude/skills/oracle-advisor".source == toString skill;
pkgs.runCommand "oracle-skills-check" { } ''
  test -f ${skill}/SKILL.md
  grep -Fx 'name: oracle-advisor' ${skill}/SKILL.md
  touch "$out"
''
