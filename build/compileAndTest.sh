#!/bin/bash
python -m compileall   agent-runtime   tests   -q   && PYTHONPATH="./agent-runtime" python -m pytest tests -q