#!/bin/bash
# User data de lt-worker (guía §8.3). Los huecos los llena "bash infra/userdata.sh lt-worker",
# que lee los buckets de infra/entorno.sh y averigua el id del EFS solo.
set -euxo pipefail

mount -t efs -o tls __FS_MODELOS__:/ /mnt/modelos
echo "__FS_MODELOS__:/ /mnt/modelos efs _netdev,tls 0 0" >> /etc/fstab

aws s3 cp s3://__BUCKET_DEPLOY__/worker/worker-latest.zip /opt/worker/
cd /opt/worker
unzip -o worker-latest.zip
aws s3 cp s3://__BUCKET_DEPLOY__/config/worker.env /etc/ateneo.env
chmod 600 /etc/ateneo.env

systemctl reset-failed ateneo-worker || true
systemctl start ateneo-worker
