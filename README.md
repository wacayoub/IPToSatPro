# IPToSat Pro

IPToSat Pro for Enigma2 / OpenATV.

**Latest online version:** 1.0.46-r62 — NEO Dark + Comfortable (8 October 2026).

## Update from IPToSat Pro on the receiver

Open IPToSat Pro → Dashboard → **2 Online Update** → **GREEN Check GitHub** → confirm installation.

The in-plugin updater reads [update.json](update.json), downloads the repository's Base64-encoded IPK, and checks the exact package size and SHA-256 before installing.

## Download verified IPK to /tmp from SSH

```sh
wget -O /tmp/iptosat-get.sh https://raw.githubusercontent.com/wacayoub/IPToSatPro/main/download-latest.sh
sh /tmp/iptosat-get.sh
opkg install --force-reinstall /tmp/iptosatpro.ipk
```

This is a UI-only update based on r61: NEO Dark/Comfortable by default, Metrix Fusion and OLED Minimal options. Mapping data, audio, timeshift, SAT playback and the TS bridge are not removed.
