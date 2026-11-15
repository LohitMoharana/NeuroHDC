#!/bin/bash
# usage: run_asic_rev.sh <design> <tag>   (non-interactive equivalent of `make mount` + flow.tcl)
cd ~/OpenLane
docker run --rm -v /home/lohit/OpenLane:/openlane -v /home/lohit/OpenLane/designs:/openlane/install -v /home/lohit:/home/lohit -v /home/lohit/.ciel:/home/lohit/.ciel -e PDK_ROOT=/home/lohit/.ciel -e PDK=sky130A --user 1000:1000 --network host --security-opt seccomp=unconfined ghcr.io/the-openroad-project/openlane:ff5509f65b17bfa4068d5336495ab1718987ff69-amd64 bash -c "cd /openlane && ./flow.tcl -design $1 -tag $2 -overwrite"
