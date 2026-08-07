#!/bin/bash
set -euo pipefail

rm -rf /tmp/tuiweathergirl
mkdir -p /tmp/tuiweathergirl
# git clone --depth 1 https://github.com/StrayFeral/tuiweathergirl /tmp/tuiweathergirl
curl -L -O --output-dir /tmp/tuiweathergirl/ "https://github.com/StrayFeral/tuiweathergirl/releases/latest/download/tuiweathergirl.zip"
echo ""
echo "Installing TUIWEATHERGIRL, please wait ..."
unzip /tmp/tuiweathergirl/tuiweathergirl.zip -d /tmp/tuiweathergirl/
make -f /tmp/tuiweathergirl/Makefile install
rm -rf /tmp/tuiweathergirl
