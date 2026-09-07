#!/bin/bash
# User data de lt-worker (guía §8.3). Idéntico al de la guía. Reemplazá fs-XXXXXXXX en las dos líneas.
set -euxo pipefail

mount -t efs -o tls fs-XXXXXXXX:/ /mnt/modelos
echo "fs-XXXXXXXX:/ /mnt/modelos efs _netdev,tls 0 0" >> /etc/fstab

aws s3 cp s3://ateneo-deploy-g7/worker/worker-latest.zip /opt/worker/
cd /opt/worker
unzip -o worker-latest.zip
aws s3 cp s3://ateneo-deploy-g7/config/worker.env /etc/ateneo.env
chmod 600 /etc/ateneo.env

systemctl reset-failed ateneo-worker
systemctl start ateneo-worker
