# Discord message drafts

Pre-written messages to copy-paste into Discord. Add new drafts at the
bottom; mark each one **DRAFT** until sent, then **SENT YYYY-MM-DD** with
the OP's reply quoted underneath.

Channel is `#support-ticket` unless noted otherwise.

---

## DS-1 — Disk space / runtime environment on demo-day machine — **DRAFT**

> Hi! `<TeamName>_zhengboon`. We're preparing for our qualifier slot on 22 May 14:00.
>
> The provided v3 VM ships with a 49 GB root partition that's already at ~95% used (~2.5 GB free). Our autonomy code uses a custom YOLO model via `ultralytics`, and a fresh `pip install ultralytics` on the stock v3 VM fails partway through with `No space left on device` (it pulls in `torch`, which needs ~2 GB to install). We discovered this when setting up our own VM and worked around it by expanding the VM disk to 100 GB on our host machine.
>
> Three quick questions:
>
> 1. **On the demo-day machines** at Orchard Grand Court, will `ultralytics` (and its `torch` / `torchvision` dependencies) be pre-installed in the VM, or are teams expected to install them in the 15-min setup window?
> 2. If pre-installation isn't planned, would it be permitted for us to either (a) bring our own laptop with the pre-configured VM and demo from there, or (b) resize the VM root partition with `growpart` during the 15-min setup window? (`growpart` is non-destructive and takes < 1 min.)
> 3. As a fallback, we're also exporting our model to ONNX so we can run it with `onnxruntime` (~50 MB install vs torch's ~2 GB) which would fit in the existing free space. If we go that route, no install changes would be needed on the demo machine. Is `onnxruntime` permitted, and is it pre-installed?
> 4. **Is the VM reset between teams?** A 10-min run can write ~100–200 MB of PX4 logs / Gazebo cache / detection output. After several teams, that adds up on a near-full disk. Just want to know whether we should assume a clean VM or budget for whatever previous teams left behind.
>
> Thanks!

**When to send:** as soon as Z is at Discord. Highest-priority info gain — every downstream plan depends on the answer.

**When the OP replies, paste their answer here:**

```
[paste reply]
```

---

## Template for next drafts

```markdown
## DS-<N> — <title> — **DRAFT**

> [message body, formatted as Discord blockquote]

**When to send:** [trigger]
**When the OP replies:** [where it impacts our plans]

[blank line for the actual reply]
```
