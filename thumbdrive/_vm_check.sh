#!/bin/bash
# Run inside the VM to verify env + symlink verylousymodel as default weights.
set -e
cd /home/drone/ArtificiallyUnintelligent/models
ln -sf verylousymodel.pt best.pt
echo "--- models ---"
ls -la /home/drone/ArtificiallyUnintelligent/models/
echo
echo "--- pymavlink ---"
python3 -c "import pymavlink; print(pymavlink.__version__)" || echo "MISSING"
echo "--- ultralytics ---"
python3 -c "import ultralytics; print(ultralytics.__version__)" || echo "MISSING"
echo "--- mavsdk ---"
python3 -c "import mavsdk; print(mavsdk.__version__)" || echo "MISSING"
echo "--- gz.transport13 ---"
python3 -c "from gz.transport13 import Node; print('ok')" || echo "MISSING"
echo "--- gz.msgs10 ---"
python3 -c "import os; os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION']='python'; from gz.msgs10.image_pb2 import Image; print('ok')" || echo "MISSING"
echo "--- matplotlib ---"
python3 -c "import matplotlib; print(matplotlib.__version__)" || echo "MISSING"
echo "--- numpy ---"
python3 -c "import numpy; print(numpy.__version__)" || echo "MISSING"
echo "--- python ---"
python3 --version
