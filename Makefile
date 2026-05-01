SHELL := /bin/bash
.ONESHELL:
.SHELLFLAGS := -euo pipefail -c

# by StrayF 2026

BIN_DIR = $(HOME)/.local/bin
SCRIPT_NAME = tuiweathergirl.py
TARGET_NAME = tuiweathergirl

.PHONY: help install

MAKEFILEPATH := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))

install:
	@if ! command -v python3 &> /dev/null; then \
		sudo apt-get update && sudo apt-get install -y python3; \
	fi
	sudo apt-get update && sudo apt-get install -y python3-babel python3-requests libncurses6 tzdata
	mkdir -p $(BIN_DIR)
	cp $(SCRIPT_NAME) $(BIN_DIR)/$(TARGET_NAME)
	chmod +x $(BIN_DIR)/$(TARGET_NAME)
	@echo ""
	@echo "Installation complete! You can now run '$(TARGET_NAME)'"

help:
	@echo "TARGETS:"
	@echo "  make install	- Installation"
