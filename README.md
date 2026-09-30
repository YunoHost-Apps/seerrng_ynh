# SeerrNG for YunoHost

This repository contains SeerrNG's native YunoHost package. It installs the official prebuilt Linux release archives for `amd64` and `arm64`, uses YunoHost's Node.js 22 runtime, and stores application data in YunoHost's persistent app data directory.

Install manually with:

```bash
sudo yunohost app install https://github.com/YunoHost-Apps/seerrng_ynh --debug
```

The package tracks stable SeerrNG releases with YunoHost's `latest_github_release` source updater and architecture-specific asset patterns. YunoHost's infrastructure periodically proposes manifest URL and checksum updates; administrators apply those updates through the normal YunoHost app upgrade flow.

SeerrNG requires a dedicated domain root because it does not support URL subpaths. The package does not integrate with YunoHost LDAP or portal SSO. For application usage and administration, see the [SeerrNG documentation](https://snapetech.github.io/seerrng/).
