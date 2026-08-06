# runit services for the PipeWire user session

These templates run the PipeWire user session (`pipewire`, `wireplumber`,
`pipewire-pulse`) under runit. They are for init systems without systemd
user services — e.g. Devuan with runit — where PipeWire normally runs as a
plain user-session process rather than a supervised service.

```
runit/
├── pipewire/run        # main PipeWire daemon
├── pipewire-pulse/run  # PulseAudio compatibility daemon
├── wireplumber/run     # PipeWire session manager
└── README.md
```

Each `run` script is a plain `#!/bin/sh` script that `exec`s the service in
the foreground (runit's requirement). `pipewire-pulse` and `wireplumber`
poll for the main `pipewire-0` socket (up to ~10s) before exec, because
runit starts services in parallel — without the wait they race the main
daemon and fail with "Host is down". The wait also requires the `pipewire`
process to be running, so a stale socket left by a dead daemon does not
count as ready.

## Install

Make the scripts executable:

```bash
chmod +x runit/pipewire/run runit/pipewire-pulse/run runit/wireplumber/run
```

Then copy the service directories to where runit will supervise them.

### Per-user (recommended for a desktop)

PipeWire is a per-user audio service, so per-user supervision is the
correct choice for a single-user desktop:

```bash
mkdir -p ~/.config/runit
cp -r runit/pipewire runit/pipewire-pulse runit/wireplumber ~/.config/runit/
```

### System-wide

```bash
sudo mkdir -p /etc/runit/runsvdir
sudo cp -r runit/pipewire runit/pipewire-pulse runit/wireplumber /etc/runit/runsvdir/
```

Which directory to use depends on whether you start services per-user
(`runsvdir-user`) or system-wide. For PipeWire, per-user is correct: each
user gets their own audio session.

## Managing the services

```bash
sv status pipewire
sv restart pipewire
sv stop pipewire
sv start pipewire
```

`sv restart pipewire` is the runit equivalent of
`systemctl --user restart pipewire`.

## Starting runsvdir at login

Your exact session startup is unknown, so here are two systemd-independent
options.

### Option A: ~/.xinitrc (X11)

Add this before starting your window manager:

```bash
runsvdir -P "$HOME/.config/runit" &
```

### Option B: login shell rc (~/.profile or ~/.bash_profile)

```bash
# Start per-user PipeWire services at login (runit)
if [ -d "$HOME/.config/runit" ] && [ -z "$RUNSVDIR_STARTED" ]; then
    export RUNSVDIR_STARTED=1
    runsvdir -P "$HOME/.config/runit" &
fi
```

The `RUNSVDIR_STARTED` guard prevents a second runsvdir when a login shell
profile runs inside an already-started session.

### Option C: runsvdir-user service

If your distribution ships a `runsvdir-user` service (Devuan does), point
it at your per-user directory instead of starting runsvdir manually. See
`ls /etc/sv/` for a `runsvdir-user` service and configure its `run` script
to supervise `~/.config/runit`.

## Notes

- The `run` scripts set `XDG_RUNTIME_DIR` to `/run/user/<uid>` when it is
  not already set, so the services work outside a full session.
- If you previously started PipeWire manually (e.g. from `~/.xinitrc` or a
  shell script), remove that so you don't end up with two instances.
- `da4linux restart-pipewire` is the manual equivalent of
  `sv restart pipewire` when you are not using runit supervision. If it
  detects that pipewire is supervised (a service dir under
  `/etc/service`, `/etc/sv`, or `~/.config/runit`), it delegates to
  `sv restart pipewire pipewire-pulse wireplumber` instead of killing and
  respawning the daemons itself.