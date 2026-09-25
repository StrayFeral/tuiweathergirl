#!/usr/bin/env bash
# Make a test local .deb package so I can manually inspect/test with Lintian
dpkg-buildpackage -us -uc -b
