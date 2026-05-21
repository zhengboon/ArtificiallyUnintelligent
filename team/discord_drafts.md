# Discord message drafts

Pre-written messages to copy-paste into Discord. Add new drafts at the
bottom; mark each one **DRAFT** until sent, then **SENT YYYY-MM-DD** with
the OP's reply quoted underneath.

Channel is `#support-ticket` unless noted otherwise.

---

## DS-1 — Demo-day machine: ultralytics pre-installed? bring own laptop OK? — **RESOLVED 2026-05-21 (answered by org's public announcements; ticket never sent)**

**Resolution summary** (via org's #general posts, not this ticket):
- ultralytics + torch ARE pre-installed in qualifier VM (org 16/5 11:32am)
- Bring own laptop NOT allowed (org 18/5 6:39am rule #1)
- Deploy via USB stick (`thumbdrive/`), no internet needed (org 18/5 rule #3)
- No setup help from judges; judges only reset VM on request (org 18/5 rule #4)
- VM specs: up to 8 cores, 8GB RAM, 50GB disk, reset between teams (org 21/5)
- No points deduction for incorrect detections (org 21/5)

---

**Original draft (kept for record, NOT sent)**

(v1 was broader, including the general "disk fills up" question. That's been answered separately by the OP in `#general`/`#tech-discussion` on 13/5/2026 6:00 PM — it's PX4 SITL logs; cleanup with `rm -rf ~/PX4-Autopilot/build/px4_sitl_default/rootfs/log/*`. This v2 focuses on the install-time question that's still open.)

> Hi! `<TeamName>_zhengboon`. We're preparing for our qualifier slot on 22 May 14:00.
>
> Thanks for the disk-cleanup tip in #general re: the PX4 SITL logs — that's solved our day-to-day diskspace creep. We still have an install-time concern we'd appreciate clarification on.
>
> Our autonomy code uses YOLO via the `ultralytics` Python package (pulls in `torch` ≈ 2 GB and `torchvision` ≈ 500 MB). On the stock v3 VM (49 GB partition, ~95% used), a fresh `pip install ultralytics` fails midway with `No space left on device` because torch's extraction needs ~3 GB of free space. We discovered this and worked around it on our own VM by expanding the partition to 100 GB.
>
> Three questions:
>
> 1. On the demo-day machines at Orchard Grand Court, will `ultralytics` + `torch` / `torchvision` be **pre-installed** in the VM, or are teams expected to install them in the 15-min setup window?
> 2. If not pre-installed, would it be permitted for us to either (a) bring our own laptop with the pre-configured VM and demo from there, or (b) expand the VM root partition with `growpart` during the 15-min setup window? (`growpart` is non-destructive and takes < 1 min.)
> 3. As a fallback, we're also exporting our model to ONNX so we can run inference with `onnxruntime` (~50 MB install vs torch's ~2 GB) — would fit in the existing free space. Is `onnxruntime` permitted, and is it pre-installed?
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
