#!/bin/bash
ls -la /home/drone/ArtificiallyUnintelligent/models/
python3 - <<'PY'
import torch, warnings
warnings.filterwarnings("ignore")
ckpt = torch.load("/home/drone/ArtificiallyUnintelligent/models/best.pt",
                  map_location="cpu", weights_only=False)
m = ckpt["model"]
print("classes:", m.names)
print("model class:", type(m).__name__)
PY
