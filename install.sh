#!/bin/sh
pip3 install -r requirements.txt
./setup.py install
systemctl stop zerowire
cp zerowire.service /etc/systemd/system/
systemctl daemon-reload
systemctl start zerowire
