#!/bin/bash
uvicorn main:app --host 0.0.0.0 --port 8082 &
streamlit run ui/dashboard.py --server.port 8502 --server.address 0.0.0.0
wait -n
