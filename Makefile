# DA4Linux Makefile — build-free install for any Linux distribution.
# The Python package itself is installed with pip (system, --user, or a
# venv); this Makefile installs the launcher and the integration files
# (man page, XDG autostart entry, runit templates).
#
# Usage:
#   make install                          # system-wide (run as root)
#   make install PREFIX=/usr              # for an FHS /usr layout
#   make install DESTDIR=/tmp/stage PREFIX=/usr   # staging for packaging
#   make install-user                     # per-user, no root needed
#   make uninstall                        # remove what install added

PREFIX ?= /usr/local
BINDIR = $(PREFIX)/bin
DATADIR = $(PREFIX)/share
MANDIR = $(DATADIR)/man/man1
SHAREDIR = $(DATADIR)/da4linux
RUNDIR = $(SHAREDIR)/runit
AUTOSTARTDIR ?= /etc/xdg/autostart
XDG_CONFIG_HOME ?= $(HOME)/.config

PYTHON ?= python3

INSTALL = install
SED = sed
RM = rm -f

.PHONY: all install uninstall install-user test clean

all:
	@echo "DA4Linux — no compilation needed (pure Python)"
	@for f in install/da4linux install/da4linux-autostart.desktop docs/da4linux.1 \
	          runit/pipewire/run runit/pipewire-pulse/run runit/wireplumber/run; do \
		[ -f "$$f" ] || { echo "error: missing $$f" >&2; exit 1; }; \
	done
	@echo "sanity check passed — run: make install"

install: all
	@echo "=== Installing DA4Linux ==="
	# Launcher
	$(INSTALL) -d $(DESTDIR)$(BINDIR)
	$(INSTALL) -m 755 install/da4linux $(DESTDIR)$(BINDIR)/da4linux
	# Man page
	$(INSTALL) -d $(DESTDIR)$(MANDIR)
	$(INSTALL) -m 644 docs/da4linux.1 $(DESTDIR)$(MANDIR)/da4linux.1
	# Autostart entry (canonical copy, PREFIX substituted at install time)
	$(INSTALL) -d $(DESTDIR)$(SHAREDIR)
	$(SED) 's|@PREFIX@|$(PREFIX)|' install/da4linux-autostart.desktop \
		> $(DESTDIR)$(SHAREDIR)/da4linux-autostart.desktop
	# XDG autostart — only when running as root (writes outside PREFIX)
	@if [ "$$(id -u)" = 0 ]; then \
		$(INSTALL) -d $(DESTDIR)$(AUTOSTARTDIR); \
		$(INSTALL) -m 644 $(DESTDIR)$(SHAREDIR)/da4linux-autostart.desktop \
			$(DESTDIR)$(AUTOSTARTDIR)/da4linux-autostart.desktop; \
	fi
	# runit templates (reference copies)
	$(INSTALL) -d $(DESTDIR)$(RUNDIR)
	cp -r runit/pipewire runit/pipewire-pulse runit/wireplumber $(DESTDIR)$(RUNDIR)/
	@echo ""
	@echo "DA4Linux installed to $(PREFIX)"
	@echo "  Launcher:  $(BINDIR)/da4linux"
	@echo "  Man page:  $(MANDIR)/da4linux.1"
	@echo "  Autostart: $(SHAREDIR)/da4linux-autostart.desktop"
	@echo "  runit templates: $(RUNDIR)/"
	@echo ""
	@echo "Note: the da4linux Python package must be importable by $(PYTHON)"
	@echo "      (install it first, e.g.: $(PYTHON) -m pip install .)"
	@echo "Next: da4linux detect && da4linux generate"

uninstall:
	$(RM) $(DESTDIR)$(BINDIR)/da4linux
	$(RM) $(DESTDIR)$(MANDIR)/da4linux.1
	$(RM) -r $(DESTDIR)$(SHAREDIR)
	$(RM) $(DESTDIR)$(AUTOSTARTDIR)/da4linux-autostart.desktop

install-user:
	@echo "=== Installing DA4Linux user files ==="
	# Autostart entry pointing at $(PREFIX)/bin/da4linux
	$(INSTALL) -d $(XDG_CONFIG_HOME)/autostart
	$(SED) 's|@PREFIX@|$(PREFIX)|' install/da4linux-autostart.desktop \
		> $(XDG_CONFIG_HOME)/autostart/da4linux-autostart.desktop
	# runit templates
	$(INSTALL) -d $(XDG_CONFIG_HOME)/runit
	cp -r runit/pipewire runit/pipewire-pulse runit/wireplumber $(XDG_CONFIG_HOME)/runit/
	@echo "Installed to $(XDG_CONFIG_HOME)/autostart and $(XDG_CONFIG_HOME)/runit"

test:
	$(PYTHON) -m pytest tests/ -v

clean:
	@echo "Nothing to clean (pure Python)"
