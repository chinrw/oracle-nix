{
  description = "Oracle CLI and MCP server packaged for Nix";

  inputs.nixpkgs.url = "github:nixos/nixpkgs/nixpkgs-unstable";

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
      ];
      eachSystem = nixpkgs.lib.genAttrs systems;
      packageFor = system: nixpkgs.legacyPackages.${system}.callPackage ./package { };
    in
    {
      packages = eachSystem (system: {
        default = self.packages.${system}.oracle;
        oracle = packageFor system;
        oracle-advisor = nixpkgs.legacyPackages.${system}.callPackage ./skills { };
      });
      apps = eachSystem (system: {
        default = self.apps.${system}.oracle;
        oracle = {
          type = "app";
          program = "${self.packages.${system}.oracle}/bin/oracle";
        };
        oracle-mcp = {
          type = "app";
          program = "${self.packages.${system}.oracle}/bin/oracle-mcp";
        };
      });
      overlays.default = final: _prev: {
        oracle = final.callPackage ./package { };
      };
      homeManagerModules.default =
        {
          config,
          lib,
          pkgs,
          ...
        }:
        let
          cfg = config.programs.oracle;
          package =
            if cfg.apiKeyFile == null then
              cfg.package
            else
              cfg.package.override {
                apiKeyFile = cfg.apiKeyFile;
              };
        in
        {
          options.programs.oracle = {
            enable = lib.mkEnableOption "Oracle CLI and MCP server";
            skills.enable = lib.mkEnableOption "the upstream oracle-advisor skill for Codex, pi and Claude Code";
            apiKeyFile = lib.mkOption {
              type = lib.types.nullOr (lib.types.strMatching "/.*");
              default = null;
              description = "Absolute runtime path to an OpenAI API key; explicit OPENAI_API_KEY takes precedence. The file is not read during evaluation or build.";
            };
            package = lib.mkOption {
              type = lib.types.package;
              default = pkgs.callPackage ./package { };
              description = "Oracle package installed in the user environment.";
            };
          };
          config = lib.mkIf cfg.enable {
            home.packages = [ package ];
            home.file = lib.mkIf cfg.skills.enable {
              ".agents/skills/oracle-advisor".source =
                self.packages.${pkgs.stdenv.hostPlatform.system}.oracle-advisor;
              ".claude/skills/oracle-advisor".source =
                self.packages.${pkgs.stdenv.hostPlatform.system}.oracle-advisor;
            };
          };
        };
      checks = eachSystem (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          oracle = self.packages.${system}.oracle;
          skills = import ./tests/skills.nix {
            inherit pkgs;
            module = self.homeManagerModules.default;
            skill = self.packages.${system}.oracle-advisor;
          };
          api-key-file =
            let
              wrapped = self.packages.${system}.oracle.override {
                apiKeyFile = "/tmp/oracle-nix-keyfile-check";
              };
            in
            assert
              !(builtins.tryEval (
                (self.packages.${system}.oracle.override {
                  apiKeyFile = "relative-key";
                }).drvPath
              )).success;
            assert
              !(builtins.tryEval (
                (self.packages.${system}.oracle.override {
                  apiKeyFile = "/nix/store/not-a-runtime-secret";
                }).drvPath
              )).success;
            pkgs.runCommand "oracle-api-key-file-check"
              {
                nativeBuildInputs = [ pkgs.python3 ];
              }
              ''
                python3 ${./tests/keyfile.py} ${wrapped}
                touch "$out"
              '';
          updater =
            pkgs.runCommand "oracle-updater-tests"
              {
                nativeBuildInputs = [ pkgs.python3 ];
              }
              ''
                cp -r ${./scripts} scripts
                cp -r ${./tests} tests
                export PYTHONDONTWRITEBYTECODE=1
                python3 -m unittest discover -s tests -v
                touch "$out"
              '';
        }
      );
      formatter = eachSystem (system: nixpkgs.legacyPackages.${system}.nixfmt);
      devShells = eachSystem (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          default = pkgs.mkShell {
            packages = with pkgs; [
              nodejs_24
              python3
              prefetch-npm-deps
              nixfmt
              actionlint
              git
            ];
          };
        }
      );
    };
}
