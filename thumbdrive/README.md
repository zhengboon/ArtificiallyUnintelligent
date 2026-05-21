# Thumbdrive — qualifier-day deploy package

What goes on the USB stick we bring to the qualifier on Fri 22 May 14:00.

> **Why this exists**: org confirmed 18/5 6:39am no internet guarantee at
> the venue, no own laptop, no setup help from judges. We must have
> everything we need on a USB stick that runs an `setup.sh` on the org VM
> to get our code installed in < 5 min.

## Layout (when fully assembled)

```
thumbdrive/
├── README.md                ← this file
├── setup.sh                 ← the one-command install script
├── make_thumbdrive.sh       ← build script — regenerates the contents
├── ArtificiallyUnintelligent.tar.gz    ← repo tarball (built by make script)
├── best.pt                  ← K's trained YOLO weights (copied from models/)
├── wheels/                  ← offline pip wheels for VM-missing deps
│   ├── pymavlink-*.whl
│   ├── ...
│   └── (whatever else `pip download` collects)
└── runbook.md               ← printed copy of qualifier/day_of_runbook.md
```

The `*.tar.gz`, `*.pt`, and `wheels/` contents are **build artifacts** —
they're gitignored so the repo stays clean. Rebuild with
`./make_thumbdrive.sh` each time anything material changes.

## How to use on Friday

Two copies (USB stick #1 + USB stick #2) — both identical. Plug one in.

```bash
# Copy contents to home dir (USB might be read-only after a while)
cp -r /media/$USER/<USB_LABEL>/thumbdrive ~/

# Run the installer
cd ~/thumbdrive && bash setup.sh
```

`setup.sh` will:
1. Untar the repo into `~/ArtificiallyUnintelligent`
2. Copy `best.pt` into `~/ArtificiallyUnintelligent/models/`
3. `pip install --user` everything in `wheels/` (no internet needed)
4. Print the next-step commands for starting the sim + running the controller

The actual sim start and EKF origin still need to be typed by hand —
they're documented in `runbook.md` for the person reading aloud.

## How to build the thumbdrive (do this on Z's VM, not Windows host)

1. Make sure `models/best.pt` is current (K's latest weights)
2. Make sure repo is in a clean committed state (no untracked .ipynb checkpoints etc.)
3. Run:
   ```bash
   cd ~/AU/thumbdrive && bash make_thumbdrive.sh
   ```
4. Copy the entire `thumbdrive/` folder onto two USB sticks
5. Test: plug a stick into a *fresh* v3 VM, run setup.sh, verify the
   controller runs through `python3 controller.py --no-detect` cleanly.

## Why not just `git clone`?

We could — IF the venue has internet. Org said they can't guarantee that.
USB-stick is the safe default. If internet works, `git clone` works too
(`git clone https://github.com/zhengboon/ArtificiallyUnintelligent`) — but
the repo is currently **private**, so either:

- Make repo public before Friday (5-min `gh repo edit --visibility public`), OR
- Stick to USB-only (this is what `setup.sh` is for)
