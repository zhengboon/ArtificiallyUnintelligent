#!/bin/bash
echo "==== files ===="
ls -la /home/drone/ArtificiallyUnintelligent/searchctl/
echo
echo "==== controller.py parse ===="
python3 -c "
import ast
ast.parse(open('/home/drone/ArtificiallyUnintelligent/searchctl/controller.py').read())
print('controller.py parses OK')
"
echo
echo "==== wall_following.py importable ===="
python3 -c "
import sys
sys.path.insert(0, '/home/drone/ArtificiallyUnintelligent/searchctl')
from wall_following import WallFollower, get_wall_distances, VelocitySmoother
print('wall_following imports OK')
import numpy as np
wf = WallFollower()
sm = VelocitySmoother()
# Smoke test get_wall_distances with empty + tiny synthetic point cloud
print('initial state:', wf.state)
print('empty regions:', get_wall_distances(np.empty((0,3))))
print('synthetic obstacle 1m forward:', get_wall_distances(np.array([[0.0, 0.0, 2.0]], dtype=np.float32)))
cmd = wf.compute({'front': 2.0, 'front_right': 5.0, 'right': 1.5})
print('compute on synthetic regions:', cmd)
print('after compute state:', wf.state)
"
