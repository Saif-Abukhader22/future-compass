#!/bin/bash
export PYTHONPATH=$(pwd)/..
echo  PYTHONPATH: ${PYTHONPATH}
dotenv run -- uvicorn main:app --host 0.0.0.0 --port 8020 --reload
