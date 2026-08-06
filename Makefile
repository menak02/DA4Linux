# DA4Linux Makefile — build-free install for any Linux distribution
# Usage:
#   make install           # install to /usr/local (default)
#   make install PREFIX=/usr
#   make install DESTDIR=/tmp/staging PREFIX=/usr  # for packaging

PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin
DATADIR ?= $(PREFIX)/share
APPDIR ?= $(DATADIR)/applications
AUTOSTARTDIR ?= /etc/xdg/autostart
MODULEDIR ?= $(DATADIR)/da4linux
MANDIR ?= $(DATADIR)/man/man1

SRCDIR = src/da4linux

.PHONY: all install uninstall clean test

all:
	@echo "DA4Linux — no compilation needed (pure Python)"
	@echo "Run: make install"

install:
	@echo "=== Installing DA4Linux ==="
	# Install Python modules
	install -d $(DESTDIR)$(MODULEDIR)/da4linux
	install -d $(DESTDIR)$(MODULEDIR)/da4linux/profiles
	cp $(SRCDIR)/*.py $(DESTDIR)$(MODULEDIR)/da4linux/
	cp $(SRCDIR)/profiles/*.py $(DESTDIR)$(MODULEDIR)/da4linux/profiles/
	# Install launcher
	install -d $(DESTDIR)$(BINDIR)
	install -m 755 install/da4linux $(DESTDIR)$(BINDIR)/da4linux
	# Install .desktop file
	install -d $(DESTDIR)$(APPDIR)
	install -m 644 install/da4linux-autostart.desktop $(DESTDIR)$(APPDIR)/
	# Symlink into XDG autostart
	install -d $(DESTDIR)$(AUTOSTARTDIR)
	ln -sf $(APPDIR)/da4linux-autostart.desktop $(DESTDIR)$(AUTOSTARTDIR)/da4linux-autostart.desktop 2>/dev/null || \
		cp $(APPDIR)/da4linux-autostart.desktop $(DESTDIR)$(AUTOSTARTDIR)/
	# Install man page (if exists)
	@if [ -f docs/da4linux.1 ]; then \
		install -d $(DESTDIR)$(MANDIR); \
		install -m 644 docs/da4linux.1 $(DESTDIR)$(MANDIR)/; \
	fi
	@echo ""
	@echo "DA4Linux installed to $(PREFIX)"
	@echo "  Binary:  $(BINDIR)/da4linux"
	@echo "  Modules: $(MODULEDIR)/da4linux/"
	@echo "  Autostart: $(AUTOSTARTDIR)/da4linux-autostart.desktop"
	@echo ""
	@echo "Next: da4linux detect && da4linux generate"

uninstall:
	rm -f $(DESTDIR)$(BINDIR)/da4linux
	rm -rf $(DESTDIR)$(MODULEDIR)
	rm -f $(DESTDIR)$(APPDIR)/da4linux-autostart.desktop
	rm -f $(DESTDIR)$(AUTOSTARTDIR)/da4linux-autostart.desktop
	rm -f $(DESTDIR)$(MANDIR)/da4linux.1

test:
	python3 -m pytest tests/ -v

clean:
	@echo "Nothing to clean (pure Python)"
