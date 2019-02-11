#!/bin/bash
git clone https://github.com/mattmb/zookeeper.git /zookeeper
cd /zookeeper
git checkout release-3.4.5-hack
ant
cp build/zookeeper-3.4.5.jar /usr/share/java/zookeeper.jar
/usr/share/zookeeper/bin/zkServer.sh start-foreground
