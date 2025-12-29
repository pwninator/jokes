{pkgs}: {
  channel = "stable-24.05";
  packages = [
    pkgs.flutter
    pkgs.jdk17
    pkgs.unzip
    pkgs.python313
  ];
  idx.extensions = [
    
  ];
  idx.previews = {
    previews = {
      android = {
        command = [
          "flutter"
          "run"
          "--machine"
          "-d"
          "android"
          "-d"
          "localhost:5555"
        ];
        manager = "flutter";
      };
    };
  };
}