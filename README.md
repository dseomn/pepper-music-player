# Pepper Music Player

Open source music player written in Python; not yet ready for general
consumption.

**NOTE**: This is alpha software. Configuration and other data may not be
preserved across code changes. Functionality may change or disappear without
warning.

## Features

*   Plays local audio files.
*   Supports [ReplayGain](https://en.wikipedia.org/wiki/ReplayGain).
*   Supports [gapless playback](https://en.wikipedia.org/wiki/Gapless_playback).
*   Runs on Linux and macOS.

<!-- TODO(dseomn): Add screenshots? -->

## Goals

*   Focus primarily on album playback, but offer track-focused playback options
    too.
*   Easily handle a music library with about 10k files.
*   Handle a variety of metadata gracefully. E.g.,
    [track titles longer than 255 code points](https://musicbrainz.org/recording/9685f9b6-9154-414a-9a4a-109dafce92b2),
    [non-square album art](https://en.wikipedia.org/wiki/J-card), and
    [bidirectional text](https://en.wikipedia.org/wiki/Bidirectional_text).
*   Internationalize and localize the app as much as possible.
*   [last.fm](https://www.last.fm/) scrobbling
*   [MPRIS](https://www.freedesktop.org/wiki/Specifications/mpris-spec/) support

## Potential future goals

*   Playback of remote streams
*   [MusicBrainz](https://musicbrainz.org/) integration
*   Easy to install packages on Linux and macOS
*   Run on Windows.
*   Easily handle a music library with about 100k files.

## Non-goals

*   Music library management. There are other good tools for this, e.g.,
    [MusicBrainz Picard](https://picard.musicbrainz.org/) and
    [Ex Falso](https://quodlibet.readthedocs.io/en/latest/guide/commands/exfalso.html).

## Development

*   Almost all code should be tested: [![test workflow
    status,](https://github.com/dseomn/pepper-music-player/workflows/.github/workflows/test.yaml/badge.svg)](https://github.com/dseomn/pepper-music-player/actions?query=workflow%3A.github%2Fworkflows%2Ftest.yaml)
    [![coverage
    status,](https://codecov.io/gh/dseomn/pepper-music-player/branch/master/graph/badge.svg)](https://codecov.io/gh/dseomn/pepper-music-player)
    [![visual
    tests.](https://percy.io/static/images/percy-badge.svg)](https://percy.io/dseomn/pepper-music-player)
*   Static analysis is great for catching bugs, so we use
    [pylint](https://github.com/PyCQA/pylint) and
    [pytype](https://github.com/google/pytype).
*   The code mostly follows the [Google Python Style
    Guide](https://google.github.io/styleguide/pyguide.html).
*   [YAPF](https://github.com/google/yapf) makes it easier to code without
    needing to think about formatting too much, so we use it.

## Dependencies

### Debian

```
sudo apt install \
    gir1.2-gst-plugins-base-1.0 \
    gir1.2-gstreamer-1.0 \
    gir1.2-gtk-3.0 \
    gstreamer1.0-plugins-good \
    libgirepository1.0-dev \
    python3-frozendict \
    python3-gi \
    python3-jinja2 \
    python3-mutagen
```

## Disclaimer

This is not an officially supported Google product.
