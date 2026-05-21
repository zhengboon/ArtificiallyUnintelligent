#!/bin/bash
RUN_DIR=$(ls -td /home/drone/ArtificiallyUnintelligent/searchctl/run_* 2>/dev/null | head -1)
echo "Latest run dir: $RUN_DIR"
echo
if [ -z "$RUN_DIR" ]; then echo "(no run dir found)"; exit 0; fi
echo "--- contents ---"
ls -la "$RUN_DIR/"
echo
echo "--- map_frames/ ---"
ls -la "$RUN_DIR/map_frames/" 2>/dev/null | head -20
echo
echo "--- detections/ ---"
ls -la "$RUN_DIR/detections/" 2>/dev/null | head -20
echo
echo "--- map_points.npy info ---"
if [ -f "$RUN_DIR/map_points.npy" ]; then
    python3 -c "import numpy as np; p = np.load('$RUN_DIR/map_points.npy'); print(f'shape: {p.shape}, dtype: {p.dtype}'); print(f'N range: [{p[:,0].min():.2f}, {p[:,0].max():.2f}]' if len(p) else 'empty'); print(f'E range: [{p[:,1].min():.2f}, {p[:,1].max():.2f}]' if len(p) else 'empty')"
fi
echo
echo "--- run_summary.json ---"
cat "$RUN_DIR/run_summary.json" 2>/dev/null | head -30
