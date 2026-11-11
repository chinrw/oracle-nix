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
        in
        {
          options.programs.oracle = {
            enable = lib.mkEnableOption "Oracle CLI and MCP server";
            package = lib.mkOption {
              type = lib.types.package;
              default = pkgs.callPackage ./package { };
              description = "Oracle package installed in the user environment.";
            };
          };
          config = lib.mkIf cfg.enable {
            home.packages = [ cfg.package ];
          };
        };
      checks = eachSystem (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          oracle = self.packages.${system}.oracle;
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
