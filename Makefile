SHELL := /bin/bash
.ONESHELL:
.SHELLFLAGS := -euo pipefail -c

# by StrayF 2026 (Updated for Cross-Distro Support)

BIN_DIR = $(HOME)/.local/bin
SCRIPT_NAME = tuiweathergirl.py
TARGET_NAME = tuiweathergirl

.PHONY: help install install-deps

MAKEFILEPATH := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))

install: install-deps
	@echo ""
	mkdir -p $(BIN_DIR)
	cp $(MAKEFILEPATH)/$(SCRIPT_NAME) $(BIN_DIR)/$(TARGET_NAME)
	chmod +x $(BIN_DIR)/$(TARGET_NAME)
	@echo ""
	@echo "Installation complete! You can now run '$(TARGET_NAME)'"

install-deps:
	@echo "INSTALLING TUIWEATHERGIRL"
	@echo "========================="
	@if command -v apt-get &> /dev/null; then \
		echo "* Debian installation"; \
		echo ""; \
		sudo apt-get update && sudo apt-get install -y python3 python3-babel python3-requests libncurses6 tzdata; \
	elif command -v dnf &> /dev/null; then \
		echo "* Red Hat installation"; \
		echo ""; \
		sudo dnf install -y python3 python3-babel python3-requests ncurses-libs tzdata; \
	elif command -v yum &> /dev/null; then \
		echo "* RHEL installation"; \
		echo ""; \
		sudo yum install -y python3 python3-babel python3-requests ncurses-libs tzdata; \
	elif command -v pacman &> /dev/null; then \
		echo "* Arch installation"; \
		echo ""; \
		sudo pacman -Sy --noconfirm python python-babel python-requests ncurses tzdata; \
	elif command -v zypper &> /dev/null; then \
		echo "* openSUSE installation"; \
		echo ""; \
		sudo zypper install -y python3 python3-babel python3-requests libncurses6 timezone; \
	elif command -v emerge &> /dev/null; then \
		echo "* Gentoo installation"; \
		echo ""; \
		sudo emerge --noreplace dev-lang/python dev-python/babel dev-python/requests sys-libs/ncurses sys-libs/timezone-data; \
	else \
		echo "Error: Could not detect a supported package manager (apt, dnf, yum, pacman, zypper, emerge)." >&2; \
		exit 1; \
	fi

help:
	@echo "TARGETS:"
	@echo "  make install  - Install application and dependencies"
