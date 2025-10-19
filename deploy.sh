#!/bin/bash
cd ~/stark
git pull
sudo systemctl restart stark-ai.service
echo "✅ Deploy completed"
