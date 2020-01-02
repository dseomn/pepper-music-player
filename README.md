# Pepper Music Player

Open source music player written in Python; not yet ready for general
consumption.

**NOTE**: This is alpha software. Configuration and other data may not be
preserved across code changes. Functionality may change or disappear without
warning.

## Features

None yet.

## Goals

*   Focus primarily on album playback, but offer track-focused playback options
    too.
*   Playback of local files
*   [ReplayGain](https://en.wikipedia.org/wiki/ReplayGain) support
*   [Gapless playback](https://en.wikipedia.org/wiki/Gapless_playback) between
    tracks on the same album
*   Run on Linux.
*   Easily handle a music library with about 10k files.
*   Handle a variety of metadata gracefully. E.g.,
    [track titles longer than 255 code points](https://musicbrainz.org/recording/9685f9b6-9154-414a-9a4a-109dafce92b2),
    [non-square album art](https://en.wikipedia.org/wiki/J-card), and
    [bidirectional text](https://en.wikipedia.org/wiki/Bidirectional_text).
*   High test coverage. Ideally 95% or more of the application code will be
    covered by unit tests, with occasional integration tests as needed.

## Potential future goals

*   Playback of remote streams
*   [MusicBrainz](https://musicbrainz.org/) integration
*   Run on platforms other than Linux.
*   Easily handle a music library with about 100k files.

## Non-goals

*   Music library management. There are other good tools for this, e.g.,
    [MusicBrainz Picard](https://picard.musicbrainz.org/) and
    [Ex Falso](https://quodlibet.readthedocs.io/en/latest/guide/commands/exfalso.html).

## Dependencies

### Debian

```
sudo apt install \
    gir1.2-gtk-3.0 \
    libgirepository1.0-dev \
    python3-frozendict \
    python3-gi \
    python3-mutagen
```

## Disclaimer

This is not an officially supported Google product.
